"""RAG 서비스"""

from typing import Dict, Any, List, Union, Tuple
from uuid import UUID
import pandas as pd
import re
from datetime import datetime
import asyncio
from loguru import logger
from app.services.llm import LLMService
from app.services.embedding import EmbeddingService
from app.services.prompts import ChatPrompt, TablePrompt, TableHeaderPrompt
from app.services.chunker import Chunk, ChunkMetadata
from app.core.config import settings
from app.models.document import Document
from app.schemas.table_response import TableHeader, TableCell, TableColumn, TableResponse
from app.schemas.table_history import TableHistoryCreate
from app.services.table_history import TableHistoryService
from collections import defaultdict
from fastapi import HTTPException
from sqlalchemy import select

# logging 설정
logger = logger

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
        self.table_header_prompt = TableHeaderPrompt()
        self.table_prompt = TablePrompt()  # 테이블 분석을 위한 프롬프트 추가
        self.db = None
        # 동시 처리할 최대 문서 수 (rate limit 고려)
        self.max_concurrent = 5
        # 청크 수 관련 설정
        self.chunk_multiplier = 5  # 청크 수 배수
        self.max_chunks_per_doc = 10  # 문서당 최대 청크 수
        
        # 금융/경제 관련 키워드
        self.financial_keywords = [
            # 기업 실적
            "매출", "revenue", "영업이익", "operating profit",
            "순이익", "net profit", "영업손실", "operating loss",
            "적자", "deficit", "흑자", "surplus",
            "이익률", "profit margin", "손익", "profit and loss",
            
            # 재무제표
            "자산", "asset", "부채", "liability",
            "자본", "capital", "현금흐름", "cash flow",
            "부채비율", "debt ratio", "유동비율", "current ratio",
            "자기자본", "equity", "영업현금", "operating cash",
            
            # 주식/증시
            "주가", "stock price", "시가총액", "market cap",
            "주식", "stock", "증시", "stock market",
            "코스피", "kospi", "코스닥", "kosdaq",
            "나스닥", "nasdaq", "다우", "dow jones",
            
            # 투자지표
            "per", "pbr", "eps", "roe",
            "roa", "ebitda", "ebit", "fcf",
            "배당", "dividend", "수익률", "yield",
            "베타", "beta", "알파", "alpha",
            
            # 거래/투자
            "매수", "buy", "매도", "sell",
            "거래량", "trading volume", "거래대금", "trading value",
            "기관", "institution", "외국인", "foreigner",
            "개인", "retail", "투자자", "investor",
            
            # 경제지표
            "gdp", "물가", "inflation", "금리", "interest rate",
            "환율", "exchange rate", "무역수지", "trade balance",
            "경상수지", "current account", "외환보유액", "forex reserve",
            
            # 경제 상황
            "경기", "economy", "불황", "recession",
            "호황", "boom", "침체", "depression",
            "회복", "recovery", "성장", "growth",
            
            # 기업 가치
            "기업가치", "enterprise value", "시장가치", "market value",
            "브랜드가치", "brand value", "무형자산", "intangible asset",
            "영업권", "goodwill", "특허권", "patent right",
            
            # 기업 구조
            "지배구조", "governance", "대주주", "major shareholder",
            "소액주주", "minority shareholder", "경영권", "management right",
            "이사회", "board", "감사", "audit",
            
            # 기업 활동
            "인수합병", "m&a", "분할", "split",
            "상장", "ipo", "증자", "capital increase",
            "감자", "capital reduction", "회사채", "corporate bond"
        ]

        # 법률 관련 키워드
        self.legal_keywords = [
            # 법률 용어
            "법률", "법령", "규정", "법원",
            "판결", "판례", "법률문서", "법률서류",
            "계약", "계약서", "법률관계", "법률문제",
            "법률자문", "법률상담", "법률서비스", "법률지원",
            "법률교육", "법률연구", "법률학", "법학",
            "법학자", "법학연구", "법학교육", "법학서비스",
            "법률정보", "법률자료", "법률데이터", "법률분석",
            "법률보고", "법률보고서", "법률보고서 작성", "법률보고서 제출",
            "법률서류 작성", "법률서류 제출", "법률서류 관리", "법률서류 보관",
            "법률서류 검색", "법률서류 조회", "법률서류 열람", "법률서류 복사",
            "법률서류 전송", "법률서류 수신", "법률서류 저장", "법률서류 삭제",
            "법률서류 관리 시스템", "법률서류 관리 소프트웨어", "법률서류 관리 서비스",
            "법률서류 보관 시스템", "법률서류 보관 소프트웨어", "법률서류 보관 서비스",
            "법률서류 검색 시스템", "법률서류 검색 소프트웨어", "법률서류 검색 서비스",
            "법률서류 열람 시스템", "법률서류 열람 소프트웨어", "법률서류 열람 서비스",
            "법률서류 복사 시스템", "법률서류 복사 소프트웨어", "법률서류 복사 서비스",
            "법률서류 전송 시스템", "법률서류 전송 소프트웨어", "법률서류 전송 서비스",
            "법률서류 수신 시스템", "법률서류 수신 소프트웨어", "법률서류 수신 서비스",
            "법률서류 저장 시스템", "법률서류 저장 소프트웨어", "법률서류 저장 서비스",
            "법률서류 삭제 시스템", "법률서류 삭제 소프트웨어", "법률서류 삭제 서비스",
            "법률서류 관리 시스템 개발", "법률서류 관리 소프트웨어 개발", "법률서류 관리 서비스 개발",
            "법률서류 보관 시스템 개발", "법률서류 보관 소프트웨어 개발", "법률서류 보관 서비스 개발",
            "법률서류 검색 시스템 개발", "법률서류 검색 소프트웨어 개발", "법률서류 검색 서비스 개발",
            "법률서류 열람 시스템 개발", "법률서류 열람 소프트웨어 개발", "법률서류 열람 서비스 개발",
            "법률서류 복사 시스템 개발", "법률서류 복사 소프트웨어 개발", "법률서류 복사 서비스 개발",
            "법률서류 전송 시스템 개발", "법률서류 전송 소프트웨어 개발", "법률서류 전송 서비스 개발",
            "법률서류 수신 시스템 개발", "법률서류 수신 소프트웨어 개발", "법률서류 수신 서비스 개발",
            "법률서류 저장 시스템 개발", "법률서류 저장 소프트웨어 개발", "법률서류 저장 서비스 개발",
            "법률서류 삭제 시스템 개발", "법률서류 삭제 소프트웨어 개발", "법률서류 삭제 서비스 개발",
        ]

        # 기술/IT 관련 키워드
        self.tech_keywords = [
            # 기술 용어
            "기술", "기술개발", "기술연구", "기술교육",
            "기술서비스", "기술지원", "기술컨설팅", "기술컨설팅 서비스",
            "기술교육 서비스", "기술교육 프로그램", "기술교육 과정", "기술교육 자료",
            "기술연구 서비스", "기술연구 프로그램", "기술연구 과정", "기술연구 자료",
            "기술개발 서비스", "기술개발 프로그램", "기술개발 과정", "기술개발 자료",
            "기술지원 서비스", "기술지원 프로그램", "기술지원 과정", "기술지원 자료",
            "기술컨설팅 서비스", "기술컨설팅 프로그램", "기술컨설팅 과정", "기술컨설팅 자료",
            "기술교육 서비스 개발", "기술교육 프로그램 개발", "기술교육 과정 개발", "기술교육 자료 개발",
            "기술연구 서비스 개발", "기술연구 프로그램 개발", "기술연구 과정 개발", "기술연구 자료 개발",
            "기술개발 서비스 개발", "기술개발 프로그램 개발", "기술개발 과정 개발", "기술개발 자료 개발",
            "기술지원 서비스 개발", "기술지원 프로그램 개발", "기술지원 과정 개발", "기술지원 자료 개발",
            "기술컨설팅 서비스 개발", "기술컨설팅 프로그램 개발", "기술컨설팅 과정 개발", "기술컨설팅 자료 개발",
        ]

        # 참가자 관련 키워드
        self.participant_keywords = [
            "참석자", "발표자", "스피커", "참가자", "질문자",
            "패널", "토론자", "사회자", "진행자", "연사",
            "attendee", "speaker", "participant", "questioner",
            "panelist", "moderator", "presenter", "Q&A",
            # 컨퍼런스콜 특화
            "발언자", "대화자", "통화참여자", "컨퍼런스참가자",
            "콜참가자", "미팅참가자"
        ]

        # 테이블 처리 관련 설정
        self.config = {
            'table_chunk_size': 8000,  # 테이블 처리시 청크 크기 (토큰)
            'min_similarity_score': 0.6  # 최소 유사도 점수
        }

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

    def contains_keywords(self, text: str, keywords: List[str]) -> bool:
        """
        주어진 텍스트에 키워드 목록 중 하나라도 포함되어 있는지 확인합니다.
        
        Args:
            text: 검색할 텍스트
            keywords: 키워드 목록
            
        Returns:
            bool: 키워드가 포함되어 있으면 True, 아니면 False
        """
        if not isinstance(text, str):
            text = str(text)
        text = text.lower()
        
        for keyword in keywords:
            if not isinstance(keyword, str):
                keyword = str(keyword)
            if keyword.lower() in text:
                return True
        return False

    def _extract_keywords(self, text: str) -> List[str]:
        """
        텍스트에서 주요 키워드를 추출합니다.
        """
        # 텍스트를 소문자로 변환하고 기본적인 전처리
        text = text.lower()
        
        # 불용어 정의
        stop_words = {'을', '를', '이', '가', '은', '는', '에', '의', '와', '과', '로', '으로'}
        
        # 텍스트를 단어로 분리
        words = text.split()
        
        # 불용어 제거 및 2글자 이상인 단어만 선택
        keywords = [word for word in words if word not in stop_words and len(word) >= 2]
        
        return keywords

    def _filter_chunks_by_query(self, chunks: List[Dict[str, Any]], query: str, query_analysis: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        쿼리와 관련성이 높은 청크만 필터링합니다.
        
        Args:
            chunks: 필터링할 청크 목록
            query: 사용자 쿼리
            query_analysis: 쿼리 분석 결과 (선택사항)
        """
        if not chunks:
            logger.warning("필터링할 청크가 없습니다.")
            return []

        filtered_chunks = []
        min_score = self.config.get('min_similarity_score', 0.6)
        
        for chunk in chunks:
            # 청크 메타데이터에서 텍스트 추출
            metadata = chunk.get("metadata", {})
            content = metadata.get("text", "")
            
            if not content:
                logger.warning(f"청크 {chunk.get('id', 'unknown')}에서 텍스트를 찾을 수 없음")
                continue

            # 청크 점수 계산 (Pinecone 유사도 점수)
            similarity_score = chunk.get("score", 0)
            if similarity_score < min_score:
                continue

            # 쿼리 분석 결과가 있는 경우 추가 필터링
            if query_analysis:
                query_type = query_analysis.get("query_type", "general")
                if query_type != "general":
                    # 특정 타입의 쿼리에 대한 추가 처리 로직
                    pass

            # 최종 점수는 유사도 점수 사용
            chunk["score"] = similarity_score

            # 최소 점수 임계값을 넘는 경우만 포함
            if similarity_score >= min_score:
                filtered_chunks.append(chunk)
                logger.debug(f"청크 {chunk.get('id')} 선택됨 - 점수: {similarity_score:.2f}")

        # 점수 기준으로 정렬
        filtered_chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        return filtered_chunks

    async def _get_relevant_chunks(self, query: str, top_k: int = 5, document_ids: List[UUID] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """관련 문서 청크 검색 및 패턴 분석"""
        logger.info(f"청크 검색 시작 - 쿼리: {query}, top_k: {top_k}")
        if document_ids:
            logger.info(f"검색 대상 문서 ID: {document_ids}")
            # UUID를 문자열로 변환
            doc_ids_str = [str(doc_id) for doc_id in document_ids]
        
        # 쿼리 정규화
        normalized_query = self._normalize_query(query)
        logger.info(f"정규화된 쿼리: {normalized_query}")
        
        try:
            # 문서 검색
            all_chunks = await self.embedding_service.search_similar(
                query=normalized_query,
                document_ids=doc_ids_str if document_ids else None,
                top_k=top_k
            )
            
            logger.info(f"검색된 총 청크 수: {len(all_chunks)}")
            
            # 쿼리 분석
            query_analysis = self._analyze_query(query)
            
            # 청크 필터링
            if all_chunks:
                filtered_chunks = self._filter_chunks_by_query(all_chunks, query, query_analysis)
                logger.info(f"필터링 후 청크 수: {len(filtered_chunks)}")
            else:
                logger.warning("검색된 청크가 없습니다.")
                filtered_chunks = []
                
            return filtered_chunks, query_analysis
            
        except Exception as e:
            logger.error(f"청크 검색 중 오류 발생: {str(e)}")
            return [], {}

    async def handle_table_mode(self, query: str, document_ids: List[UUID] = None, user_id: str = None, project_id: str = None) -> TableResponse:
        """테이블 모드 처리"""
        try:
            # 테이블 제목 생성
            title = await self.table_header_prompt.generate_title(query)
            logger.info("테이블 헤더 생성 완료")

            # 관련 청크 검색
            relevant_chunks, query_analysis = await self._get_relevant_chunks(query, document_ids=document_ids)
            logger.info(f"관련 청크 검색 완료 - 총 {len(relevant_chunks)}개 청크 발견")

            if not relevant_chunks:
                return TableResponse(columns=[
                    TableColumn(
                        header=TableHeader(name=title, prompt=query),
                        cells=[TableCell(doc_id="1", content="관련 문서를 찾을 수 없습니다.")]
                    )
                ])

            # 문서별로 청크 그룹화 및 키워드 추출
            docs_data = {}
            for chunk in relevant_chunks:
                # 디버그 로깅 추가
                logger.debug(f"청크 데이터: {chunk}")
                
                doc_id = chunk["metadata"].get("document_id")
                if doc_id:
                    # chunk["text"] 대신 chunk["metadata"]["text"] 사용
                    chunk_text = chunk["metadata"].get("text", "")
                    if doc_id not in docs_data:
                        docs_data[doc_id] = {
                            "content": chunk_text,
                            "keywords": self._extract_keywords(chunk_text)
                        }
                    else:
                        docs_data[doc_id]["content"] += "\n" + chunk_text
                        # 키워드 업데이트
                        new_keywords = self._extract_keywords(chunk_text)
                        docs_data[doc_id]["keywords"].extend(new_keywords)

            # 각 문서별로 테이블 분석 수행
            columns = []
            for doc_id, data in docs_data.items():
                # 키워드 추출 및 딕셔너리로 변환
                keywords = self._extract_keywords(data["content"])
                keywords_dict = {
                    "keywords": keywords,
                    "type": "extracted",
                    "source": "document_content"
                }
                
                # 테이블 분석 수행
                analysis_result = await self.table_prompt.analyze(
                    content=data["content"],
                    query=query,
                    keywords=keywords_dict,
                    query_analysis=query_analysis
                )
                
                # 분석 결과에서 content 필드만 추출
                result_content = (
                    analysis_result["content"] 
                    if isinstance(analysis_result, dict) and "content" in analysis_result 
                    else str(analysis_result)
                )
                
                # 셀 추가
                columns.append(TableColumn(
                    header=TableHeader(name=title, prompt=query),
                    cells=[TableCell(doc_id=doc_id, content=result_content)]
                ))

            # 히스토리 저장
            if user_id and project_id:
                try:
                    history_service = TableHistoryService(self.db)
                    await history_service.create_many([
                        TableHistoryCreate(
                            project_id=UUID(project_id),
                            document_id=UUID(cell.doc_id),
                            user_id=UUID(user_id),
                            prompt=query,
                            title=title,
                            result=str(cell.content)
                        ) for column in columns for cell in column.cells
                    ])
                except Exception as e:
                    logger.error(f"히스토리 저장 실패: {str(e)}")

            return TableResponse(columns=columns)

        except Exception as e:
            logger.error(f"테이블 모드 처리 실패: {str(e)}")
            raise

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
            # UUID로 변환하여 전달
            doc_ids = [UUID(doc_id) for doc_id in document_ids]
            return await self.handle_table_mode(
                query=query,
                document_ids=doc_ids,
                user_id=user_id,
                project_id=project_id
            )
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

    async def _process_table_response(self, content: str, query: str, keywords: List[str], query_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """테이블 응답 처리
        
        Args:
            content: 분석할 내용
            query: 사용자 질문
            keywords: 발견된 패턴 목록
            query_analysis: 쿼리 분석 결과
            
        Returns:
            Dict[str, Any]: 분석 결과
        """
        try:
            # 데이터 전처리
            content = self._preprocess_table_content(content)
            
            # 설정에서 청크 사이즈 가져오기 (기본값: 8000 토큰)
            chunk_size = self.config.get('table_chunk_size', 8000)
            
            # 토큰 길이를 문자 길이로 대략 변환 (1토큰 ≈ 1.5 characters)
            char_chunk_size = int(chunk_size * 1.5)
            
            # 컨텐츠를 청크로 분할
            chunks = [content[i:i + char_chunk_size] for i in range(0, len(content), char_chunk_size)]
            
            all_rows = []
            for chunk in chunks:
                try:
                    result = await self.table_header_prompt.analyze(
                        content=chunk,
                        query=query,
                        keywords=keywords,
                        query_analysis=query_analysis
                    )
                    
                    if isinstance(result, dict) and 'rows' in result:
                        all_rows.extend(result['rows'])
                        
                except Exception as e:
                    logger.error(f"테이블 셀 내용 추출 중 오류 발생: {str(e)}")
                    continue
            
            return {'rows': all_rows}
            
        except Exception as e:
            logger.error(f"테이블 응답 처리 실패: {str(e)}")
            raise

    def _preprocess_table_content(self, content: str) -> str:
        """테이블 내용 전처리
        
        Args:
            content: 원본 문서 내용
            
        Returns:
            str: 전처리된 문서 내용
        """
        # 연속된 공백 제거
        content = content.replace('\n', ' ')
        content = ' '.join(content.split())
        return content.strip()

    def _analyze_query(self, query: str) -> Dict[str, Any]:
        """쿼리 분석
        
        Args:
            query: 사용자 질문
            
        Returns:
            Dict[str, Any]: 분석 결과
        """
        # 쿼리가 문자열이 아닌 경우 문자열로 변환
        if not isinstance(query, str):
            query = str(query)
            
        # 쿼리를 소문자로 변환
        query_lower = query.lower()
            
        analysis = {
            "query": query_lower,        # 원본 쿼리 (소문자)
            "length": len(query),        # 쿼리 길이
            "word_count": len(query.split()),  # 단어 수
            "has_numbers": bool(re.search(r'\d', query)),  # 숫자 포함 여부
            "has_special_chars": bool(re.search(r'[^\w\s]', query)),  # 특수문자 포함 여부
            "timestamp": datetime.now().isoformat(),  # 분석 시간
            "focus_area": self._get_query_focus(query_lower),  # 쿼리 초점 영역
            "doc_type": self._get_doc_type(query_lower)  # 문서 타입 추론
        }
        
        return analysis
        
    def _get_query_focus(self, query: str) -> str:
        """쿼리 초점 영역 분석
        
        Args:
            query: 소문자로 변환된 쿼리
            
        Returns:
            str: 쿼리 초점 영역
        """
        # 정규표현식 패턴 정의
        patterns = {
            'meeting': r'회의|미팅|발표|토론|컨퍼런스|세미나|워크샵|브리핑|인터뷰',
            'report': r'보고서|리포트|분석|결과|평가|검토|조사|연구|데이터',
            'contract': r'계약|협약|약관|동의서|합의서|규정|조항|법률|계약서',
            'financial_statement': r'재무|회계|재표|손익|자산|부채|자본|현금흐름|매출',
            'investment': r'투자|수익률|성장률|밸류에이션|PER|ROE|배당|주가|시가총액',
            'risk': r'리스크|위험|평가|등급|변동성|안정성|취약성|대응',
            'industry': r'산업|시장|경쟁|점유율|원가|마진|효율성|경기|규제',
            'esg': r'ESG|환경|사회|지배구조|탄소|에너지|고용|이사회|주주',
            'financial_metric': r'지표|메트릭|스코어|품질|검증|일관성|추세|상관관계|회귀',
            'hr': r'인사|채용|직원|급여|복리후생|교육|훈련|평가|인력',
            'tech': r'기술|개발|시스템|프로그램|소프트웨어|하드웨어|네트워크|데이터베이스'
        }
        
        # 각 패턴에 대해 매칭 확인
        matches = {}
        for focus, pattern in patterns.items():
            count = len(re.findall(pattern, query))
            if count > 0:
                matches[focus] = count
                
        # 가장 많이 매칭된 패턴 반환
        if matches:
            return max(matches.items(), key=lambda x: x[1])[0]
                
        return "general"
        
    def _get_doc_type(self, query: str) -> str:
        """문서 타입 추론
        
        Args:
            query: 소문자로 변환된 쿼리
            
        Returns:
            str: 추론된 문서 타입
        """
        # 정규표현식 패턴 정의
        patterns = {
            'dialogue': r'말씀|이야기|대화|토론|인터뷰|면담|상담|회의록|의견',
            'numeric': r'금액|수치|통계|퍼센트|그래프|차트|데이터|수량|측정',
            'temporal': r'날짜|기간|일정|시간|연도|월|주|요일|분기',
            'legal': r'법률|계약|규정|조항|약관|정책|지침|가이드라인',
            'technical': r'사양|스펙|기술|시스템|프로그램|코드|알고리즘|프로토콜',
            'personal': r'이력서|프로필|신상|개인정보|자기소개|경력|학력|자격',
            'financial_report': r'재무|회계|재표|손익|자산|부채|자본|현금흐름|매출',
            'market_analysis': r'시장|산업|경쟁|점유율|트렌드|성장성|전망|예측',
            'risk_assessment': r'리스크|위험|평가|등급|변동성|안정성|취약성|대응',
            'performance': r'성과|실적|달성|목표|KPI|효율|생산성|품질'
        }
        
        # 복합 타입 처리를 위한 가중치 계산
        type_weights = defaultdict(int)
        
        for doc_type, pattern in patterns.items():
            matches = len(re.findall(pattern, query))
            if matches > 0:
                type_weights[doc_type] = matches
                
        # 가장 높은 가중치를 가진 타입 반환
        if type_weights:
            return max(type_weights.items(), key=lambda x: x[1])[0]
                
        return "general"