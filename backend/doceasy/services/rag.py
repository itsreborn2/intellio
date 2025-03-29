"""RAG 서비스"""

from typing import Dict, Any, List, Union, Tuple, Optional, Callable
from uuid import UUID

import re
from datetime import datetime
import asyncio
import time
import json
from loguru import logger
from requests import Session as RequestsSession
from common.services.vector_store_manager import VectorStoreManager
from common.core.config import settings
from common.services.retrievers.tablemode_semantic import TableModeSemanticRetriever
from common.services.embedding import EmbeddingService
from doceasy.services.prompts import ChatPrompt, TablePrompt, TableHeaderPrompt

from doceasy.models.document import Document
from doceasy.schemas.table_response import TableHeader, TableCell, TableColumn, TableResponse
from doceasy.schemas.table_history import TableHistoryCreate
from doceasy.services.table_history import TableHistoryService
from collections import defaultdict
from sqlalchemy import select
from common.utils.util import measure_time_async
from doceasy.workers.rag import analyze_table_mode_task
from celery import group
from common.models.user import Session
from common.models.token_usage import ProjectType

from common.services.retrievers.semantic import SemanticRetriever, SemanticRetrieverConfig
from common.services.retrievers.models import DocumentWithScore, RetrievalResult
from common.services.retrievers.hybrid import HybridRetriever, HybridRetrieverConfig, ContextualBM25Config
from common.services.retrievers.contextual_bm25 import ContextualBM25Retriever, ContextualBM25Config

