"""
텔레그램 메시지 검색 에이전트 모듈

이 모듈은 사용자 질문에 관련된 텔레그램 메시지를 검색하는 에이전트 클래스를 구현합니다.
기존 텔레그램 검색 기능을 QuestionAnalyzerAgent의 결과를 활용하도록 개선합니다.
"""

import re
import json
import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
from loguru import logger
from typing import Dict, List, Any, Optional, Set, cast


from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser

from common.utils.util import async_retry
#from common.core.logger import get_logger
#from common.core.llm import LLMProvider
from common.core.config import settings
from stockeasy.services.telegram.embedding import TelegramEmbeddingService

from common.services.vector_store_manager import VectorStoreManager
from common.services.retrievers.semantic import SemanticRetriever, SemanticRetrieverConfig
from common.services.retrievers.models import RetrievalResult
from stockeasy.models.agent_io import RetrievedData, RetrievedMessage


class TelegramRetrieverAgent:
    """텔레그램 메시지 검색 에이전트"""
    
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0):
        """
        텔레그램 메시지 검색 에이전트 초기화
        
        Args:
            model_name: 사용할 OpenAI 모델 이름
            temperature: 모델 출력의 다양성 조절 파라미터
        """
        self.embedding_service = TelegramEmbeddingService()
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature, api_key=settings.OPENAI_API_KEY)
        self.parser = JsonOutputParser()
        logger.info(f"TelegramRetrieverAgent initialized with model: {model_name}")
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        사용자 쿼리와 분류 정보를 기반으로 텔레그램 메시지를 검색합니다.
        
        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리
            
        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 성능 측정 시작
            start_time = datetime.now()
            logger.info("TelegramRetrieverAgent starting processing")
            
            # 현재 쿼리 및 세션 정보 추출
            query = state.get("query", "")
            
            # 질문 분석 결과 추출 (새로운 구조)
            question_analysis = state.get("question_analysis", {})
            entities = question_analysis.get("entities", {})
            classification = question_analysis.get("classification", {})
            data_requirements = question_analysis.get("data_requirements", {})
            keywords = question_analysis.get("keywords", [])
            detail_level = question_analysis.get("detail_level", "보통")
            
            # 엔티티에서 종목 정보 추출
            stock_code = entities.get("stock_code", state.get("stock_code"))
            stock_name = entities.get("stock_name", state.get("stock_name"))
            sector = entities.get("sector", "")
            
            if not query:
                logger.warning("Empty query provided to TelegramRetrieverAgent")
                self._add_error(state, "검색 쿼리가 제공되지 않았습니다.")
                return state
            
            logger.info(f"TelegramRetrieverAgent processing query: {query}")
            logger.info(f"Classification data: {classification}")
            logger.info(f"State keys: {state.keys()}")
            logger.info(f"Entities: {entities}")
            logger.info(f"Data requirements: {data_requirements}")
            
            # 동적 임계값 및 메시지 수 설정
            threshold = self._calculate_dynamic_threshold(classification)
            message_count = self._get_message_count(classification)
            
            # 검색 쿼리 생성 (보다 정확한 검색을 위해 클래스 및 의도 정보 활용)
            search_query = self._make_search_query(query, stock_code, stock_name, classification, sector)
            
            # 메시지 검색 실행
            messages = await self._search_messages(
                search_query, 
                message_count, 
                threshold
            )
            
            # 검색 결과가 없는 경우
            if not messages:
                logger.warning("텔레그램 메시지 검색 결과가 없습니다.")
                
                # 실행 시간 계산
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                # 새로운 구조로 상태 업데이트 (결과 없음)
                state["agent_results"] = state.get("agent_results", {})
                state["agent_results"]["telegram_retriever"] = {
                    "agent_name": "telegram_retriever",
                    "status": "partial_success",
                    "data": [],
                    "error": None,
                    "execution_time": duration,
                    "metadata": {
                        "message_count": 0,
                        "threshold": threshold
                    }
                }
                
                # 타입 주석을 사용한 데이터 할당
                if "retrieved_data" not in state:
                    state["retrieved_data"] = {}
                retrieved_data = cast(RetrievedData, state["retrieved_data"])
                telegram_messages: List[RetrievedMessage] = []
                retrieved_data["telegram_messages"] = telegram_messages
                
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["telegram_retriever"] = "completed_no_data"
                
                # 메트릭 기록
                state["metrics"] = state.get("metrics", {})
                state["metrics"]["telegram_retriever"] = {
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": duration,
                    "status": "completed_no_data",
                    "error": None,
                    "model_name": self.llm.model_name
                }
                
                logger.info(f"TelegramRetrieverAgent completed in {duration:.2f} seconds, found 0 messages")
                return state
                
            # 수행 시간 계산
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 새로운 구조로 상태 업데이트
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["telegram_retriever"] = {
                "agent_name": "telegram_retriever",
                "status": "success",
                "data": messages,
                "error": None,
                "execution_time": duration,
                "metadata": {
                    "message_count": len(messages),
                    "threshold": threshold
                }
            }
            
            # 타입 주석을 사용한 데이터 할당
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            retrieved_data = cast(RetrievedData, state["retrieved_data"])
            telegram_messages: List[RetrievedMessage] = messages
            retrieved_data["telegram_messages"] = telegram_messages
            
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["telegram_retriever"] = "completed"
            
            # 메트릭 기록
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["telegram_retriever"] = {
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "status": "completed",
                "error": None,
                "model_name": self.llm.model_name
            }
            
            logger.info(f"TelegramRetrieverAgent completed in {duration:.2f} seconds, found {len(messages)} messages")
            return state
            
        except Exception as e:
            logger.exception(f"Error in TelegramRetrieverAgent: {str(e)}")
            self._add_error(state, f"텔레그램 메시지 검색 에이전트 오류: {str(e)}")
            
            # 오류 상태 업데이트
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["telegram_retriever"] = {
                "agent_name": "telegram_retriever",
                "status": "failed",
                "data": [],
                "error": str(e),
                "execution_time": 0,
                "metadata": {}
            }
            
            # 타입 주석을 사용한 데이터 할당
            if "retrieved_data" not in state:
                state["retrieved_data"] = {}
            retrieved_data = cast(RetrievedData, state["retrieved_data"])
            telegram_messages: List[RetrievedMessage] = []
            retrieved_data["telegram_messages"] = telegram_messages
            
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["telegram_retriever"] = "error"
            
            return state
            
    def _add_error(self, state: Dict[str, Any], error_message: str) -> None:
        """
        상태 객체에 오류 정보를 추가합니다.
        
        Args:
            state: 상태 객체
            error_message: 오류 메시지
        """
        state["errors"] = state.get("errors", [])
        state["errors"].append({
            "agent": "telegram_retriever",
            "error": error_message,
            "type": "processing_error",
            "timestamp": datetime.now(),
            "context": {"query": state.get("query", "")}
        })
    
    def _calculate_dynamic_threshold(self, classification: Dict[str, Any]) -> float:
        """
        질문 복잡도에 따른 동적 유사도 임계값 계산
        
        Args:
            classification: 분류 결과
            
        Returns:
            유사도 임계값
        """
        complexity = classification.get("complexity", "중간")
        
        # 복잡도에 따른 임계값 설정
        if complexity == "단순":
            return 0.7  # 단순 질문일수록 높은 임계값 (정확한 결과 필요)
        elif complexity == "중간":
            return 0.6
        elif complexity == "복합":
            return 0.5
        else:  # "전문가급"
            return 0.4  # 복잡한 질문일수록 낮은 임계값 (폭넓은 결과 수집)
    
    def _get_message_count(self, classification: Dict[str, Any]) -> int:
        """
        복잡도에 따른 검색 메시지 수 결정
        
        Args:
            classification: 분류 결과
            
        Returns:
            검색할 메시지 수
        """
        complexity = classification.get("complexity", "중간")
        
        if complexity == "단순":
            return 5
        elif complexity == "중간":
            return 10
        elif complexity == "복합":
            return 15
        else:  # "전문가급"
            return 20
    
    def _calculate_message_importance(self, message: str) -> float:
        """
        메시지의 중요도를 계산합니다.
        
        Args:
            message: 중요도를 계산할 메시지
            
        Returns:
            0~1 사이의 중요도 점수
        """
        importance_score = 0.0
        
        # 1. 금액/수치 정보 포함 여부 (40%)
        if re.search(r'[0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?%?원?', message):
            importance_score += 0.4
            
        # 2. 주요 키워드 포함 여부 (40%)
        important_keywords = [
            '실적', '공시', '매출', '영업이익', '순이익',
            '계약', '특허', '인수', '합병', 'M&A',
            '상한가', '하한가', '급등', '급락',
            '목표가', '투자의견', '리포트'
        ]
        keyword_count = sum(1 for keyword in important_keywords if keyword in message)
        if keyword_count > 0:
            importance_score += min(0.4, keyword_count * 0.2)  # 키워드당 0.2점, 최대 0.4점
        
        # 3. 메시지 길이 가중치 (20%)
        msg_length = len(message)
        if 50 <= msg_length <= 500:
            importance_score += 0.2
        elif 20 <= msg_length < 50 or 500 < msg_length <= 1000:
            importance_score += 0.1
            
        return importance_score
    
    def _is_duplicate(self, message: str, seen_messages: Set[str]) -> bool:
        """
        메시지가 이미 처리된 메시지 중 중복인지 확인합니다.
        
        Args:
            message: 검사할 메시지
            seen_messages: 이미 처리된 메시지 해시 집합
            
        Returns:
            중복 여부
        """
        # 메시지 해시 생성
        message_hash = self._get_message_hash(message)
        
        # 중복 확인
        if message_hash in seen_messages:
            return True
            
        return False
    
    def _calculate_time_weight(self, created_at_str: str) -> float:
        """
        메시지 생성 시간 기반의 가중치를 계산합니다.
        
        Args:
            created_at_str: 메시지 생성 시간 문자열 (ISO 형식)
            
        Returns:
            시간 기반 가중치 (0.4 ~ 1.0)
        """
        try:
            # 시간 문자열을 datetime 객체로 변환
            if created_at_str:
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            else:
                # 시간 정보가 없는 경우 1개월 전으로 가정
                created_at = datetime.now(timezone.utc) - timedelta(days=30)
                
            # 현재 시간과의 차이 계산
            now = datetime.now(timezone.utc)
            delta = now - created_at
            
            # 시간 차이에 따른 가중치 설정
            if delta.days < 1:  # 24시간 이내
                return 1.0
            elif delta.days < 7:  # 1주일 이내
                return 0.9
            elif delta.days < 14:  # 2주일 이내
                return 0.8
            elif delta.days < 30:  # 1개월 이내
                return 0.6
            else:  # 1개월 이상
                return 0.4
                
        except Exception as e:
            logger.warning(f"시간 가중치 계산 오류: {str(e)}")
            return 0.5  # 오류 시 중간값 반환
    
    def _make_search_query(self, query: str, stock_code: Optional[str], 
                          stock_name: Optional[str], classification: Dict[str, Any],
                          sector: Optional[str] = None) -> str:
        """
        검색 쿼리를 구성합니다.
        
        Args:
            query: 원본 사용자 쿼리
            stock_code: 종목 코드
            stock_name: 종목 이름
            classification: 질문 분류 정보
            sector: 산업 섹터 정보
            
        Returns:
            검색을 위한 향상된 쿼리 문자열
        """
        # 분류 정보에서 관련 데이터 추출
        primary_intent = classification.get("primary_intent", "")
        secondary_intent = classification.get("secondary_intent", "")
        time_frame = classification.get("time_frame", "")
        aspect = classification.get("aspect", "")
        
        # 중요 키워드 추출 (검색 쿼리 강화에 사용)
        important_keywords = []
        
        # 주요 의도를 기반으로 키워드 추가
        if primary_intent == "현재가치":
            important_keywords.extend(["현재가", "주가", "시세", "시가총액"])
        elif primary_intent == "성과전망":
            important_keywords.extend(["전망", "예측", "기대", "목표가"])
        elif primary_intent == "투자의견":
            important_keywords.extend(["투자의견", "매수", "매도", "보유", "추천"])
        elif primary_intent == "재무정보":
            important_keywords.extend(["실적", "매출", "영업이익", "순이익", "재무"])
        elif primary_intent == "기업정보":
            important_keywords.extend(["기업", "사업", "제품", "서비스"])
        
        # 시간 프레임을 기반으로 키워드 추가
        if time_frame == "과거":
            important_keywords.extend(["지난", "이전", "과거"])
        elif time_frame == "현재":
            important_keywords.extend(["현재", "지금", "오늘"])
        elif time_frame == "미래":
            important_keywords.extend(["향후", "전망", "예상", "미래"])
        
        # 종목 정보가 있는 경우 쿼리에 추가
        query_parts = [query]
        
        if stock_name:
            query_parts.append(stock_name)
        
        if stock_code:
            query_parts.append(stock_code)
            
        if sector:
            query_parts.append(sector)
        
        # 분류에서 중요 정보가 있을 경우 쿼리에 포함 (상위 3개만)
        enhanced_query = " ".join(query_parts)
        
        return enhanced_query
    
    @async_retry(retries=3, delay=1.0, exceptions=(Exception,))
    async def _search_messages(self, search_query: str, k: int, threshold: float) -> List[Dict[str, Any]]:
        """
        텔레그램 메시지 검색을 수행합니다.
        
        Args:
            search_query: 검색 쿼리
            k: 검색할 메시지 수
            threshold: 유사도 임계값
            
        Returns:
            검색된 텔레그램 메시지 목록
        """
        try:
            logger.info(f"Generated search query: {search_query}")
            
            # 임베딩 모델을 사용하여 쿼리 벡터 생성
            # embeddings = TelegramEmbeddingModel(model_type="remote")
            
            # # 텔레그램 검색 인덱스에서 검색 수행
            # retriever = TelegramRetriever(embeddings)
            # retriever.filter_by_threshold(threshold)
            
            # 초기 검색은 더 많은 결과를 가져온 후 필터링
            initial_k = min(k * 3, 30)  # 적어도 원하는 k의 3배, 최대 30개까지
            
            # Pinecone 벡터 스토어 연결
            vs_manager = VectorStoreManager(
                embedding_model_type=self.embedding_service.get_model_type(),
                project_name="stockeasy",
                namespace=settings.PINECONE_NAMESPACE_STOCKEASY_TELEGRAM
            )

            # 시맨틱 검색 설정
            semantic_retriever = SemanticRetriever(
                config=SemanticRetrieverConfig(min_score=threshold),
                vs_manager=vs_manager
            )
                    
            # 검색 수행
            result: RetrievalResult = await semantic_retriever.retrieve(
                query=search_query, 
                top_k=initial_k,#k * 2,
            )
            
            if len(result.documents) == 0:
                logger.warning(f"No telegram messages found for query: {search_query}")
                return []
                
            # 결과가 너무 적은 경우 임계값 낮춰서 다시 시도
            # if len(result) < 3 and threshold > 0.3:
            #     logger.info(f"Few results ({len(result)}), lowering threshold to 0.3")
            #     retriever.filter_by_threshold(0.3)
            #     result = await retriever.get_relevant_messages(search_query, k=initial_k)
                
            # if not result:
            #     logger.warning("Still no telegram messages found after lowering threshold")
            #     return []
                
            logger.info(f"Found {len(result.documents)} telegram messages")
            
            # 중복 메시지 필터링 및 점수 계산
            processed_messages = []
            seen_messages = set()  # 중복 확인용
            
            for doc in result.documents:
                doc_metadata = doc.metadata
                content = doc_metadata.get("text", "")
                
                # 내용이 없거나 너무 짧은 메시지 제외
                if not content or len(content) < 10:
                    continue
                    
                # 중복 메시지 확인
                if self._is_duplicate(content, seen_messages):
                    continue
                    
                seen_messages.add(self._get_message_hash(content))
                
                # 메시지 중요도 계산
                importance_score = self._calculate_message_importance(content)
                
                # 시간 기반 가중치 계산
                time_weight = self._calculate_time_weight(
                    doc_metadata.get("message_created_at", datetime.now().isoformat())
                )
                
                # 최종 점수 = 유사도 * 중요도 * 시간 가중치
                final_score = doc.score * importance_score * time_weight
                
                # 메시지 데이터 구성
                message = {
                    "content": content,
                    "channel_name": doc_metadata.get("channel_name", "알 수 없음"),
                    "message_created_at": doc_metadata.get("message_created_at"),
                    "similarity": doc.score,
                    "importance": importance_score,
                    "time_weight": time_weight,
                    "final_score": final_score,
                    "id": doc_metadata.get("id", "")
                }
                
                processed_messages.append(message)
            
            # 최종 점수 기준으로 정렬하고 상위 k개 선택
            processed_messages.sort(key=lambda x: x["final_score"], reverse=True)
            result_messages = processed_messages[:k]
            
            # 점수 분포 정규화
            if result_messages:
                max_score = max(msg["final_score"] for msg in result_messages)
                min_score = min(msg["final_score"] for msg in result_messages)
                score_range = max_score - min_score if max_score > min_score else 1.0
                
                for msg in result_messages:
                    msg["normalized_score"] = (msg["final_score"] - min_score) / score_range
            
            return result_messages
            
        except Exception as e:
            logger.exception(f"Error searching telegram messages: {str(e)}")
            raise 

    def _get_message_hash(self, content: str) -> str:
        """
        메시지 내용의 해시값을 생성합니다.
        
        Args:
            content: 메시지 내용
            
        Returns:
            메시지 해시값
        """
        # 메시지 전처리 (공백 제거, 소문자 변환)
        normalized_content = re.sub(r'\s+', ' ', content).strip().lower()
        
        # 너무 긴 메시지는 앞부분만 사용
        if len(normalized_content) > 200:
            normalized_content = normalized_content[:200]
            
        # SHA-256 해시 생성하여 반환
        return hashlib.sha256(normalized_content.encode('utf-8')).hexdigest() 