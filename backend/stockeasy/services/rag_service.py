"""멀티에이전트 기반 텔레그램 RAG 서비스

이 모듈은 텔레그램 메시지에 대한 검색과 요약, 기업 리포트 분석, 재무 데이터 분석, 
산업 동향 분석을 Langgraph 기반 멀티에이전트 시스템을 통해 제공합니다.
"""

import asyncio
import os
import threading
from typing import Dict, List, Any, Optional, ClassVar, Union, Callable
from uuid import UUID
from loguru import logger
import time
from sqlalchemy.ext.asyncio import AsyncSession

from stockeasy.models.agent_io import QuestionClassification
from common.utils.util import async_retry
from common.core.config import settings
from common.core.database import get_db_session
from langchain.callbacks.tracers import LangChainTracer

class StockRAGService:
    """Langgraph 기반 주식 분석 RAG 서비스"""
    
    _cleanup_thread: Optional[threading.Thread] = None
    _stop_event: threading.Event = threading.Event()
    
    def __init__(self, db: Optional[AsyncSession] = None):
        """
        주식 분석 그래프 초기화
        
        Args:
            db: 데이터베이스 세션 객체 (선택적)
        """
        # LangSmith 트레이서 초기화
        os.environ["LANGCHAIN_TRACING"] = "true"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        if settings.ENV == "production":
            os.environ["LANGCHAIN_PROJECT"] = "stockeasy_server_agents"
            tracer = LangChainTracer(project_name="stockeasy_server_agents")
        else:
            os.environ["LANGCHAIN_PROJECT"] = "stockeasy_dev"
            tracer = LangChainTracer(project_name="stockeasy_dev")
            
        self.db = db or asyncio.run(get_db_session())
        
        # AgentRegistry 및 그래프를 직접 소유
        from stockeasy.graph.agent_registry import AgentRegistry
        self.agent_registry = AgentRegistry()
        self.agent_registry.initialize_agents(self.db)
        self.graph = self.agent_registry.get_graph(self.db)
        
        self._user_contexts = {}  # 사용자별 컨텍스트 저장
        
        #logger.info("멀티에이전트 기반 주식 분석 RAG 서비스가 초기화되었습니다.")
    async def close(self):
        """
        리소스 정리 - DB 세션 닫기
        """
        if hasattr(self, 'db') and self.db:
            try:
                
                # DB 세션 닫기
                logger.info("StockRAGService DB 세션 닫기")
                await self.db.close()
                self.db = None
            except Exception as e:
                logger.error(f"DB 세션 닫기 중 오류 발생: {str(e)}")
    
    def __del__(self):
        """
        소멸자 - 리소스 정리
        """
        if hasattr(self, 'db') and self.db:
            try:
                
                # DB 세션 닫기 (비동기 함수를 동기적으로 호출)
                logger.warning("소멸자에서 DB 세션 닫기 시도 - 비추천 방식")
                
                # 주의: 소멸자에서 비동기 함수를 실행하는 것은 문제가 있으므로
                # 가능하면 명시적 close() 호출을 권장
                try:
                    import asyncio
                    # 이미 이벤트 루프가 있는 경우와 없는 경우 모두 처리
                    loop = asyncio.get_event_loop() if asyncio.get_event_loop_policy().get_event_loop().is_running() else None
                    if loop and loop.is_running():
                        # 현재 실행 중인 이벤트 루프가 있으면 future로 처리
                        asyncio.run_coroutine_threadsafe(self.db.close(), loop)
                    else:
                        # 없으면 새 루프 생성
                        asyncio.run(self.db.close())
                except Exception as e:
                    logger.error(f"소멸자에서 DB 세션 닫기 실패: {str(e)}")
            except Exception as e:
                logger.error(f"소멸자에서 리소스 정리 중 오류: {str(e)}")
    
    # 비동기 컨텍스트 매니저 메소드 (선택 사항)
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입점"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료점"""
        await self.close()
    
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
    async def analyze_stock(
        self,
        query: str,
        stock_code: str,
        stock_name: str,
        session_id: str,
        user_id: Optional[Union[str, UUID]] = None,
        chat_session_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        streaming_callback: Optional[Callable] = None,
        is_follow_up: bool = False,
        agent_results: Optional[Dict[str, Any]] = {}
    ) -> Dict[str, Any]:
        """
        주식 정보 분석

        Args:
            query: 사용자 질문
            stock_code: 종목 코드
            stock_name: 종목명
            session_id: 세션 ID
            user_id: 사용자 ID
            chat_session_id: 채팅 세션 ID (선택적)
            conversation_history: 대화 이력 (선택적)
            streaming_callback: 스트리밍 응답을 받을 콜백 함수 (선택적)
            is_follow_up: 후속질문 여부 (선택적)
            agent_results : 후속질문에 사용할 이전 에이전트 결과물

        Returns:
            분석 결과
        """
        try:
            # 에이전트 그래프 초기화 (필요시)
            if not self.graph:
                self.graph = self.agent_registry.get_graph(self.db)

            # 사용자 컨텍스트 준비
            user_context = {
                "user_id": str(user_id) if user_id else None,
                "session_id": session_id,
                "stock_code": stock_code,
                "stock_name": stock_name,
                "is_follow_up": is_follow_up
            }

            # 분석 실행
            logger.info(f"[StockRAGService] 주식 분석 시작: 질문='{query}', 종목코드={stock_code}, 종목명={stock_name}, 후속질문={is_follow_up}")
            
            # streaming_callback 로깅 추가
            callback_name = getattr(streaming_callback, '__name__', '이름 없음')
            callback_id = id(streaming_callback) if streaming_callback else None
            logger.info(f"[StockRAGService] 스트리밍 콜백 상태: {callback_name}, id={callback_id}")
            
            # process_query 호출 시 추가 인자 전달
            result = await self.graph.process_query(
                query=query,
                session_id=session_id,
                stock_code=stock_code,
                stock_name=stock_name,
                user_context=user_context,
                chat_session_id=chat_session_id,
                conversation_history=conversation_history,
                streaming_callback=streaming_callback,  # 스트리밍 콜백 함수 전달
                is_follow_up=is_follow_up,  # 후속질문 여부 전달
                agent_results=agent_results  # 후속질문에 사용할 이전 에이전트 결과물 전달
            )
            
            logger.info(f"[StockRAGService] 주식 분석 완료: 종목코드={stock_code}, 결과 크기={len(str(result))}자")
            
            return result
            
        except Exception as e:
            logger.exception(f"[StockRAGService] 주식 분석 중 오류 발생: {str(e)}")
            # 오류 발생 시 기본 응답 반환
            return {
                "query": query,
                "stock_code": stock_code,
                "stock_name": stock_name,
                "answer": f"죄송합니다. 질문 처리 중 오류가 발생했습니다: {str(e)}",
                "error": str(e)
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

    