# logging 설정


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
        
        
        self.db = None
        self.session = None  # 세션 정보 추가
        
        self._should_stop = False  # 생성 중지 플래그 추가
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

    async def initialize(self, db, session: Optional[Session] = None, streaming_callback: Optional[Callable[[str], None]] = None):
        """DB 세션 및 유저 세션 초기화"""
        self.db = db
        self.session = session
        
        if session:
            logger.info(f"RAG 서비스 세션 정보 설정: user_id={session.user_id}, user_email={session.user_email}")
        
        if streaming_callback:
            logger.warning(f"RAG Init with callback")
            self.chat_prompt = ChatPrompt(session=session, streaming_callback=streaming_callback)
            self.set_streaming_callback(streaming_callback)
        else:
            logger.warning(f"RAG Init without callback")
            self.chat_prompt = ChatPrompt(session=session)
        self._streaming_callback = streaming_callback
        
        self.table_header_prompt = TableHeaderPrompt(session=session)
        self.table_prompt = TablePrompt(session=session)  # 테이블 분석을 위한 프롬프트 추가

    async def set_streaming_callback(self, streaming_callback: Optional[Callable[[str], None]] = None):
        """스트리밍 콜백 설정"""
        if self._streaming_callback is None:
            logger.warning(f"RAG set_streaming_callback")
            self._streaming_callback = streaming_callback
            self.chat_prompt.LLM.set_streaming_callback(streaming_callback=streaming_callback)
        else:
            logger.warning(f"RAG set_streaming_callback already set")

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
    
    async def _get_first_chunks_parallel(self, doc_ids: List[str]) -> List[Dict[str, Any]]:
        """여러 문서의 첫 번째 청크 병렬 검색
        
        EmbeddingService를 통하지 않고 VectorStoreManager를 직접 사용하여 
        문서의 첫 번째 청크를 효율적으로 병렬 검색합니다.
        
        Args:
            doc_ids: 문서 ID 목록
            
        Returns:
            List[Dict[str, Any]]: 각 문서의 첫 번째 청크 정보
        """
        if not doc_ids:
            logger.warning("검색할 문서 ID가 없습니다")
            return []
            
        logger.info(f"문서 {len(doc_ids)}개의 첫 번째 청크 병렬 검색 시작")
        start_time = time.time()
        
        # VectorStoreManager 인스턴스 생성
        vs_manager = VectorStoreManager(
            embedding_model_type=self.embedding_service.get_model_type(),
            project_name=ProjectType.DOCEASY,
            namespace=settings.PINECONE_NAMESPACE_DOCEASY
        )
        
        # 각 문서에 대한 첫 번째 청크 검색 작업 비동기 생성
        async def get_first_chunk(doc_id: str) -> Dict[str, Any]:
            try:
                # VS Manager 초기화 확인
                await vs_manager.ensure_initialized()
                
                # 임베딩 모델의 차원 정보 가져오기
                dimension = self.embedding_service.current_model_config.dimension
                
                # 청크 인덱스가 0인 청크 검색 시도 (metadata 접두어 없이 필터 지정)
                filters = {"document_id": doc_id, "chunk_index": 0}
                query_response = await vs_manager.query_async(
                    vector=[0.0] * dimension,  # 더미 벡터
                    top_k=1,
                    filters=filters
                )
                
                # 첫 번째 청크가 없으면 페이지 번호가 1인 청크 검색
                if not query_response.matches:
                    filters = {"document_id": doc_id, "page_number": 1}
                    query_response = await vs_manager.query_async(
                        vector=[0.0] * dimension,
                        top_k=1,
                        filters=filters
                    )
                
                # 결과가 있으면 포맷팅하여 반환
                if query_response.matches:
                    match = query_response.matches[0]
                    return {
                        "id": match.id,
                        "score": 0.9,  # 첫 번째 청크이므로 높은 점수 부여
                        "metadata": match.metadata
                    }
                
                logger.warning(f"문서 {doc_id}의 첫 번째 청크를 찾을 수 없음")
                return None
                
            except Exception as e:
                logger.error(f"문서 {doc_id}의 첫 번째 청크 검색 중 오류: {str(e)}")
                return None
        
        # 병렬로 작업 실행
        tasks = [get_first_chunk(doc_id) for doc_id in doc_ids]
        chunks = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 유효한 청크만 필터링
        valid_chunks = []
        for doc_id, chunk in zip(doc_ids, chunks):
            if isinstance(chunk, Exception):
                logger.error(f"문서 {doc_id}의 첫 번째 청크 검색 실패: {str(chunk)}")
            elif chunk:
                valid_chunks.append(chunk)
                logger.debug(f"문서 {doc_id}의 첫 번째 청크 검색 성공")
            else:
                logger.warning(f"문서 {doc_id}의 첫 번째 청크가 없습니다")
                
        end_time = time.time()
        logger.info(f"첫 번째 청크 검색 완료: {len(valid_chunks)}/{len(doc_ids)} ({end_time - start_time:.2f}초)")
        
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

    def _sort_chunks_by_score(self, chunks: List[Dict[str, Any]], query: str, query_analysis: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """쿼리와 관련된 청크 정렬. 필터링은 이미 search_similar 함수에서 수행됨.

        Args:
            chunks: 검색된 청크 리스트
            query: 사용자 쿼리
            query_analysis: 쿼리 분석 결과

        Returns:
            List[Dict[str, Any]]: 필터링된 청크 리스트
        """
        # 쿼리 타입 확인
        query_type = query_analysis.get("query_type", "general") if query_analysis else "general"
        
        # 테이블 모드인 경우 모든 청크 반환
        if query_type == "table":
            logger.info("테이블 모드: 모든 청크 포함")
            for chunk in chunks:
                chunk["score"] = chunk.get("score", 0)  # 점수가 없는 경우 0으로 설정
            return sorted(chunks, key=lambda x: x.get("score", 0), reverse=True)
        
        # 이미 similarity_score 로 필터링 되어있음.
        # 일반 모드에서는 필터링 수행
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
            
            # 최소 점수보다 낮은 경우 제외
            if similarity_score < min_score:
                continue

            # 최종 점수 설정
            chunk["score"] = similarity_score
            filtered_chunks.append(chunk)
            logger.debug(f"청크 {chunk.get('id')} 선택됨 - 점수: {similarity_score:.2f}")


        filtered_chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        return filtered_chunks

    @measure_time_async
    async def process_retrival(self, query: str, query_analysis: Dict[str, Any] = None, top_k: int = 5, document_ids: List[str] = None, query_type:str = "chat", user_id: str = None) -> RetrievalResult:
        """관련 문서 청크 검색 및 패턴 분석"""
        # 쿼리 정규화
        normalized_query = self._normalize_query(query)
        logger.info(f"청크 검색 시작 - 쿼리: {normalized_query}, top_k: {top_k}")
        
        try:
            logger.info(f"검색할 문서별 청크 수: {top_k * 1}")
            
            # 쿼리 분석
            #query_analysis = self._analyze_query(normalized_query)
            query_intent = query_analysis.get("intent", "general")
            
            # 문서 검색
            #all_chunks = await self.embedding_service.search_similar(
            #     query=normalized_query,
            #     document_ids=doc_ids_str if doc_ids_str else None,
            #     top_k=search_top_k
            # )
            
            filtersMetadata = { "document_id": {"$in": document_ids} } if document_ids else None
            
            vs_manager = VectorStoreManager(embedding_model_type=self.embedding_service.get_model_type(),
                                            project_name=ProjectType.DOCEASY,
                                            namespace=settings.PINECONE_NAMESPACE_DOCEASY)

            # 요약 관련 쿼리인지 확인
            is_summary_query = query_intent == "summary"
            
            # 검색 전략 조정
            min_score = 0.15 if is_summary_query else 0.22  # 요약 쿼리면 더 낮은 임계값 사용
            

            if query_type == "table":
                # 테이블 모드에서넌 top-k가 문서의 숫자의 5배로 넘어온다.
                # 문서 20개면 k=100
                tablemode_retriever = TableModeSemanticRetriever(config=SemanticRetrieverConfig(
                                                                min_score=min_score,
                                                                user_id=user_id,
                                                                project_type=ProjectType.DOCEASY
                                                                ), vs_manager=vs_manager)
                all_chunks:RetrievalResult = await tablemode_retriever.retrieve(
                    query=normalized_query, 
                    top_k=top_k,
                    filters=filtersMetadata
                )
            else:
                if is_summary_query:
                    logger.warning(f"요약 의도 감지: '{normalized_query}' - min_score를 {min_score}로 설정")
                    # 요약 쿼리의 경우 검색 범위 확대
                    top_k = max(top_k * 3, 15)  # 최소 15개 이상 결과 확보 (기존 2배에서 3배로 증가)
                    logger.warning(f"요약 쿼리를 위해 top_k를 {top_k}로 증가")
                #Chat Mode
                semantic_retriever = SemanticRetriever(config=SemanticRetrieverConfig(
                                                        min_score=min_score,
                                                        user_id=user_id,
                                                        project_type=ProjectType.DOCEASY
                                                        ), vs_manager=vs_manager)
                
                # 기본 시맨틱 검색 (벡터 검색)
                all_chunks:RetrievalResult = await semantic_retriever.retrieve(
                    query=normalized_query, 
                    top_k=top_k,
                    filters=filtersMetadata
                )
                
                # # 벡터-BM25 순차 검색 (새로운 방식) - 실험 중이므로 주석 처리
                # hybrid_config = HybridRetrieverConfig(
                #     semantic_config=SemanticRetrieverConfig(
                #         min_score=min_score,
                #         user_id=user_id, 
                #         project_type=ProjectType.DOCEASY
                #     ),
                #     contextual_bm25_config=ContextualBM25Config(
                #         min_score=0.3,
                #         bm25_weight=0.6,
                #         context_weight=0.4,
                #         context_window_size=3,
                #         user_id=user_id,
                #         project_type=ProjectType.DOCEASY
                #     ),
                #     semantic_weight=0.6,
                #     contextual_bm25_weight=0.4,
                #     vector_weight=0.7,
                #     keyword_weight=0.3,
                #     vector_multiplier=3,
                #     user_id=user_id,
                #     project_type=ProjectType.DOCEASY
                # )
                # hybrid_retriever = HybridRetriever(config=hybrid_config, vs_manager=vs_manager)
                # all_chunks = await hybrid_retriever.retrieve_vector_then_bm25(
                #     query=normalized_query, 
                #     top_k=top_k,
                #     filters=filtersMetadata
                # )
                
                # # 기존 병렬 하이브리드 검색 방식 (현재 주석 처리됨)
                # hybrid_config = HybridRetrieverConfig(
                #     semantic_config=SemanticRetrieverConfig(min_score=0.6),
                #     contextual_bm25_config=ContextualBM25Config(
                #         min_score=0.3,
                #         bm25_weight=0.6,
                #         context_weight=0.4,
                #         context_window_size=3
                #     ),
                #     semantic_weight=0.6,
                #     contextual_bm25_weight=0.4
                # )
                # hybrid_retriever = HybridRetriever(config=hybrid_config, vs_manager=vs_manager)
                # hybrid_retriever.contextual_bm25_retriever.db = self.db  # db 세션 전달
                
                # all_chunks = await hybrid_retriever.retrieve(
                #     query=normalized_query, 
                #     top_k=top_k,
                #     filters=filtersMetadata
                # )
                # 요약 쿼리이고 결과가 부족한 경우
                if is_summary_query and document_ids:
                    # 모든 문서의 첫 번째 청크 가져오기 (충분한 청크가 있더라도 문서의 시작 부분은 중요)
                    logger.warning(f"요약 쿼리에 대해 각 문서의 첫 번째 청크를 추가로 가져옵니다.")
                    
                    # 각 문서의 첫 청크도 가져오기 시도
                    first_chunks = await self._get_first_chunks_parallel(document_ids)
                    
                    if first_chunks:
                        # 중복 제거를 위해 이미 가져온 청크 ID 추적
                        existing_ids = {doc.metadata.get("chunk_id", doc.metadata.get("id", "")) 
                                       for doc in all_chunks.documents 
                                       if doc.metadata.get("chunk_id") or doc.metadata.get("id")}
                        
                        # 중복되지 않은 첫 청크만 추가
                        chunks_added = 0
                        for chunk in first_chunks:
                            chunk_id = chunk.get("id")
                            if not chunk_id or chunk_id in existing_ids:
                                continue
                                
                            # first_chunk를 DocumentWithScore로 변환
                            metadata = chunk.get("metadata", {})
                            content = metadata.get("text", "")
                            
                            if not content:
                                continue
                                
                            document = DocumentWithScore(
                                page_content=content,
                                metadata=metadata,
                                score=chunk.get("score", 0.9)  # 첫 번째 청크는 높은 점수 부여
                            )
                            all_chunks.documents.append(document)
                            existing_ids.add(chunk_id)
                            chunks_added += 1
                        
                        if chunks_added > 0:
                            logger.warning(f"요약을 위해 {chunks_added}개의 첫 번째 청크가 추가되었습니다.")
                        else:
                            logger.warning("추가 가능한 첫 번째 청크가 없습니다.")
                    else:
                        logger.warning("문서의 첫 번째 청크를 찾을 수 없습니다.")

            # 상위 3개의 문서 텍스트 출력
            for idx, doc in enumerate(all_chunks.documents[:3], start=1):
                logger.warning(f"문서 #{idx}")
                score_str = f"{doc.score:.4f}" if doc.score is not None else "0.0000"
                logger.warning(f"- 유사도 점수: {score_str}")
                logger.warning(f"- 메타데이터: {json.dumps(doc.metadata, ensure_ascii=False)}")
                logger.warning(f"- 내용: {doc.page_content[:100]}...")
            logger.info(f"검색된 총 청크 수: {len(all_chunks.documents)}")
            
            return all_chunks
        except Exception as e:
            
            error_msg = str(e)
            logger.exception(f"청크 검색 중 오류 발생: {error_msg}", exc_info=True)
            
            # 상세한 오류 메시지
            if "insufficient_quota" in error_msg:
                user_msg = "시스템 사용량이 많아 잠시 후 다시 시도해주세요."
            elif "rate_limit" in error_msg:
                user_msg = "요청이 너무 많습니다. 잠시 후 다시 시도해주세요."
            elif "connection" in error_msg.lower():
                user_msg = "서버 연결에 실패했습니다. 네트워크 상태를 확인해주세요."
            else:
                user_msg = f"문서 검색 중 오류가 발생했습니다: {error_msg}"
            
            return [{"error": user_msg}], {}
    
    @measure_time_async
    async def handle_table_mode(self, query: str, document_ids: List[str] = None, user_id: str = None, project_id: str = None) -> TableResponse:
        """테이블 모드로 문서 처리
        
        아직 기존 문서의 쿼리 처리와 동일하게 동작 - 평문형 문서와 동일하게 청크로 나누어 조회
        
        Args:
            query: 분석 요청
            document_ids: 문서 ID 목록 (선택사항) - 지정하지 않으면 모든 문서 대상
            user_id: 사용자 ID (선택사항)
            project_id: 프로젝트 ID (선택사항)
            
        Returns:
            TableResponse: 테이블 응답
        """
        try:
            # 시작 로깅
            logger.info(f"[테이블 모드] 시작: query={query}, docs={document_ids}")
            
            # 쿼리 및 키워드 분석
            query_clean = self._normalize_query(query)  # 정규화된 쿼리
            response = TableResponse()
            
            # 쿼리 의도 분석
            query_analysis = self._analyze_query(query_clean)
            
            # 키워드 추출
            keywords = self._extract_keywords(query_clean)
            keywords_dict = {"type": "extracted", "source": "query", "keywords": [{"text": k, "frequency": 1} for k in keywords]}
            
            # 타임아웃 시간 계산 (문서당 최대 5초, 최소 10초, 최대 60초)
            doc_count = len(document_ids) if document_ids else 10
            timeout_seconds = min(60, max(10, doc_count * 5))
            logger.info(f"[테이블 모드] 타임아웃 설정: {timeout_seconds}초 (문서 {doc_count}개)")
            
            # 첫 번째 청크 가져오기
            doc_chunks = await self._get_first_chunks_parallel(document_ids)
            chunk_count = len(doc_chunks)
            
            if not doc_chunks:
                response.add_error("분석할 문서를 찾을 수 없습니다.")
                return response
            
            # 테이블 분석 실행
            all_tasks = []
            completed_count = 0
            
            # 진행 상황 업데이트
            response.add_progress(0, f"테이블 분석 작업 시작: {chunk_count}개의 테이블 분석 예정")
            
            # 동시 실행할 작업 수 조절
            concurrent_tasks = min(3, chunk_count)
            logger.info(f"[테이블 모드] 분석 작업 생성: 동시성={concurrent_tasks}, 청크={chunk_count}개")
            
            # 셀러리 태스크 큐
            from doceasy.workers.rag import analyze_table_mode_task
            
            for i, chunk in enumerate(doc_chunks):
                chunk_id = chunk.get("id", f"chunk_{i}")
                doc_id = chunk.get("document_id", "unknown")
                content = chunk.get("content", "")
                
                # 작업 진행 메시지
                progress_msg = f"테이블 분석 작업 {i+1}/{chunk_count} 시작: 문서 ID {doc_id}의 테이블 분석 중"
                response.add_progress(int((i / chunk_count) * 50), progress_msg)
                
                # 비동기 작업 생성
                try:
                    # 셀러리 태스크 호출 (비동기)
                    # 여러 인자를 전달할 때는 순서대로 나열 (user_id가 맨 앞으로)
                    task = analyze_table_mode_task.delay(user_id, content, query_clean, keywords_dict, query_analysis)
                    
                    # 작업 추적용 정보 저장
                    task_info = {
                        "task": task,
                        "task_id": task.id,
                        "chunk_id": chunk_id,
                        "doc_id": doc_id,
                        "content": content[:100] + "..." if len(content) > 100 else content
                    }
                    all_tasks.append(task_info)
                    
                    logger.info(f"[테이블 모드] 작업 생성 완료: task_id={task.id}, chunk_id={chunk_id}")
                except Exception as e:
                    # 작업 생성 실패
                    logger.error(f"[테이블 모드] 작업 생성 실패: {str(e)}")
                    response.add_error(f"문서 ID {doc_id}의 테이블 분석 작업 생성 실패: {str(e)}")
            
            # 작업 처리 완료 대기
            logger.info(f"[테이블 모드] 모든 작업 생성 완료, 결과 대기 중...")
            start_time = time()
            
            # 모든 작업의 결과 수집
            for task_info in all_tasks:
                try:
                    task = task_info["task"]
                    doc_id = task_info["doc_id"]
                    chunk_id = task_info["chunk_id"]
                    
                    # 작업 완료 대기 (타임아웃 적용)
                    elapsed = time() - start_time
                    remaining = max(1, timeout_seconds - elapsed)  # 최소 1초
                    
                    logger.info(f"[테이블 모드] 작업 결과 대기: task_id={task.id}, 남은 시간={remaining:.1f}초")
                    
                    try:
                        # 작업 결과 가져오기 (타임아웃 적용)
                        result = task.get(timeout=remaining)
                        completed_count += 1
                        
                        # 진행률 업데이트
                        progress = 50 + int((completed_count / chunk_count) * 50)
                        response.add_progress(
                            progress, 
                            f"테이블 분석 {completed_count}/{chunk_count} 완료: 문서 ID {doc_id}의 분석 결과 수신"
                        )
                        
                        # 결과 추가
                        if result:
                            response.add_result(chunk_id, doc_id, result)
                            logger.info(f"[테이블 모드] 작업 결과 수신: task_id={task.id}, 길이={len(result)}")
                        else:
                            logger.warning(f"[테이블 모드] 작업 결과 없음: task_id={task.id}")
                    
                    except TimeoutError:
                        # 타임아웃 발생
                        logger.warning(f"[테이블 모드] 작업 타임아웃: task_id={task.id}")
                        response.add_error(f"문서 ID {doc_id}의 테이블 분석 시간 초과")
                        task.revoke(terminate=True)  # 작업 강제 종료
                        
                except Exception as e:
                    # 작업 처리 중 오류
                    logger.error(f"[테이블 모드] 작업 처리 오류: {str(e)}")
                    response.add_error(f"테이블 분석 작업 처리 중 오류 발생: {str(e)}")
            
            # 최종 메시지
            if completed_count > 0:
                response.add_completion("테이블 분석 완료")
            else:
                response.add_error("모든 테이블 분석 작업이 실패했습니다.")
            
            # 총 소요 시간
            total_time = time() - start_time
            logger.info(f"[테이블 모드] 모든 작업 완료: 총 {completed_count}/{chunk_count} 완료, 소요 시간={total_time:.1f}초")
            
            return response
            
        except Exception as e:
            # 전체 처리 오류
            logger.error(f"[테이블 모드] 처리 오류: {str(e)}")
            response = TableResponse()
            response.add_error(f"테이블 분석 중 오류 발생: {str(e)}")
            return response

    async def handle_table_mode_stream(self, query: str, document_ids: List[str] = None, user_id: str = None, project_id: str = None):
        """테이블 모드 처리 (스트리밍 방식)"""
        try:
            logger.warning("테이블 모드 스트리밍 처리 시작")
            
            # 세션에서 사용자 정보 활용
            if self.session and not user_id:
                user_id = str(self.session.user_id) if self.session.user_id else None
                logger.info(f"테이블 모드 스트리밍에서 세션 사용자 정보 활용: user_id={user_id}")
                
            # 테이블 헤더 생성
            title = await self.table_header_prompt.generate_title(query)
            logger.warning(f"테이블 헤더 생성 완료 : {title}")
            
            # 헤더 정보 이벤트 전송
            yield {
                "event": "header",
                "data": {
                    "header_name": title,
                    "prompt": query
                }
            }
            
            # 쿼리 분석
            query_analysis = self._analyze_query(query)
            
            # 관련 청크 검색
            k = len(document_ids) * 5  # 문서당 5개
            # yield {
            #     "event": "progress",
            #     "data": {
            #         "message": "문서에서 관련 정보를 검색 중입니다...",
            #         "progress": 10
            #     }
            # }
            
            rr: RetrievalResult = await self.process_retrival(query=query, 
                                                              query_analysis=query_analysis,
                                                              top_k=k,
                                                              document_ids=document_ids, 
                                                              query_type="table")
            logger.warning(f"청크 추출 완료 : {len(rr.documents)} 개")
            
            if not rr.documents:
                # 문서를 찾을 수 없는 경우
                yield {
                    "event": "cell_result",
                    "data": {
                        "doc_id": "empty",
                        "content": "관련 문서를 찾을 수 없습니다.",
                        "is_error": True
                    }
                }
                yield {
                    "event": "completed",
                    "data": {
                        "header_name": title,
                        "message": "분석이 완료되었습니다."
                    }
                }
                return
            
            # 진행 상황 업데이트
            yield {
                "event": "progress",
                "data": {
                    "message": "문서별 정보를 분석 중입니다...",
                    "progress": 30
                }
            }
            
            # 문서별로 청크 그룹화 및 키워드 추출
            docs_data = {}
            for doc in rr.documents:
                doc_id = doc.metadata.get("document_id")
                if not doc_id:
                    continue
                
                chunk_text = doc.page_content
                if not chunk_text:
                    continue
                
                if doc_id not in docs_data:
                    docs_data[doc_id] = {
                        "content": chunk_text,
                        "keywords": {}
                    }
                else:
                    docs_data[doc_id]["content"] += "\n" + chunk_text
                
                # 키워드 빈도수 업데이트
                chunk_keywords = self._extract_keywords(chunk_text)
                for keyword in chunk_keywords:
                    if keyword in docs_data[doc_id]["keywords"]:
                        docs_data[doc_id]["keywords"][keyword] += 1
                    else:
                        docs_data[doc_id]["keywords"][keyword] = 1
            
            # 각 문서에 대해 처리 중 상태 전송
            doc_ids = list(docs_data.keys())
            for doc_id in doc_ids:
                yield {
                    "event": "cell_processing",
                    "data": {
                        "doc_id": doc_id,
                        "message": "분석 진행 중..."
                    }
                }
            
            # 진행 상황 업데이트
            yield {
                "event": "progress",
                "data": {
                    "message": "문서 내용을 분석하여 결과를 생성 중입니다...",
                    "progress": 50
                }
            }
            
            # 각 문서별로 테이블 분석을 위한 태스크 준비
            tasks = []
            for doc_id, data in docs_data.items():
                # 빈도수 기반으로 상위 키워드 선택
                sorted_keywords = sorted(
                    data["keywords"].items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
                
                keywords = {
                    "keywords": [
                        {
                            "text": kw[0],
                            "frequency": kw[1]
                        } for kw in sorted_keywords
                    ],
                    "type": "extracted",
                    "source": "document_content"
                }
                
                # 태스크 생성
                task = analyze_table_mode_task.s(
                    user_id,  # 위치 인자로 수정
                    data["content"],
                    query,
                    keywords,
                    query_analysis
                )
                tasks.append((doc_id, task))
            
            # 진행 상황 업데이트
            yield {
                "event": "progress",
                "data": {
                    "message": "각 문서별로 분석을 시작합니다...",
                    "progress": 60
                }
            }
            
            # 각 문서별로 결과를 개별적으로 처리하여 완료된 즉시 클라이언트에 전송
            total_docs = len(tasks)
            completed_docs = 0
            
            for doc_id, task in tasks:
                try:
                    # 각 문서별로 개별적으로 태스크 실행
                    task_result = task.apply_async()
                    result = task_result.get(timeout=30)  # 최대 30초 대기
                    
                    if not result:
                        result_content = "분석 결과가 없습니다."
                    else:
                        result_content = result
                    
                    # 진행률 업데이트
                    completed_docs += 1
                    progress_percent = 60 + int((completed_docs / total_docs) * 30)
                    
                    # 진행 상황 업데이트
                    yield {
                        "event": "progress",
                        "data": {
                            "message": f"문서 분석 진행 중... ({completed_docs}/{total_docs})",
                            "progress": progress_percent
                        }
                    }
                    
                    # 결과 전송
                    yield {
                        "event": "cell_result",
                        "data": {
                            "doc_id": doc_id,
                            "content": result_content,
                            "is_error": False
                        }
                    }
                    
                    # 히스토리 저장
                    if user_id and project_id:
                        try:
                            history_service = TableHistoryService(db=self.db)
                            await history_service.create(
                                TableHistoryCreate(
                                    project_id=str(project_id),
                                    document_id=str(doc_id),
                                    user_id=str(user_id),
                                    prompt=query,
                                    title=title,
                                    result=str(result_content)
                                )
                            )
                        except Exception as e:
                            logger.exception(f"히스토리 저장 실패 (개별 문서): {str(e)}")
                    
                except TimeoutError:
                    logger.error(f"문서 ID: {doc_id} 분석 시간 초과")
                    yield {
                        "event": "cell_result",
                        "data": {
                            "doc_id": doc_id,
                            "content": "분석 시간이 초과되었습니다.",
                            "is_error": True
                        }
                    }
                except Exception as e:
                    logger.error(f"문서 ID: {doc_id} 분석 중 오류: {str(e)}")
                    yield {
                        "event": "cell_result",
                        "data": {
                            "doc_id": doc_id,
                            "content": f"분석 중 오류가 발생했습니다: {str(e)}",
                            "is_error": True
                        }
                    }
            
            # 완료 이벤트 전송
            yield {
                "event": "progress",
                "data": {
                    "message": "분석이 완료되었습니다",
                    "progress": 100
                }
            }
            
            yield {
                "event": "completed",
                "data": {
                    "header_name": title,
                    "message": "모든 문서 분석이 완료되었습니다."
                }
            }
            
        except Exception as e:
            logger.exception(f"테이블 모드 스트리밍 처리 실패: {str(e)}")
            # 오류 이벤트 전송
            yield {
                "event": "error",
                "data": {
                    "message": f"분석 처리 중 오류가 발생했습니다: {str(e)}"
                }
            }

    async def _handle_chat_mode(self, query: str, document_ids: List[UUID] = None) -> Dict[str, Any]:
        """채팅 모드 처리
        
        Args:
            query: 사용자 질문
            top_k: 검색할 상위 문서 수
            document_ids: 검색할 문서 ID 목록
            
        Returns:
            Dict[str, Any]: 응답 결과
            {
                "answer": str,  # AI 응답
                "context": List[Dict]  # 관련 문서 컨텍스트
            }
        """
        try:
            # 관련 문서 검색 및 패턴 분석
            query_analysis = self._analyze_query(query)
            k = len(document_ids) * 5 # 문서당 5개. 이 옵션이 문서별로 5개를 뽑아주진 않음.
            # 그러나 적어도 전체 문서 * 5개 정도는 기본적으로 뽑아서 데이터를 추출하도록 처리
            rr: RetrievalResult = await self.process_retrival(query=query, top_k=k, document_ids=document_ids, query_type="chat")
            logger.info(f"관련 청크 검색 완료 - 총 {len(rr)}개 청크 발견")

            if not rr:
                return {
                    "answer": "관련 문서를 찾을 수 없습니다.",
                    "context": []
                }

            # 문서 컨텍스트 구성
            doc_contexts = []
            for doc in rr:
                metadata = doc.metadata
                doc_contexts.append(
                    f"문서 ID: {metadata.get('document_id', 'N/A')}\n"
                    f"페이지: {metadata.get('page_number', 'N/A')}\n" # pinecone의 metadata에는 page_number가 없음.
                    f"내용: {metadata.get('text', '')}"
                )

            # 프롬프트로 분석
            # 사용자의 질문 + 문서 컨텍스트(relevant_chunks)
            chain_response = await self.chat_prompt.analyze_async(
                content='\n\n'.join(doc_contexts),
                user_query=query,
                keywords={
                    "keywords": self._extract_keywords('\n'.join(doc_contexts)),
                    "type": "extracted",
                    "source": "document_content"
                },
                query_analysis=query_analysis
            )

            return {
                "answer": chain_response,
                "context": rr
            }

        except Exception as e:
            logger.error(f"채팅 모드 처리 중 오류 발생: {str(e)}")
            return {
                "answer": "죄송합니다. 응답 생성 중 오류가 발생했습니다.",
                "context": []
            }

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
        # 세션에서 사용자 정보 활용
        if self.session and not user_id:
            user_id = str(self.session.user_id) if self.session.user_id else None
            logger.info(f"세션에서 사용자 정보 활용: user_id={user_id}")
            
        if mode == "table":
            # UUID로 변환하여 전달
            #doc_ids = [UUID(doc_id) for doc_id in document_ids]
            return await self.handle_table_mode(
                query=query,
                document_ids=document_ids,
                user_id=user_id,
                project_id=project_id
            )
        
        # chat 모드에서는 이미 initialize에서 설정된 streaming_callback 사용
        return await self._handle_chat_mode(query, top_k, document_ids=document_ids)

    async def query_stream(
        self,
        query: str,
        mode: str = "chat",
        document_ids: List[str] = None,
        user_id: str = None,
        **kwargs
    ):
        """스트리밍 응답을 위한 쿼리 처리"""
        try:
            # 세션에서 사용자 정보 활용
            if self.session and not user_id:
                user_id = str(self.session.user_id) if self.session.user_id else None
                logger.info(f"스트리밍 응답에서 세션 사용자 정보 활용: user_id={user_id}")
                
            # 테이블 모드인 경우 별도 처리
            if mode == "table":
                async for event in self.handle_table_mode_stream(
                    query=query,
                    document_ids=document_ids,
                    user_id=user_id,
                ):
                    yield event
                return
                
            # 쿼리 타입 분석
            # retrival후 결과에 딸려오는 RetrievalResult.query_analysis 랑 헷갈리면 안됨.
            query_analysis = self._analyze_query(query)

            ###############################################
            # 관련 청크 검색   
            k = len(document_ids) * 5  # 문서당 5개. 이 옵션이 문서별로 5개를 뽑아주진 않음.
            # 그러나 적어도 전체 문서 * 5개 정도는 기본적으로 뽑아서 데이터를 추출하도록 처리
            # k 값에 대한 고민이 필요함
            # 짧은 문서는 k=5로 충분. 그러나 매우 긴 문서는? k=5로는 턱없이 부족할텐데.
            # 사용자 입력에 따라서, 어떤 스타일로 k값을 결정하고 응답을 줄지 
            # 사용자 입력의 전처리 과정 필요. _analyze_query로는 안됨.
            rr:RetrievalResult = await self.process_retrival(query=query, 
                                                             query_analysis=query_analysis, 
                                                             top_k=k, 
                                                             document_ids=document_ids, 
                                                             query_type="chat",
                                                             user_id=user_id)

            #logger.info(f"[query_stream] 관련 청크 검색 완료 - 총 {len(relevant_chunks.documents)}개 청크 발견")
            doc_cnt = len(rr.documents)
            if not rr.documents or doc_cnt == 0:
                logger.warning("관련 내용을 찾을 수 없습니다.")
                yield "관련 내용을 찾을 수 없습니다."
                return
            if document_ids is None or len(document_ids) == 0:
                logger.warning("선택된 문서가 없습니다.")
                yield "선택된 문서가 없습니다."

            if doc_cnt > 0:
                # 문서 컨텍스트 구성
                doc_contexts = []
                for doc in rr.documents:
                    if not doc.page_content or doc.page_content.strip() == "":
                        continue
                    metadata = doc.metadata
                    doc_contexts.append(
                        #f"문서 ID: {metadata.get('document_id', 'N/A')}\n"
                        #f"페이지: {metadata.get('page_number', 'N/A')}\n"
                        f"내용: {doc.page_content}"
                    )

                # 생성형AI에게 수집한 context를 바탕으로 query를 질문
                # 프롬프트 생성 및 응답
            
                async for token in self.chat_prompt.analyze_streaming(
                                        content='\n\n'.join(doc_contexts),
                                        user_query=query,
                                        keywords={
                                            "keywords": self._extract_keywords('\n\n'.join(doc_contexts)),
                                            "type": "extracted",
                                            "source": "document_content"
                                        },
                                        query_analysis=query_analysis
                                    ):
                    if self._should_stop:  # 중지 플래그 확인
                        break
                    yield token

        except Exception as e:
            logger.exception(f"스트리밍 쿼리 처리 중 오류 발생: {str(e)}")
            raise


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

            # 접근 가능 여부 확인 - bool 타입으로 반환
            is_accessible = document.status in ['COMPLETED', 'PARTIAL'] and bool(document.embedding_ids)

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
        
        # 쿼리 의도 분석
        query_intent = self._analyze_query_intent(query_lower)
            
        analysis = {
            "query": query_lower,        # 원본 쿼리 (소문자)
            "length": len(query),        # 쿼리 길이
            "word_count": len(query.split()),  # 단어 수
            "has_numbers": bool(re.search(r'\d', query)),  # 숫자 포함 여부
            "has_special_chars": bool(re.search(r'[^\w\s]', query)),  # 특수문자 포함 여부
            "timestamp": datetime.now().isoformat(),  # 분석 시간
            "focus_area": self._get_query_focus(query_lower),  # 쿼리 초점 영역(어떤 분야에 대한 질문인지)
            "doc_type": self._get_doc_type(query_lower),  # 문서 타입 추론
            "intent": query_intent  # 쿼리 의도 추가
        }
        
        return analysis
        
    def _analyze_query_intent(self, query: str) -> str:
        """쿼리 의도 분석 (요약, 세부정보 등)
        
        Args:
            query: 소문자로 변환된 쿼리
            
        Returns:
            str: 쿼리 의도
        """
        # 요약 관련 키워드
        summary_keywords = [
            "summarize", "summary", "overview", "brief", "outline", 
            "highlight", "key points", "key information", "main points",
            "요약", "개요", "정리", "핵심", "중요 내용", "주요 정보"
        ]
        
        # 세부 정보 관련 키워드
        detail_keywords = [
            "detail", "explain", "elaborate", "specific", "exactly",
            "세부", "상세", "자세히", "구체적", "정확히"
        ]
        
        # 요약 키워드 포함 여부 확인
        if any(keyword in query for keyword in summary_keywords):
            return "summary"
            
        # 세부 정보 키워드 포함 여부 확인
        if any(keyword in query for keyword in detail_keywords):
            return "detail"
            
        # 기타 의도 분석 (추가 가능)
        
        # 기본 의도
        return "general"
        
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
            'industry': r'산업|시장|경쟁|점유율|트렌드|성장성|전망|예측',
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

    async def stop_generation(self):
        """메시지 생성 중지"""
        self._should_stop = True
        if hasattr(self.chat_prompt, 'stop_generation'):
            await self.chat_prompt.stop_generation()

    
