"""
오케스트레이터 에이전트

이 모듈은 전체 워크플로우를 조정하고 사용자 질문에 따라 적절한 처리 경로를 결정하는 에이전트를 정의합니다.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from stockeasy.agents.base import BaseAgent
from stockeasy.models.agent_io import AgentState
from common.core.config import settings


class OrchestratorAgent(BaseAgent):
    """워크플로우 조정 에이전트"""
    
    def __init__(self):
        """에이전트 초기화"""
        super().__init__("orchestrator")
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL_NAME,
            temperature=0.0,
            api_key=settings.OPENAI_API_KEY
        )
        self.parser = JsonOutputParser()
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        쿼리 유형에 따라 적절한 에이전트를 선택하고 실행 계획을 수립합니다.

        Args:
            state: 현재 상태

        Returns:
            업데이트된 상태
        """
        try:
            # 오케스트레이션 시작 시간 기록
            start_time = datetime.now()
            
            # 쿼리 타입 확인
            classification = state.get("classification", {})
            question_type = classification.get("질문주제", 4)  # 기본값: 기타
            answer_level = classification.get("답변수준", 1)  # 기본값: 간단 설명
            
            # 필요한 에이전트 결정
            needed_agents = []
            
            # 종목 기본 정보 (0)
            if question_type == 0:
                needed_agents = ["telegram_retriever", "report_analyzer"]
            
            # 종목 전망 (1)
            elif question_type == 1:
                needed_agents = ["telegram_retriever", "report_analyzer", "financial_analyzer"]
            
            # 재무 정보 (2)
            elif question_type == 2:
                needed_agents = ["financial_analyzer", "telegram_retriever"]
            
            # 산업 동향 (3)
            elif question_type == 3:
                needed_agents = ["telegram_retriever", "industry_analyzer", "report_analyzer"]
            
            # 기타 질문 (4)
            else:
                needed_agents = ["telegram_retriever", "report_analyzer"]
            
            # 답변 수준이 높은 경우 모든 데이터 소스 사용
            if answer_level >= 2:  # 종합적 판단 또는 전문가 수준
                # 기업리포트 분석 추가
                if "report_analyzer" not in needed_agents:
                    needed_agents.append("report_analyzer")
                
                # 재무정보 분석 추가 (특정 조건에서만)
                if "financial_analyzer" not in needed_agents and question_type != 3:
                    needed_agents.append("financial_analyzer")
            
            # 추가 처리 로직 (향후 구현)
            
            # 결과 반환
            return {
                **state,
                "needed_agents": needed_agents,
                "orchestration_time": (datetime.now() - start_time).total_seconds(),
                "processing_status": {
                    **state.get("processing_status", {}),
                    "orchestrator": "completed"
                }
            }
            
        except Exception as e:
            logger.error(f"워크플로우 조정 중 오류 발생: {e}", exc_info=True)
            return {
                **state,
                "errors": state.get("errors", []) + [{
                    "agent": self.get_name(),
                    "error": str(e),
                    "type": type(e).__name__,
                    "timestamp": datetime.now()
                }],
                "processing_status": {
                    **state.get("processing_status", {}),
                    "orchestrator": "error"
                }
            }
    
    def _select_agents_for_query(self, query: str) -> List[str]:
        """
        질문에 따라 활성화할 에이전트를 선택합니다.
        
        Args:
            query: 사용자 질문
            
        Returns:
            선택된 에이전트 목록
        """
        # 기본적으로 모든
        selected_agents = ["question_analyzer", "telegram_retriever", "knowledge_integrator", "summarizer"]
        
        # 향후 구현: 질문 내용에 따라 에이전트 선택 로직
        
        return selected_agents
    
    def _prioritize_data_sources(self, query: str, stock_code: Optional[str] = None, 
                                stock_name: Optional[str] = None) -> Dict[str, int]:
        """
        질문에 따라 데이터 소스의 우선순위를 결정합니다.
        
        Args:
            query: 사용자 질문
            stock_code: 종목 코드
            stock_name: 종목명
            
        Returns:
            데이터 소스별 우선순위
        """
        # 기본 우선순위
        priorities = {
            "telegram": 1,
            "report": 2,
            "financial": 3,
            "industry": 4
        }
        
        # 재무 관련 키워드
        financial_keywords = ["재무", "실적", "매출", "영업이익", "순이익", "부채", "자산", "ROE", "PER", "PBR"]
        # 산업 관련 키워드
        industry_keywords = ["산업", "섹터", "시장", "트렌드", "경쟁사", "시장점유율", "산업구조"]
        # 전망 관련 키워드
        outlook_keywords = ["전망", "목표가", "투자의견", "미래", "성장성", "기대", "예상"]
        
        # 키워드 기반 우선순위 조정
        for keyword in financial_keywords:
            if keyword in query:
                priorities["financial"] = 1
                priorities["telegram"] = 2
                break
                
        for keyword in industry_keywords:
            if keyword in query:
                priorities["industry"] = 1
                priorities["telegram"] = 2
                break
                
        for keyword in outlook_keywords:
            if keyword in query:
                priorities["report"] = 1
                priorities["telegram"] = 2
                break
        
        return priorities
    
    
