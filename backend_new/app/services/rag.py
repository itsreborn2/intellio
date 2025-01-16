"""RAG 서비스"""

from typing import Dict, Any, List, Union
from uuid import UUID
import pandas as pd
import logging
from sqlalchemy import select

from app.core.config import settings
from app.services.embedding import EmbeddingService
from app.services.prompt_manager import PromptManager, PromptTemplate
from app.models.document import Document
from app.schemas.table_response import TableHeader, TableCell, TableColumn, TableResponse

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
        self.prompt_manager = PromptManager()
        self.db = None

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

    def _analyze_query(self, query: str) -> Dict[str, Any]:
        """쿼리 분석 - 사용자 질문의 의도와 필요한 정보를 파악
        
        Args:
            query: 사용자 쿼리
            
        Returns:
            Dict: 쿼리 분석 결과
        """
        import re
        import hashlib
        from collections import defaultdict
        
        # 1. 기본 분석 구조
        analysis = {
            "type": "general",      # 쿼리 유형 (일반/숫자/날짜/비교)
            "focus": None,          # 분석 초점 (재무/인사/경영 등)
            "time_range": None,     # 시간 범위
            "metrics": set(),       # 요청된 지표들
            "complexity": "low",    # 복잡도 (낮음/중간/높음)
            "required_context": 3,  # 필요한 컨텍스트 수
            "cache_key": None       # 캐시 키
        }
        
        # 2. 단순 숫자 쿼리 필터링
        if query.strip().isdigit():
            return {
                "type": "invalid",
                "message": "단순 숫자 쿼리는 처리할 수 없습니다."
            }
        
        # 3. 쿼리 정규화 및 캐시 키 생성
        normalized_query = self._normalize_query(query)
        analysis["cache_key"] = hashlib.md5(normalized_query.encode()).hexdigest()
        
        # 4. 재무 지표 분석 (확장)
        financial_terms = {
            # 수익 관련
            "매출": "revenue", "매출액": "revenue", "수입": "revenue",
            "영업이익": "operating_profit", "영업손실": "operating_loss",
            "순이익": "net_profit", "당기순이익": "net_profit",
            
            # 수익성 지표
            "ROE": "roe", "ROIC": "roic", "ROA": "roa",
            "이익률": "profit_ratio", "마진": "margin",
            "영업이익률": "operating_margin", "순이익률": "net_margin",
            
            # 성장성 지표
            "성장률": "growth_rate", "증가율": "increase_rate",
            "신장률": "growth_rate", "확대율": "expansion_rate",
            
            # 비용 관련
            "원가": "cost", "비용": "expense", "지출": "expenditure",
            "판관비": "sga", "인건비": "labor_cost",
            
            # 재무상태 관련
            "부채": "debt", "자산": "asset", "자본": "capital",
            "현금": "cash", "유동성": "liquidity", "재고": "inventory"
        }
        
        for term, metric in financial_terms.items():
            if term in normalized_query:
                analysis["metrics"].add(metric)
                analysis["focus"] = "financial"
        
        # 5. 시간 범위 분석 (개선)
        time_patterns = {
            r'20\d{2}년': 'year',           # 연도
            r'(\d{1,2})월': 'month',        # 월
            r'(\d{1,2})분기': 'quarter',    # 분기
            r'전년\s*대비': 'yoy',          # 전년 대비
            r'전월\s*대비': 'mom',          # 전월 대비
            r'전분기\s*대비': 'qoq',        # 전분기 대비
            r'연간': 'yearly',              # 연간
            r'반기': 'half_year',           # 반기
            r'월간': 'monthly'              # 월간
        }
        
        time_matches = defaultdict(list)
        for pattern, time_type in time_patterns.items():
            matches = re.finditer(pattern, normalized_query)
            time_matches[time_type].extend(m.group() for m in matches)
        
        # 시간 범위 결정
        if time_matches['yoy'] or len(time_matches['year']) > 1:
            analysis["time_range"] = "multi_year"
        elif time_matches['year']:
            analysis["time_range"] = "single_year"
        elif any(time_matches[t] for t in ['month', 'quarter', 'half_year']):
            analysis["time_range"] = "specific_period"
        elif any(time_matches[t] for t in ['yearly', 'monthly']):
            analysis["time_range"] = "periodic"
            
        # 6. 복잡도 분석
        complexity_score = 0
        
        # 길이 기반 점수
        complexity_score += len(normalized_query) > 100 and 3 or (len(normalized_query) > 50 and 2 or 1)
        
        # 문장 수 기반 점수
        sentences = [s for s in normalized_query.split('.') if s.strip()]
        complexity_score += len(sentences) > 2 and 2 or 1
        
        # 조건절 점수
        conditions = ['만약', '경우', '조건', 'if', '때', '어떻게', '어떤']
        complexity_score += sum(1 for c in conditions if c in normalized_query)
        
        # 연산 필요성 점수
        calculations = ['평균', '합계', '총', '증가율', '비율', '차이', '편차', '분포']
        complexity_score += sum(1 for c in calculations if c in normalized_query)
        
        # 복잡도 수준 결정
        analysis["complexity"] = "high" if complexity_score >= 6 else ("medium" if complexity_score >= 3 else "low")
        analysis["required_context"] = {"high": 8, "medium": 5, "low": 3}[analysis["complexity"]]
        
        # 7. 비교 분석 필요 여부 확인 (가중치 기반)
        comparison_patterns = {
            "추세": 0.8,    # 가중치
            "추이": 0.8,
            "변화": 0.7,
            "증가": 0.6,
            "감소": 0.6,
            "대비": 0.9,
            "비교": 1.0,
            "차이": 0.7,
            "어떻게": 0.5,
            "얼마나": 0.5
        }
        
        comparison_score = sum(weight for word, weight in comparison_patterns.items() if word in normalized_query)
        if comparison_score >= 0.8:
            analysis["type"] = "comparison"
            
        # 8. 숫자 데이터 요청 확인
        if re.search(r'(\d+%|[\d,.]+\s*(원|달러|위안|엔|유로|%)|[\d,.]+\s*(억|만|천|조))', normalized_query):
            if analysis["type"] == "general":
                analysis["type"] = "number"
            
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
            
            # 프롬프트 체인으로 분석 (쿼리 분석 결과 추가)
            chain_response = await self.prompt_manager.process_prompt(
                template=PromptTemplate.ANALYSIS,
                context={
                    'query': query,
                    'content': '\n\n'.join(doc_contexts),
                    'patterns': patterns,
                    'query_analysis': query_analysis
                }
            )
            
            return {
                "answer": chain_response,
                "context": relevant_chunks
            }
            
        except Exception as e:
            logger.error(f"채팅 모드 처리 실패: {str(e)}")
            raise

    async def handle_table_mode(self, query: str, document_ids: List[str] = None):
        """테이블 모드 처리"""
        try:
            # 테이블 제목 생성
            title = await self.prompt_manager.process_prompt(
                template=PromptTemplate.TABLE_TITLE,
                context={'query': query}
            )
            
            # 관련 문서 검색
            relevant_chunks, patterns = await self._get_relevant_chunks(query, top_k=5, document_ids=document_ids)
            
            if not relevant_chunks:
                return TableResponse(columns=[
                    TableColumn(
                        header=TableHeader(name=title, prompt=query),
                        cells=[TableCell(doc_id="1", content="관련 문서를 찾을 수 없습니다.")]
                    )
                ])
            
            # 각 문서별로 개별 분석 수행
            analysis_results = []
            for chunk in relevant_chunks:
                if not isinstance(chunk, dict):
                    logger.warning(f"잘못된 청크 형식: {type(chunk)}")
                    continue
                    
                # 문서 분석 수행
                analysis_result = await self.prompt_manager.process_prompt(
                    template=PromptTemplate.TABLE_ANALYSIS,
                    context={
                        'query': query,
                        'content': chunk.get('text', '')
                    }
                )
                
                analysis_results.append({
                    'doc_id': chunk.get('document_id', 'N/A'),
                    'content': analysis_result
                })
            
            # 분석 결과를 테이블 형식으로 변환
            return TableResponse(columns=[
                TableColumn(
                    header=TableHeader(name=title, prompt=query),
                    cells=[
                        TableCell(
                            doc_id=result['doc_id'],
                            content=result['content']
                        )
                        for result in analysis_results
                    ]
                )
            ])
            
        except Exception as e:
            logger.error(f"테이블 모드 처리 실패: {str(e)}", exc_info=True)
            raise

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

    async def _get_relevant_chunks(self, query: str, top_k: int = 5, document_ids: List[str] = None):
        """관련 청크 검색 및 패턴 분석
        
        Args:
            query: 검색 쿼리
            top_k: 검색할 상위 청크 수
            document_ids: 검색할 문서 ID 리스트
            
        Returns:
            Tuple[List, Dict]: 검색된 청크와 패턴 분석 결과
        """
        chunks = await self.embedding_service.search_similar(
            query=query,
            top_k=top_k,
            document_ids=document_ids
        )
        
        patterns = self._analyze_chunk_patterns(chunks)
        
        return chunks, patterns

    async def query(
        self,
        query: str,
        mode: str = "chat",
        document_ids: List[str] = None
    ) -> Union[Dict[str, Any], TableResponse]:
        """쿼리에 대한 응답 생성
        
        Args:
            query: 사용자 쿼리
            mode: 응답 모드 ("chat" 또는 "table")
            document_ids: 테이블 모드에서 사용할 문서 ID 목록
            
        Returns:
            Union[Dict[str, Any], TableResponse]: 모드에 따른 응답
            - chat 모드: {"answer": str, "context": List[Dict]}
            - table 모드: TableResponse 객체
        """
        if mode == "table":
            return await self.handle_table_mode(query, document_ids=document_ids)
        return await self._handle_chat_mode(query, 5, document_ids=document_ids)

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

    def _process_table_response(self, header: str, content: str):
        """테이블 응답 처리"""
        try:
            # 데이터 전처리
            content = self._preprocess_table_content(content)
            
            # 청크 사이즈 계산 (약 8000 토큰)
            chunk_size = 12000
            chunks = [content[i:i + chunk_size] for i in range(0, len(content), chunk_size)]
            
            results = []
            for chunk in chunks:
                try:
                    messages = [
                        {"role": "system", "content": self.prompt_manager.get_system_message(PromptTemplate.TABLE)},
                        {"role": "user", "content": chunk}
                    ]
                    
                    completion = self.prompt_manager.process_prompt(
                        template=PromptTemplate.TABLE,
                        context={
                            'query': header,
                            'content': chunk
                        }
                    )
                    
                    result = completion
                    results.append(result)
                    
                except Exception as e:
                    logger.error(f"테이블 셀 내용 추출 중 오류 발생: {str(e)}")
                    continue
                    
            return {
                "columns": [{"name": header, "key": header}],
                "rows": [{"id": "1", header: "\n".join(results)}]
            }
            
        except Exception as e:
            logger.error(f"테이블 응답 처리 실패: {str(e)}")
            raise

    def _preprocess_table_content(self, content: str) -> str:
        """테이블 내용 전처리"""
        # 연속된 공백 제거
        content = content.replace('\n', ' ')
        content = ' '.join(content.split())
        return content.strip()
