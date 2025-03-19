"""멀티에이전트 기반 텔레그램 RAG 서비스

이 모듈은 텔레그램 메시지에 대한 검색과 요약, 기업 리포트 분석, 재무 데이터 분석, 
산업 동향 분석을 Langgraph 기반 멀티에이전트 시스템을 통해 제공합니다.
"""

import asyncio
import threading
from typing import Dict, List, Any, Optional, ClassVar
from loguru import logger
import time
from sqlalchemy.ext.asyncio import AsyncSession

from stockeasy.graph.agent_registry import get_graph
from stockeasy.services.telegram.question_classifier import QuestionClassification
from common.utils.util import async_retry
from common.core.config import settings
from common.core.database import get_db_session


class StockRAGService:
    """Langgraph 기반 주식 분석 RAG 서비스 (싱글톤 패턴)"""
    
    _instance: ClassVar[Optional["StockRAGService"]] = None
    _initialized: bool = False
    _cleanup_thread: Optional[threading.Thread] = None
    _stop_event: threading.Event = threading.Event()
    
    def __new__(cls, db: Optional[AsyncSession] = None, *args, **kwargs):
        """싱글톤 인스턴스 생성 또는 반환"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, db: Optional[AsyncSession] = None):
        """
        주식 분석 그래프 초기화 (싱글톤)
        
        Args:
            db: 데이터베이스 세션 객체 (선택적)
        """
        # 이미 초기화된 경우 스킵
        if self._initialized:
            return
            
        self.db = db or asyncio.run(get_db_session())
        self.graph = get_graph(self.db)
        self._user_contexts = {}  # 사용자별 컨텍스트 저장
        self._initialized = True
        
        # 백그라운드 세션 정리 시작
        self._start_cleanup_thread()
        
        logger.info("멀티에이전트 기반 주식 분석 RAG 서비스가 초기화되었습니다.")

    def _start_cleanup_thread(self):
        """백그라운드 세션 정리 스레드 시작"""
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._stop_event.clear()
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_worker,
                daemon=True
            )
            self._cleanup_thread.start()
            logger.info("세션 정리 백그라운드 작업이 시작되었습니다.")
    
    def _cleanup_worker(self):
        """백그라운드 세션 정리 작업"""
        cleanup_interval = 3600  # 1시간마다 정리
        while not self._stop_event.is_set():
            try:
                time.sleep(cleanup_interval)
                if not self._stop_event.is_set():
                    cleaned_count = self.cleanup_old_contexts()
                    logger.info(f"정기 세션 정리 완료: {cleaned_count}개 정리됨")
            except Exception as e:
                logger.error(f"세션 정리 작업 중 오류 발생: {e}")
    
    def stop_cleanup_thread(self):
        """백그라운드 정리 스레드 중지"""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._stop_event.set()
            self._cleanup_thread.join(timeout=5)
            logger.info("세션 정리 백그라운드 작업이 중지되었습니다.")
    
    def configure_for_user(self, session_id: str, user_id: Optional[str] = None) -> None:
        """특정 사용자/세션에 대한 컨텍스트 설정
        
        Args:
            session_id: 세션 ID
            user_id: 사용자 ID (선택적)
        """
        if session_id not in self._user_contexts:
            # 새 컨텍스트 생성 - user_id는 None이더라도 명시적으로 저장
            self._user_contexts[session_id] = {
                "user_id": user_id,  # None이어도 명시적으로 저장
                "session_id": session_id,
                "last_accessed": time.time()
            }
        else:
            # 기존 컨텍스트 업데이트
            self._user_contexts[session_id]["last_accessed"] = time.time()
            # user_id는 None이어도 항상 업데이트 (명시적으로 세션의 현재 사용자 상태 반영)
            self._user_contexts[session_id]["user_id"] = user_id
        
        logger.info(f"사용자 컨텍스트 설정: 세션 ID {session_id}, 사용자 ID {user_id or '익명'}")
    
    @async_retry(retries=2, delay=2.0, exceptions=(Exception,))
    async def analyze_stock(self, 
                           query: str, 
                           stock_code: Optional[str] = None,
                           stock_name: Optional[str] = None,
                           session_id: Optional[str] = None,
                           user_id: Optional[str] = None,
                           classification: Optional[QuestionClassification] = None) -> Dict[str, Any]:
        """
        주식 관련 쿼리 분석 및 응답 생성
        
        Args:
            query: 사용자 질문
            stock_code: 종목 코드 (선택적)
            stock_name: 종목명 (선택적)
            session_id: 세션 ID (사용자 인증용)
            user_id: 사용자 ID (선택적)
            classification: 질문 분류 결과 (선택적)
            
        Returns:
            분석 결과 (요약, 검색된 메시지, 분류 정보 등)
        """
        try:
            start_time = time.time()
            logger.info(f"주식 분석 시작: {query}")
            
            # 세션 ID가 없는 경우 오류 반환
            if not session_id:
                logger.warning("세션 ID가 제공되지 않았습니다. 인증이 필요합니다.")
                return {
                    "query": query,
                    "errors": [{
                        "agent": "stock_rag_service",
                        "error": "인증이 필요합니다. 로그인 후 이용해주세요.",
                        "type": "AuthenticationError"
                    }],
                    "authentication_required": True,
                    "summary": "인증이 필요합니다. 로그인 후 이용해주세요."
                }
            
            # 사용자 컨텍스트 업데이트/설정
            self.configure_for_user(session_id, user_id)
            
            # 이미 분류 결과가 있으면 해당 정보 사용
            initial_state = {
                "query": query,
                "stock_code": stock_code,
                "stock_name": stock_name,
                "session_id": session_id,
            }
            
            # 사용자 ID가 있으면 추가
            if user_id is not None:  # None이더라도 명시적으로 전달
                initial_state["user_id"] = user_id
                
            # 해당 사용자의 컨텍스트가 있으면 추가
            if session_id in self._user_contexts:
                initial_state["user_context"] = self._user_contexts[session_id]
            
            if classification:
                initial_state["question_classification"] = classification.model_dump()
            
            logger.info(f"[analyze_stock] initial_state: {initial_state}")
            result = await self.graph.process_query(**initial_state)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # 처리 시간 로깅
            logger.info(f"주식 분석 완료: 처리 시간 = {processing_time:.2f}초")
            
            # 결과에 처리 시간, 세션 ID 및 사용자 ID 추가
            if result:
                if "processing_status" not in result:
                    result["processing_status"] = {}
                result["processing_status"]["total_time"] = processing_time
                
                # 세션 ID와 사용자 ID 추가 (클라이언트가 추적할 수 있게)
                result["session_id"] = session_id
                result["user_id"] = user_id
            
            return result
            
        except Exception as e:
            logger.error(f"주식 분석 중 오류 발생: {str(e)}", exc_info=True)
            return {
                "query": query,
                "session_id": session_id,  # 오류 발생 시에도 세션 ID 포함
                "user_id": user_id,        # 오류 발생 시에도 사용자 ID 포함
                "errors": [{
                    "agent": "stock_rag_service",
                    "error": str(e),
                    "type": type(e).__name__
                }],
                "summary": "죄송합니다. 주식 분석 중 오류가 발생했습니다."
            }

    def cleanup_old_contexts(self, max_age_hours: int = 24) -> int:
        """오래된 사용자 컨텍스트 정리
        
        Args:
            max_age_hours: 최대 보관 시간 (시간 단위)
            
        Returns:
            정리된 컨텍스트 수
        """
        now = time.time()
        max_age_secs = max_age_hours * 3600
        old_sessions = [
            session_id for session_id, context in self._user_contexts.items()
            if now - context["last_accessed"] > max_age_secs
        ]
        
        # 오래된 세션 삭제
        for session_id in old_sessions:
            del self._user_contexts[session_id]
        
        if old_sessions:
            logger.info(f"{len(old_sessions)}개의 오래된 사용자 컨텍스트가 정리되었습니다.")
        
        return len(old_sessions)


class TelegramRAGLangraphService:
    """Langgraph 기반 텔레그램 RAG 서비스"""
    
    def __init__(self, db: Optional[AsyncSession] = None):
        """
        서비스 초기화
        
        Args:
            db: 데이터베이스 세션 객체 (선택적)
        """
        self.stock_rag_service = StockRAGService(db)
        logger.info("Langgraph 기반 텔레그램 RAG 서비스가 초기화되었습니다.")
    
    async def search_and_summarize(self, 
                                  query: str, 
                                  stock_code: Optional[str] = None, 
                                  stock_name: Optional[str] = None,
                                  session_id: Optional[str] = None,
                                  user_id: Optional[str] = None,
                                  classification: Optional[QuestionClassification] = None) -> Dict[str, Any]:
        """
        텔레그램 메시지 검색 및 요약
        
        최신 멀티에이전트 아키텍처를 사용하여 텔레그램 메시지와 다양한
        금융 데이터 소스에서 정보를 검색하고 요약합니다.
        
        Args:
            query: 검색 쿼리
            stock_code: 종목 코드 (선택적)
            stock_name: 종목명 (선택적)
            session_id: 세션 ID (선택적)
            user_id: 사용자 ID (선택적)
            classification: 질문 분류 결과 (선택적)
            
        Returns:
            검색 및 요약 결과
        """
        try:
            logger.info(f"검색 및 요약 시작: {query}")
            
            # 세션 ID가 없는 경우 인증 오류 반환
            if not session_id:
                logger.warning("세션 ID가 제공되지 않았습니다. 인증이 필요합니다.")
                return {
                    "summary": "인증이 필요합니다. 로그인 후 이용해주세요.",
                    "telegram_messages": [],
                    "question_classification": classification.model_dump() if classification else {},
                    "processing_time": 0,
                    "authentication_required": True,
                    "error": "인증이 필요합니다. 로그인 후 이용해주세요."
                }
            
            # StockRAGService를 통해 멀티에이전트 분석 수행
            result = await self.stock_rag_service.analyze_stock(
                query=query,
                stock_code=stock_code,
                stock_name=stock_name,
                session_id=session_id,
                user_id=user_id,
                classification=classification
            )
            
            # 인증 필요한 경우 처리
            if result.get("authentication_required", False):
                return {
                    "summary": result.get("summary", "인증이 필요합니다. 로그인 후 이용해주세요."),
                    "telegram_messages": [],
                    "question_classification": classification.model_dump() if classification else {},
                    "processing_time": 0,
                    "authentication_required": True,
                    "error": result.get("errors", [{}])[0].get("error", "인증이 필요합니다. 로그인 후 이용해주세요.")
                }
            
            # 결과 구조화
            summary = result.get("summary", "")
            formatted_response = result.get("formatted_response", "")
            
            # 실제 사용할 최종 응답 선택 (formatted_response가 있으면 사용, 없으면 summary 사용)
            final_response = formatted_response or summary
            
            # 메트릭 수집
            processing_status = result.get("processing_status", {})
            
            return {
                "summary": final_response,
                "telegram_messages": result.get("retrieved_data", {}).get("telegram_messages", []),
                "question_classification": result.get("question_classification", {}),
                "processing_time": processing_status.get("total_time", 0),
                "session_id": session_id,
                "user_id": user_id
            }
            
        except Exception as e:
            logger.error(f"검색 및 요약 중 오류 발생: {str(e)}", exc_info=True)
            return {
                "summary": f"죄송합니다. 검색 중 오류가 발생했습니다: {str(e)}",
                "telegram_messages": [],
                "question_classification": classification.model_dump() if classification else {},
                "processing_time": 0,
                "error": str(e),
                "session_id": session_id,
                "user_id": user_id
            } 