"""
에이전트 레지스트리

이 모듈은 에이전트 등록 및 관리를 담당하는 AgentRegistry 클래스를 정의합니다.
"""

from typing import Dict, Type, Any, Optional
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from stockeasy.agents.confidential_analyzer_agent import ConfidentialAnalyzerAgent
from stockeasy.agents.base import BaseAgent
from stockeasy.agents.session_manager_agent import SessionManagerAgent
# 새로 구현한 에이전트들 임포트
from stockeasy.agents.orchestrator_agent import OrchestratorAgent
from stockeasy.agents.question_analyzer_agent import QuestionAnalyzerAgent
from stockeasy.agents.knowledge_integrator_agent import KnowledgeIntegratorAgent
from stockeasy.agents.response_formatter_agent import ResponseFormatterAgent
from stockeasy.agents.fallback_manager_agent import FallbackManagerAgent
from stockeasy.agents.telegram_retriever_agent import TelegramRetrieverAgent
from stockeasy.agents.report_analyzer_agent import ReportAnalyzerAgent
# 기존 에이전트들 임포트
from stockeasy.agents.financial_analyzer_agent import FinancialAnalyzerAgent
from stockeasy.agents.industry_analyzer_agent import IndustryAnalyzerAgent
from stockeasy.agents.summarizer_agent import SummarizerAgent
from common.core.config import settings
from langchain.callbacks.tracers import LangChainTracer

