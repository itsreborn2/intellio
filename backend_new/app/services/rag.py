"""RAG 서비스"""

from typing import Dict, Any, List, Union, Tuple
from uuid import UUID
import pandas as pd
import logging
import asyncio
from sqlalchemy import select
import re

from app.core.config import settings
from app.services.embedding import EmbeddingService
from app.services.prompts import ChatPrompt, TablePrompt, TableHeaderPrompt
from app.models.document import Document
from app.schemas.table_response import TableHeader, TableCell, TableColumn, TableResponse
from app.schemas.table_history import TableHistoryCreate
from app.services.table_history import TableHistoryService

logger = logging.getLogger(__name__)

# 문서 상태 상수
DOCUMENT_STATUS_REGISTERED = 'REGISTERED'
DOCUMENT_STATUS_UPLOADING = 'UPLOADING'
DOCUMENT_STATUS_UPLOADED = 'UPLOADED'
DOCUMENT_STATUS_PROCESSING = 'PROCESSING'
DOCUMENT_STATUS_COMPLETED = 'COMPLETED'
DOCUMENT_STATUS_PARTIAL = 'PARTIAL'
DOCUMENT_STATUS_ERROR = 'ERROR'
DOCUMENT_STATUS_DELETED = 'DELETED'

class RAGService:
    """RAG 서비스"""

    def __init__(self):
        """RAG 서비스 초기화"""
        self.embedding_service = EmbeddingService()
        self.chat_prompt = ChatPrompt()
        self.table_prompt = TablePrompt()
        self.table_header_prompt = TableHeaderPrompt()
        self.db = None
        # 동시 처리할 최대 문서 수 (rate limit 고려)
        self.max_concurrent = 5
        # 청크 수 관련 설정
        self.chunk_multiplier = 5  # 청크 수 배수
        self.max_chunks_per_doc = 10  # 문서당 최대 청크 수

    async def initialize(self, db):
        """DB 세션 초기화"""
        self.db = db

    async def verify_document_access(self, document_id: str) -> bool:
        """문서 접근 권한 확인

        Args:
            document_id: 확인할 문서 ID

        Returns:
            bool: 접근 가능 여부
        """
        try:
            # 문서 존재 여부 확인
            result = await self.db.execute(
                select(Document)
                .where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()

            if not document:
                logger.warning(f"문서를 찾을 수 없음: {document_id}")
                return False

            # 문서 상태 확인
            if document.status not in ['COMPLETED', 'PARTIAL']:
                logger.warning(f"문서가 아직 처리되지 않음: {document_id} (상태: {document.status})")
                return False

            # 임베딩 존재 여부 확인
            if not document.embedding_ids:
                logger.warning(f"문서에 임베딩이 없음: {document_id}")
                return False

            return True

        except Exception as e:
            logger.error(f"문서 접근 권한 확인 중 오류 발생: {str(e)}", exc_info=True)
            return False

    def _normalize_query(self, query: str) -> str:
        """쿼리 정규화 - 유사한 표현을 통일하여 캐시 효율성 향상

        Args:
            query: 원본 쿼리

        Returns:
            str: 정규화된 쿼리
        """
        import re

        # 1. 기본 정규화
        query = re.sub(r'\s+', ' ', query.strip())

        # 2. 날짜 표현 정규화
        query = re.sub(r'(\d{4})년도?', r'\1년', query)
        query = re.sub(r'(\d{1,2})월달?', r'\1월', query)
        query = re.sub(r'(\d{1,2})분기말?', r'\1분기', query)

        # 3. 한국어 특화 표현 통일
        replacements = {
            r'얼마(예요|인가요|인가|야|니|나요)': '얼마입니까',
            r'알려줘': '알려주세요',
            r'보여줘': '보여주세요',
            r'찾아줘': '찾아주세요',
            r'뭐야': '무엇입니까',
            r'뭐니': '무엇입니까',
            r'있니': '있습니까',
            r'없니': '없습니까'
        }

        for pattern, replacement in replacements.items():
            query = re.sub(pattern, replacement, query)

        return query

    async def _search_document_chunks(self, doc_id: str, query: str, top_k: int) -> List[Dict[str, Any]]:
        """단일 문서의 청크 검색 (에러 처리 포함)"""
        try:
            # 쿼리 분석
            query_analysis = self._analyze_query(query)

            # 증권사 관련 쿼리인 경우, 문서 시작 부분도 포함
            if query_analysis["requires_all_docs"] or query_analysis["query_type"] == "securities":
                first_chunk = self.embedding_service.get_first_chunk(doc_id)
                chunks = await self.embedding_service.search_similar(
                    query=query,
                    document_ids=[doc_id],
                    top_k=min(self.max_chunks_per_doc - 1, self.chunk_multiplier * top_k)
                )
                if first_chunk:
                    # 첫 번째 청크를 앞에 추가 (증권사 정보가 주로 여기에 있음)
                    return [first_chunk] + (chunks or [])

            # 일반 쿼리
            chunks = await self.embedding_service.search_similar(
                query=query,
                document_ids=[doc_id],
                top_k=min(self.max_chunks_per_doc, self.chunk_multiplier * top_k)
            )
            return chunks or []

        except Exception as e:
            logger.error(f"문서 {doc_id} 검색 중 오류 발생: {str(e)}")
            return []

    async def _get_first_chunks_parallel(self, doc_ids: List[str]) -> List[Dict[str, Any]]:
        """여러 문서의 첫 번째 청크 병렬 검색"""
        tasks = [self.embedding_service.get_first_chunk(doc_id) for doc_id in doc_ids]
        chunks = await asyncio.gather(*tasks, return_exceptions=True)

        valid_chunks = []
        for doc_id, chunk in zip(doc_ids, chunks):
            if isinstance(chunk, Exception):
                logger.error(f"문서 {doc_id}의 첫 번째 청크 검색 실패: {str(chunk)}")
            elif chunk:
                valid_chunks.append(chunk)
        return valid_chunks

    def _filter_chunks_by_query(self, chunks: List[Dict[str, Any]], query_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """쿼리 분석 결과에 따라 청크 필터링"""
        filtered_chunks = []

        if query_analysis["query_type"] == "securities":
            securities_patterns = [
                r'([가-힣A-Za-z\s&]+)증권',  # 기본 증권사 패턴
                r'([가-힣A-Za-z\s&]+)\s*Investment\s*&\s*Securities',  # 영문 증권사 패턴
                r'([가-힣A-Za-z\s&]+)\s*리서치센터',  # 리서치센터 패턴
                r'([가-힣A-Za-z\s&]+)\s*투자증권'  # 투자증권 패턴
            ]

            found_securities = set()  # 중복 제거를 위한 집합

            for chunk in chunks:
                content = chunk.get("content", "")
                # 문서 시작 부분에서 증권사 찾기 (처음 몇 줄만)
                first_lines = '\n'.join(content.split('\n')[:5])  # 처음 5줄만 검사

                for pattern in securities_patterns:
                    matches = re.finditer(pattern, first_lines, re.IGNORECASE)
                    for match in matches:
                        company = match.group(1).strip()
                        # 기본적인 정제
                        company = re.sub(r'\s+', ' ', company)  # 연속된 공백 제거
                        found_securities.add(company)

                if found_securities:  # 증권사를 찾은 경우만 청크 추가
                    chunk = chunk.copy()
                    chunk["content"] = f"증권사: {', '.join(found_securities)}"
                    filtered_chunks.append(chunk)
                    found_securities.clear()  # 다음 청크를 위해 초기화
        else:
            filtered_chunks = chunks

        return filtered_chunks

    async def _get_relevant_chunks(self, query: str, top_k: int = 5, document_ids: List[str] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """관련 문서 청크 검색 및 패턴 분석"""
        query_analysis = self._analyze_query(query)
        all_chunks = []

        if document_ids and query_analysis["requires_all_docs"]:
            # 문서 그룹화 (max_concurrent 단위로)
            doc_groups = [document_ids[i:i + self.max_concurrent]
                        for i in range(0, len(document_ids), self.max_concurrent)]

            for group in doc_groups:
                search_tasks = [
                    self._search_document_chunks(doc_id, query, top_k)
                    for doc_id in group
                ]
                chunks_list = await asyncio.gather(*search_tasks)

                for chunks in chunks_list:
                    if chunks:
                        all_chunks.extend(chunks)

            # 쿼리 타입에 따라 청크 필터링
            all_chunks = self._filter_chunks_by_query(all_chunks, query_analysis)

            # 문서별로 가장 관련성 높은 청크만 유지
            doc_chunks = {}
            for chunk in sorted(all_chunks, key=lambda x: x.get("score", 0), reverse=True):
                doc_id = chunk["document_id"]
                if doc_id not in doc_chunks:
                    doc_chunks[doc_id] = chunk

            all_chunks = list(doc_chunks.values())

        else:
            all_chunks = await self.embedding_service.search_similar(
                query=query,
                document_ids=document_ids,
                top_k=top_k
            )
            all_chunks = self._filter_chunks_by_query(all_chunks, query_analysis)

        patterns = self._analyze_chunk_patterns(all_chunks)
        return all_chunks, patterns

    def _analyze_query(self, query: str) -> Dict[str, Any]:
        """쿼리 분석"""
        analysis = {
            "requires_all_docs": False,  # 모든 문서 필요 여부
            "is_comparison": False,      # 비교 분석 필요 여부
            "target_fields": [],         # 목표 필드들
            "query_type": "general",     # 쿼리 타입
            "query": query.lower()       # 원본 쿼리 (소문자)
        }

        # 재무 정보 관련 키워드
        financial_patterns = [
            r'매출액|영업이익|당기순이익|영업이익률|순이익률',
            r'자산|부채|자본|현금흐름|재무상태',
            r'분기|연도|전년|전분기|증감률'
        ]

        # 기업 정보 관련 키워드
        company_info_patterns = [
            r'기업명|회사명|법인명|상호',
            r'증권코드|종목코드|티커',
            r'설립일|설립연도|업력',
            r'대표|임원|이사|경영진',
            r'사업내용|주요제품|서비스'
        ]

        # 시장 정보 관련 키워드
        market_patterns = [
            r'시장점유율|점유율|순위|랭킹',
            r'경쟁사|동종업체|업계',
            r'시장규모|시장현황|산업동향'
        ]

        # 증권사 관련 키워드
        securities_patterns = [
            r'증권사\s*(별|간|들의|의|모든|전체)',
            r'(모든|전체|각)\s*증권사',
            r'리서치\s*(센터|보고서)',
            r'(목표가|투자의견|전망)',
        ]

        # 비교 분석 키워드
        comparison_patterns = [
            r'비교',
            r'차이',
            r'다른',
            r'각각의?',
            r'모든',
            r'전체',
            r'종합'
        ]

        # 쿼리 타입 결정
        for pattern in financial_patterns:
            if re.search(pattern, query):
                analysis["query_type"] = "financial"
                break

        for pattern in company_info_patterns:
            if re.search(pattern, query):
                analysis["query_type"] = "company_info"
                break

        for pattern in market_patterns:
            if re.search(pattern, query):
                analysis["query_type"] = "market"
                break

        # 증권사 관련 쿼리 확인
        for pattern in securities_patterns:
            if re.search(pattern, query):
                analysis["requires_all_docs"] = True
                analysis["query_type"] = "securities"
                break

        # 비교 분석 필요 여부 확인
        for pattern in comparison_patterns:
            if re.search(pattern, query):
                analysis["is_comparison"] = True
                if not analysis["requires_all_docs"]:
                    analysis["requires_all_docs"] = True
                break

        # 목표 필드 식별
        target_patterns = {
            "price_target": r'목표가',
            "investment_opinion": r'투자의견',
            "outlook": r'전망',
            "securities_name": r'증권사\s*이름|증권사\s*명칭|어느\s*증권사'
        }

        for field, pattern in target_patterns.items():
            if re.search(pattern, query):
                analysis["target_fields"].append(field)

        if not analysis["target_fields"]:
            analysis["target_fields"].append("general")

        return analysis

    async def _handle_chat_mode(self, query: str, top_k: int = 5, document_ids: List[str] = None):
        """채팅 모드 처리"""
        try:
            # 관련 문서 검색 및 패턴 분석
            relevant_chunks, patterns = await self._get_relevant_chunks(query, top_k, document_ids)

            if not relevant_chunks:
                return {
                    "answer": "관련 문서를 찾을 수 없습니다.",
                    "context": []
                }

            # 쿼리 분석
            query_analysis = self._analyze_query(query)

            # 문서 컨텍스트 구성
            doc_contexts = []
            for chunk in relevant_chunks:
                doc_contexts.append(
                    f"문서 ID: {chunk.get('document_id', 'N/A')}\n"
                    f"페이지: {chunk.get('page_number', 'N/A')}\n"
                    f"내용: {chunk.get('text', '')}"
                )

            # 프롬프트로 분석
            chain_response = await self.chat_prompt.analyze(
                content='\n\n'.join(doc_contexts),
                query=query,
                patterns=patterns,
                query_analysis=query_analysis
            )

            return {
                "answer": chain_response,
                "context": relevant_chunks
            }

        except Exception as e:
            logger.error(f"채팅 모드 처리 실패: {str(e)}")
            raise

    async def handle_table_mode(self, query: str, document_ids: List[str] = None, user_id: str = None, project_id: str = None) -> TableResponse:
        """테이블 모드 처리"""
        try:
            # 1. 테이블 헤더 생성
            title = await self.table_header_prompt.generate_title(query)
            logger.info("테이블 헤더 생성 완료")

            if not document_ids:
                return TableResponse(columns=[
                    TableColumn(
                        header=TableHeader(name=title, prompt=query),
                        cells=[TableCell(doc_id="1", content="문서가 선택되지 않았습니다.")]
                    )
                ])

            # 2. 관련 청크 검색 및 패턴 분석
            relevant_chunks, patterns = await self._get_relevant_chunks(
                query=query,
                document_ids=document_ids
            )
            logger.info(f"관련 청크 검색 완료 - 총 {len(relevant_chunks)}개 청크 발견")

            # 3. 쿼리 분석
            query_analysis = self._analyze_query(query)
            logger.info(f"쿼리 분석 완료 - 타입: {query_analysis['query_type']}")

            # 4. 문서별로 청크 그룹화
            doc_chunks = {}
            for chunk in relevant_chunks:
                doc_id = chunk["document_id"]
                if doc_id not in doc_chunks:
                    doc_chunks[doc_id] = []
                doc_chunks[doc_id].append(chunk["text"])

            # 5. 모든 문서 동시 분석
            async def analyze_document(doc_id: str):
                try:
                    chunks_text = "\n".join(doc_chunks[doc_id])
                    response = await self._process_table_response(title, chunks_text, patterns, query_analysis)
                    return {
                        "doc_id": doc_id,
                        "content": response
                    }
                except Exception as e:
                    logger.error(f"문서 {doc_id} 분석 중 오류 발생: {str(e)}")
                    return None

            tasks = [analyze_document(doc_id) for doc_id in doc_chunks.keys()]
            results = [result for result in await asyncio.gather(*tasks) if result]

            if not results:
                return TableResponse(columns=[
                    TableColumn(
                        header=TableHeader(name=title, prompt=query),
                        cells=[TableCell(doc_id="1", content="문서 분석 중 오류가 발생했습니다.")]
                    )
                ])

            # 6. TableResponse 생성
            response = TableResponse(columns=[
                TableColumn(
                    header=TableHeader(name=title, prompt=query),
                    cells=[
                        TableCell(
                            doc_id=result["doc_id"],
                            content=result["content"]
                        )
                        for result in results
                    ]
                )
            ])

            # 7. 히스토리 저장 (프로젝트 ID가 있는 경우에만)
            if project_id:
                try:
                    history_service = TableHistoryService(self.db)
                    await history_service.create(
                        TableHistoryCreate(
                            project_id=project_id,
                            document_id=document_ids[0] if document_ids else None,
                            user_id=user_id,
                            prompt=query,
                            title=title,
                            result=str(response.model_dump())  # 딕셔너리를 문자열로 변환
                        )
                    )
                    logger.info("테이블 히스토리 저장 완료")
                except Exception as e:
                    logger.error(f"히스토리 저장 중 오류 발생: {str(e)}")
                    # 히스토리 저장 실패는 전체 프로세스에 영향을 주지 않도록 함

            return response

        except Exception as e:
            logger.error(f"테이블 모드 처리 실패: {str(e)}")
            raise Exception(f"테이블 모드 처리 실패: {str(e)}")

    async def query(
        self,
        query: str,
        mode: str = "chat",
        user_id: str = None,
        project_id: str = None,
        document_ids: List[str] = None,
        top_k: int = 5,
        is_comparison: bool = False
    ) -> Union[Dict[str, Any], TableResponse]:
        """쿼리에 대한 응답 생성
        
        Args:
            query: 사용자 쿼리
            mode: 응답 모드 ("chat" 또는 "table")
            user_id: 사용자 ID
            project_id: 프로젝트 ID
            document_ids: 테이블 모드에서 사용할 문서 ID 목록
            top_k: 검색 결과 상위 k개 반환
            is_comparison: 비교 분석 여부
            
        Returns:
            Union[Dict[str, Any], TableResponse]: 모드에 따른 응답
            - chat 모드: {"answer": str, "context": List[Dict]}
            - table 모드: TableResponse 객체
        """
        if mode == "table":
            return await self.handle_table_mode(query, document_ids=document_ids, user_id=user_id, project_id=project_id)
        return await self._handle_chat_mode(query, top_k, document_ids=document_ids)

    async def get_document_status(self, document_id: str) -> Dict[str, Any]:
        """문서의 상태 조회

        Args:
            document_id: 조회할 문서 ID

        Returns:
            Dict[str, Any]: 문서 상태 정보
        """
        try:
            # 문서 조회
            result = await self.db.execute(
                select(Document)
                .where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()

            if not document:
                return {
                    "document_id": document_id,
                    "status": "NOT_FOUND",
                    "error_message": "문서를 찾을 수 없습니다",
                    "is_accessible": False
                }

            # 접근 가능 여부 확인
            is_accessible = document.status in ['COMPLETED', 'PARTIAL'] and document.embedding_ids

            return {
                "document_id": document_id,
                "status": document.status,
                "error_message": document.error_message,
                "is_accessible": is_accessible
            }

        except Exception as e:
            logger.error(f"문서 상태 조회 중 오류 발생: {str(e)}", exc_info=True)
            return {
                "document_id": document_id,
                "status": "ERROR",
                "error_message": str(e),
                "is_accessible": False
            }

    async def _process_table_response(self, header: str, content: str, patterns: List[str], query_analysis: Dict[str, Any]):
        """테이블 응답 처리
        
        Args:
            header: 테이블 헤더
            content: 분석할 내용
            patterns: 발견된 패턴 목록
            query_analysis: 쿼리 분석 결과
        """
        try:
            # 데이터 전처리
            content = self._preprocess_table_content(content)
            
            # 청크 사이즈 계산 (약 8000 토큰)
            chunk_size = 12000
            chunks = [content[i:i + chunk_size] for i in range(0, len(content), chunk_size)]
            
            results = []
            for chunk in chunks:
                try:
                    completion = await self.table_prompt.analyze(
                        content=chunk,
                        query=header,
                        patterns=patterns,
                        query_analysis=query_analysis
                    )
                    
                    results.append(completion)
                    
                except Exception as e:
                    logger.error(f"테이블 셀 내용 추출 중 오류 발생: {str(e)}")
                    continue
            
            return "\n".join(results) if results else ""
            
        except Exception as e:
            logger.error(f"테이블 응답 처리 실패: {str(e)}")
            raise

    def _preprocess_table_content(self, content: str) -> str:
        """테이블 내용 전처리"""
        # 연속된 공백 제거
        content = content.replace('\n', ' ')
        content = ' '.join(content.split())
        return content.strip()

    def _analyze_chunk_patterns(self, chunks: List[Dict]) -> Dict[str, Any]:
        """임베딩된 청크들의 패턴을 분석

        Args:
            chunks: 검색된 청크 리스트

        Returns:
            Dict: 분석된 패턴 정보
        """
        patterns = {
            "has_numbers": False,
            "has_dates": False,
            "has_tables": False,
            "text_length": 0,
            "chunk_count": len(chunks),
            "common_terms": set()
        }

        import re
        from collections import Counter

        all_text = ""
        for chunk in chunks:
            text = chunk.get('text', '')
            all_text += text

            # 숫자 패턴 확인
            if re.search(r'\d+(?:,\d{3})*(?:\.\d+)?', text):
                patterns["has_numbers"] = True

            # 날짜 패턴 확인
            if re.search(r'\d{4}[-/년]\d{1,2}[-/월]\d{1,2}[일]?', text):
                patterns["has_dates"] = True

            # 표 패턴 확인 (|나 표 관련 키워드로 확인)
            if '|' in text or re.search(r'표\s*\d+|테이블|table', text, re.I):
                patterns["has_tables"] = True

        # 전체 텍스트 길이
        patterns["text_length"] = len(all_text)

        # 자주 등장하는 용어 추출
        words = re.findall(r'\w+', all_text)
        common_terms = Counter(words).most_common(5)
        patterns["common_terms"] = [term for term, _ in common_terms]

        return patterns