class SessionManagerAgent(BaseAgent):
    """사용자 세션을 관리하는 에이전트"""
    
    def __init__(self):
        """에이전트 초기화"""
        super().__init__("session_manager")
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        사용자 세션을 관리합니다.
        
        Args:
            state: 현재 상태
            
        Returns:
            업데이트된 상태 (사용자 컨텍스트 및 대화 이력 포함)
        """
        try:
            query = state.get("query", "")
            session_id = state.get("session_id", "")
            
            if not query or not session_id:
                return {
                    **state,
                    "errors": state.get("errors", []) + [{
                        "agent": self.get_name(),
                        "error": "세션 정보가 부족합니다.",
                        "type": "InvalidSessionError",
                        "timestamp": datetime.now()
                    }],
                    "processing_status": {
                        **state.get("processing_status", {}),
                        "session_manager": "error"
                    }
                }
            
            # 기존 대화 이력 로딩 (향후 DB 연동 구현)
            conversation_history = state.get("conversation_history", [])
            
            # 사용자 컨텍스트 로딩 또는 초기화
            user_context = state.get("user_context", {})
            if not user_context:
                user_context = {
                    "last_queries": [],
                    "preferred_stocks": [],
                    "interests": []
                }
            
            # 현재 쿼리 추가
            conversation_history.append({
                "role": "user",
                "content": query,
                "timestamp": datetime.now().isoformat()
            })
            
            # 최근 쿼리 업데이트
            last_queries = user_context.get("last_queries", [])
            last_queries.append(query)
            if len(last_queries) > 5:  # 최대 5개 쿼리 유지
                last_queries = last_queries[-5:]
            user_context["last_queries"] = last_queries
            
            # 상태 업데이트
            return {
                **state,
                "conversation_history": conversation_history,
                "user_context": user_context,
                "processing_status": {
                    **state.get("processing_status", {}),
                    "session_manager": "completed"
                }
            }
            
        except Exception as e:
            logger.error(f"세션 관리 중 오류 발생: {e}", exc_info=True)
            return {
                **state,
                "errors": state.get("errors", []) + [{
                    "agent": self.get_name(),
                    "error": str(e),
                    "type": type(e).__name__,
                    "timestamp": datetime.now()
                }],
                "processing_status": {
                    **state.get("processing_status", {}),
                    "session_manager": "error"
                }
            }
    
    def _extract_user_interests(self, query: str, history: List[Dict[str, Any]]) -> List[str]:
        """
        사용자 관심사를 추출합니다.
        
        Args:
            query: 현재 질문
            history: 대화 이력
            
        Returns:
            관심사 목록
        """
        # 향후 구현: 사용자 관심사 추출 로직
        return [] 