class AgentRegistry:
    """에이전트 등록 및 관리 클래스"""
    
    def __init__(self):
        """에이전트 레지스트리 초기화"""
        self.agents: Dict[str, BaseAgent] = {}
        self.graph = None
        self.db_session: Optional[AsyncSession] = None
        self.agent_classes: Dict[str, Type[BaseAgent]] = {
            "session_manager": SessionManagerAgent,
            "orchestrator": OrchestratorAgent,
            "question_analyzer": QuestionAnalyzerAgent,
            "telegram_retriever": TelegramRetrieverAgent,
            "report_analyzer": ReportAnalyzerAgent,
            "financial_analyzer": FinancialAnalyzerAgent,
            "industry_analyzer": IndustryAnalyzerAgent,
            "confidential_analyzer": ConfidentialAnalyzerAgent,
            "knowledge_integrator": KnowledgeIntegratorAgent,
            "summarizer": SummarizerAgent,
            "response_formatter": ResponseFormatterAgent,
            "fallback_manager": FallbackManagerAgent
        }
    
    def initialize_agents(self, db: AsyncSession = None) -> None:
        """
        모든 에이전트 초기화
        
        Args:
            db: 데이터베이스 세션 객체 (선택적)
        """
        logger.info("에이전트 초기화 시작")
        if settings.ENV == "production":
            #os.environ["LANGCHAIN_PROJECT"] = "stockeasy_server_agents"
            tracer = LangChainTracer(project_name="stockeasy_server_agents")
        else:
            #os.environ["LANGCHAIN_PROJECT"] = "stockeasy_dev"
            tracer = LangChainTracer(project_name="stockeasy_dev")    
        self.db_session = db
        
        # SessionManager는 DB 세션이 필요하므로 별도 처리
        if db is not None:
            try:
                self.agents["session_manager"] = SessionManagerAgent(db=db)
                logger.info("세션 관리자 에이전트가 DB 세션과 함께 초기화되었습니다.")
            except Exception as e:
                logger.error(f"세션 관리자 에이전트 초기화 중 오류 발생: {e}", exc_info=True)
                # 빈 세션 관리자를 사용하지 않고 오류 발생
                raise ValueError("세션 관리자 에이전트 초기화 실패") from e
        else:
            # 테스트 모드 또는 임시 사용을 위한 더미 SessionManager 처리 방법 구현 필요
            logger.warning("DB 세션 없이 에이전트 초기화 - 세션 관리자는 초기화되지 않습니다.")
        
        # 기타 에이전트 초기화 - 모든 에이전트에 DB 세션 전달
        self.agents["orchestrator"] = OrchestratorAgent(db=db)
        self.agents["question_analyzer"] = QuestionAnalyzerAgent(db=db)
        
        # 검색 및 분석 에이전트 초기화
        self.agents["telegram_retriever"] = TelegramRetrieverAgent(db=db)
        self.agents["report_analyzer"] = ReportAnalyzerAgent(db=db)
        
        # 기존 검색 및 분석 에이전트 초기화
        self.agents["financial_analyzer"] = FinancialAnalyzerAgent(db=db)
        self.agents["industry_analyzer"] = IndustryAnalyzerAgent(db=db)
        self.agents["confidential_analyzer"] = ConfidentialAnalyzerAgent(db=db)

        # 통합 및 요약 에이전트 초기화
        self.agents["knowledge_integrator"] = KnowledgeIntegratorAgent(db=db)
        self.agents["summarizer"] = SummarizerAgent(db=db)
        
        # 응답 및 오류 처리 에이전트 초기화
        self.agents["response_formatter"] = ResponseFormatterAgent(db=db)
        self.agents["fallback_manager"] = FallbackManagerAgent(db=db)
        
        logger.info(f"총 {len(self.agents)} 개의 에이전트가 초기화되었습니다.")
    
    def initialize_graph(self, db: AsyncSession = None):
        """
        그래프 초기화 및 에이전트 연결
        
        Args:
            db: 데이터베이스 세션 객체 (선택적)
            
        Returns:
            초기화된 그래프 인스턴스
        """
        try:
            # 에이전트가 초기화되지 않았으면 초기화
            if not self.agents:
                self.initialize_agents(db)
            
            # 순환 참조 방지를 위해 런타임에 임포트
            from stockeasy.graph.stock_analysis_graph import StockAnalysisGraph
            
            # 그래프 초기화
            logger.info("Stock Analysis Graph 초기화 시작")
            self.graph = StockAnalysisGraph(self.agents)
            
            # DB 세션 등록
            if db is not None:
                self.graph.register_agents(self.agents, db)
            
            logger.info("Stock Analysis Graph 초기화 완료")
            
            return self.graph
            
        except Exception as e:
            logger.exception(f"그래프 초기화 중 오류 발생: {e}")
            return None

    def get_graph(self, db: AsyncSession = None):
        """
        초기화된 그래프 인스턴스 조회
        
        Args:
            db: 데이터베이스 세션 객체 (선택적)
            
        Returns:
            그래프 인스턴스 또는 None
        """
        if not self.graph:
            return self.initialize_graph(db)
        return self.graph
    
    def get_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """
        등록된 에이전트 인스턴스 조회
        
        Args:
            agent_name: 에이전트 이름
            
        Returns:
            등록된 에이전트 인스턴스 또는 None
        """
        if agent_name in self.agents:
            return self.agents[agent_name]
        
        # 에이전트가 등록되어 있지 않으면 자동 생성 시도
        if agent_name in self.agent_classes:
            logger.info(f"에이전트 '{agent_name}' 자동 생성 시도")
            try:
                # DB 세션을 모든 에이전트에 전달
                agent = self.agent_classes[agent_name](db=self.db_session)
                self.agents[agent_name] = agent
                return agent
            except Exception as e:
                logger.error(f"에이전트 '{agent_name}' 생성 중 오류 발생: {e}")
                return None
        
        logger.warning(f"요청된 에이전트 '{agent_name}'를 찾을 수 없습니다.")
        return None
    
    def register_agent(self, agent_name: str, agent: BaseAgent) -> None:
        """
        신규 에이전트 등록
        
        Args:
            agent_name: 에이전트 이름
            agent: 에이전트 인스턴스
        """
        if agent_name in self.agents:
            logger.warning(f"에이전트 '{agent_name}'가 이미 등록되어 있습니다. 덮어쓰기를 수행합니다.")
        
        self.agents[agent_name] = agent
        logger.info(f"에이전트 '{agent_name}'가 등록되었습니다.")
    
    def unregister_agent(self, agent_name: str) -> bool:
        """
        에이전트 등록 해제
        
        Args:
            agent_name: 에이전트 이름
            
        Returns:
            성공 여부
        """
        if agent_name in self.agents:
            del self.agents[agent_name]
            logger.info(f"에이전트 '{agent_name}'가 등록 해제되었습니다.")
            return True
        
        logger.warning(f"등록 해제할 에이전트 '{agent_name}'를 찾을 수 없습니다.")
        return False
    
    def get_available_agents(self) -> Dict[str, str]:
        """
        사용 가능한 모든 에이전트 목록 조회
        
        Returns:
            에이전트 이름과 클래스 이름 매핑
        """
        return {
            name: agent.__class__.__name__ 
            for name, agent in self.agents.items()
        }
    
    def reset(self) -> None:
        """모든 에이전트 초기화"""
        self.agents.clear()
        logger.info("에이전트 레지스트리가 초기화되었습니다.")
        self.initialize_agents(self.db_session)


# 글로벌 헬퍼 함수들
def get_agents(db: AsyncSession = None):
    """
    에이전트 딕셔너리 생성 및 반환
    
    Args:
        db: 데이터베이스 세션 객체 (선택적)
        
    Returns:
        에이전트 딕셔너리
    """
    registry = AgentRegistry()
    registry.initialize_agents(db)
    return registry.agents

def get_graph(db: AsyncSession = None):
    """
    새로운 Stock Analysis Graph 인스턴스 생성 및 반환
    
    Args:
        db: 데이터베이스 세션 객체 (선택적)
        
    Returns:
        StockAnalysisGraph 인스턴스
    """
    registry = AgentRegistry()
    return registry.get_graph(db)

def get_agent(agent_name: str, db: AsyncSession = None) -> Optional[BaseAgent]:
    """
    특정 에이전트 인스턴스 생성 및 반환
    
    Args:
        agent_name: 에이전트 이름
        db: 데이터베이스 세션 객체 (선택적)
        
    Returns:
        에이전트 인스턴스 또는 None
    """
    registry = AgentRegistry()
    registry.db_session = db
    return registry.get_agent(agent_name) 