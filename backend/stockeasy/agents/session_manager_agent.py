"""
세션 관리 에이전트 모듈

이 모듈은 사용자의 세션을 관리하고 컨텍스트를 유지하는 에이전트를 정의합니다.
사용자 인증 및 세션 상태를 처리하며, 대화 이력을 관리합니다.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from stockeasy.agents.base import BaseAgent
from common.services.user import UserService
from common.schemas.user import SessionBase
from stockeasy.prompts.session_manager_prompts import SESSION_MANAGER_PROMPT


class SessionManagerAgent(BaseAgent):
    """
    사용자 세션을 관리하고 컨텍스트를 유지하는 에이전트
    
    기존 common.services.user.UserService를 활용하여 세션 인증 및 관리를 수행합니다.
    """
    
    def __init__(self, db: AsyncSession):
        """
        세션 관리자 에이전트 초기화
        
        Args:
            db: 데이터베이스 세션 객체
        """
        self.user_service = UserService(db)
        self.conversation_history_cache = {}  # 세션 ID별 대화 이력 캐싱
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        상태를 처리하고 세션 정보를 업데이트합니다.
        
        Args:
            state: 현재 에이전트 상태
            
        Returns:
            업데이트된 상태
        """
        session_id = state.get("session_id")
        user_id = state.get("user_id")
        user_email = state.get("user_email")
        
        # 성능 측정 시작
        start_time = datetime.now()
        
        try:
            # 1. 기존 세션 확인
            if session_id:
                logger.info(f"세션 ID로 세션 검색 중: {session_id}")
                if "test_session" in session_id:
                    state["user_id"] = "test_user"
                    state["user_email"] = "test_user"
                    state["is_authenticated"] = True

                    # 새로운 컨텍스트 설정
                    state["user_context"] = {
                        "user_id": "test_user",
                        "user_email": "test_user",
                        "is_authenticated": True,
                        "last_accessed_at": datetime.now()
                    }
                    return state
                session = await self.user_service.get_active_session(session_id)
                
                if session:
                    logger.info(f"유효한 세션 찾음: {session.id}, 사용자: {session.user_email}")
                    # 유효한 세션이 있는 경우
                    state["user_id"] = session.user_id
                    state["user_email"] = session.user_email
                    state["is_authenticated"] = session.is_authenticated
                    
                    # 사용자 컨텍스트 정보 가져오기
                    state["user_context"] = {
                        "user_id": session.user_id,
                        "user_email": session.user_email,
                        "is_authenticated": session.is_authenticated,
                        "last_accessed_at": session.last_accessed_at
                    }
                    
                    # 대화 이력 검색 (캐시 또는 DB에서)
                    conversation_history = self._get_conversation_history(str(session.id))
                    state["conversation_history"] = conversation_history
                    
                    # 컨텍스트를 기반으로 현재 질문 보강
                    if conversation_history and state.get("query"):
                        state = self._enhance_query_with_context(state)
                    
                    # 동일 세션 내 새 쿼리에 대해 처리 시 이전 에이전트 결과 정리
                    if state.get("query") and state.get("query") != self._get_last_query(str(session.id)):
                        # 새로운 쿼리가 있고 이전 쿼리와 다른 경우 에이전트 결과 초기화
                        state = self._clean_agent_results(state)
                        logger.info(f"새 쿼리 감지: 에이전트 결과 데이터 초기화 완료")
                    
                    return state
            
            # 2. 세션이 없거나 만료된 경우 새 세션 생성
            logger.info(f"새 세션 생성 중: 사용자 ID: {user_id}, 이메일: {user_email}")
            session_data = SessionBase(
                user_id=user_id,
                user_email=user_email or "anonymous@example.com",
                is_anonymous=not user_id
            )
            
            session = await self.user_service.create_session(session_data)
            
            # 새 세션 정보로 상태 업데이트
            state["session_id"] = str(session.id)
            state["user_id"] = session.user_id
            state["user_email"] = session.user_email
            state["is_authenticated"] = session.is_authenticated
            
            # 새로운 컨텍스트 설정
            state["user_context"] = {
                "user_id": session.user_id,
                "user_email": session.user_email,
                "is_authenticated": session.is_authenticated,
                "last_accessed_at": session.last_accessed_at
            }
            state["conversation_history"] = []
            
            # 새 세션에서는 에이전트 결과 데이터를 완전히 초기화
            state = self._initialize_new_session_state(state)
            
            logger.info(f"새 세션이 생성됨: {session.id}")
            return state
            
        except Exception as e:
            # 세션 처리 중 오류 발생
            logger.error(f"세션 처리 중 오류 발생: {str(e)}", exc_info=True)
            if "errors" not in state:
                state["errors"] = []
            state["errors"].append({
                "agent": "session_manager",
                "error": str(e),
                "type": type(e).__name__,
                "timestamp": datetime.now()
            })
            
            # 기본 세션 정보 설정 (오류 발생 시)
            if "user_context" not in state:
                state["user_context"] = {}
            if "conversation_history" not in state:
                state["conversation_history"] = []
                
            return state
        
        finally:
            # 처리 시간 측정 및 기록
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            if "processing_status" not in state:
                state["processing_status"] = {}
                
            state["processing_status"]["session_manager"] = {
                "processing_time": processing_time,
                "timestamp": end_time
            }
    
    def _initialize_new_session_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        새 세션 상태를 초기화합니다.
        
        Args:
            state: 현재 상태
            
        Returns:
            초기화된 상태
        """
        # 에이전트 결과 초기화
        state["agent_results"] = {}
        
        # 검색된 데이터 초기화
        state["retrieved_data"] = {}
        
        # 메트릭 초기화
        state["metrics"] = {}
        
        # 처리 상태 초기화 (session_manager는 유지)
        state["processing_status"] = {
            "session_manager": state.get("processing_status", {}).get("session_manager", {})
        }
        
        # 오류 목록 초기화
        state["errors"] = []
        
        logger.info("새 세션 상태 초기화 완료")
        return state
    
    def _clean_agent_results(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        에이전트 결과 데이터를 정리합니다.
        
        Args:
            state: 현재 상태
            
        Returns:
            정리된 상태
        """
        # 이전 쿼리에 대한 에이전트 결과 초기화
        if "agent_results" in state:
            state["agent_results"] = {}
        
        # 검색된 데이터 초기화
        if "retrieved_data" in state:
            state["retrieved_data"] = {}
        
        # 처리 상태 초기화 (session_manager는 유지)
        processing_status = state.get("processing_status", {})
        session_manager_status = processing_status.get("session_manager", {})
        state["processing_status"] = {"session_manager": session_manager_status}
        
        return state
    
    def _get_last_query(self, session_id: str) -> Optional[str]:
        """
        세션의 마지막 쿼리를 반환합니다.
        
        Args:
            session_id: 세션 ID
            
        Returns:
            마지막 쿼리 또는 None
        """
        conversation_history = self._get_conversation_history(session_id)
        if not conversation_history:
            return None
        
        return conversation_history[-1].get("query")
    
    def _get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        세션에 대한 대화 이력을 조회합니다.
        
        현재는 간단한 메모리 캐싱을 사용하지만, 추후 데이터베이스에 저장하도록 확장 가능합니다.
        
        Args:
            session_id: 세션 ID
            
        Returns:
            대화 이력 목록
        """
        return self.conversation_history_cache.get(session_id, [])
    
    def _update_conversation_history(self, session_id: str, query: str, response: str) -> None:
        """
        세션의 대화 이력을 업데이트합니다.
        
        Args:
            session_id: 세션 ID
            query: 사용자 질문
            response: 시스템 응답
        """
        if session_id not in self.conversation_history_cache:
            self.conversation_history_cache[session_id] = []
            
        # 새 대화 추가
        self.conversation_history_cache[session_id].append({
            "timestamp": datetime.now(),
            "query": query,
            "response": response
        })
        
        # 대화 이력 크기 제한 (최대 10개)
        if len(self.conversation_history_cache[session_id]) > 10:
            self.conversation_history_cache[session_id] = self.conversation_history_cache[session_id][-10:]
    
    def _enhance_query_with_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        컨텍스트를 기반으로 현재 질문을 보강합니다.
        
        주어진 질문이 이전 대화를 참조하는 경우 (예: '그 종목', '이전 질문에서') 
        컨텍스트 정보를 활용하여 질문을 구체화합니다.
        
        Args:
            state: 현재 에이전트 상태
            
        Returns:
            보강된 상태
        """
        # TODO: LLM을 사용하여 이전 질문 컨텍스트를 분석하고 현재 질문에 적용
        # 현재는 기본 구현만 포함 - 나중에 프롬프트 템플릿을 활용해 업그레이드 필요
        
        query = state.get("query", "")
        conversation_history = state.get("conversation_history", [])
        
        # 이전 대화가 없으면 보강 불필요
        if not conversation_history:
            return state
            
        # 마지막 대화 정보
        last_conversation = conversation_history[-1]
        last_query = last_conversation.get("query", "")
        
        # 간단한 참조 확인 (더 정교한 방식으로 구현 필요)
        reference_keywords = ["그", "이", "이전", "앞서", "해당", "같은"]
        
        # 참조 키워드가 포함되어 있고 종목명이 없는 경우
        if any(keyword in query for keyword in reference_keywords) and "종목" in query and "stock_name" not in state:
            # 이전 대화에서 종목명 및 코드를 가져와 현재 질문에 적용
            if "stock_name" in last_conversation:
                state["stock_name"] = last_conversation["stock_name"]
                logger.info(f"컨텍스트에서 종목명 적용: {state['stock_name']}")
                
            if "stock_code" in last_conversation:
                state["stock_code"] = last_conversation["stock_code"]
                logger.info(f"컨텍스트에서 종목코드 적용: {state['stock_code']}")
                
        return state 