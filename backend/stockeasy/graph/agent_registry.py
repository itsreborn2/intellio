"""
에이전트 레지스트리

이 모듈은 에이전트 등록 및 관리를 담당하는 AgentRegistry 클래스를 정의합니다.
"""

from typing import Dict, Type, Any, Optional
import time
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
from stockeasy.agents.web_search_agent import WebSearchAgent
# 기존 에이전트들 임포트
from stockeasy.agents.financial_analyzer_agent import FinancialAnalyzerAgent
from stockeasy.agents.industry_analyzer_agent import IndustryAnalyzerAgent
from stockeasy.agents.summarizer_agent import SummarizerAgent
# 대화 컨텍스트 응답 에이전트 임포트
from stockeasy.agents.context_response_agent import ContextResponseAgent
# 매출 및 수주 현황 분석 에이전트 임포트
from stockeasy.agents.revenue_breakdown_agent import RevenueBreakdownAgent
# 기술적 분석 에이전트 임포트
from stockeasy.agents.technical_analyzer_agent import TechnicalAnalyzerAgent
from common.core.config import settings
from langchain.callbacks.tracers import LangChainTracer

# 글로벌 VectorStoreManager 캐시 (애플리케이션 전체에서 공유)
_global_vector_store_cache: Dict[str, Any] = {}
_cache_initialized = False

def get_cached_vector_store_manager(embedding_model_type, namespace: str = None, project_name: str = None):
    """
    글로벌 VectorStoreManager 캐시에서 조회하거나 새로 생성
    
    Args:
        embedding_model_type: 임베딩 모델 타입
        namespace: 네임스페이스
        project_name: 프로젝트 이름
        
    Returns:
        캐시된 또는 새로 생성된 VectorStoreManager 인스턴스
    """
    global _global_vector_store_cache
    
    # 캐시 키 생성 (설정별로 구분)
    cache_key = f"{embedding_model_type}_{namespace}_{project_name}"
    
    if cache_key not in _global_vector_store_cache:
        logger.info(f"새로운 VectorStoreManager 생성: {cache_key}")
        start_time = time.time()
        
        # 동적 임포트로 순환 참조 방지
        from common.services.vector_store_manager import VectorStoreManager
        
        # 새 인스턴스 생성
        vs_manager = VectorStoreManager(
            embedding_model_type=embedding_model_type,
            namespace=namespace,
            project_name=project_name
        )
        
        # 글로벌 캐시에 저장
        _global_vector_store_cache[cache_key] = vs_manager
        
        end_time = time.time()
        logger.info(f"VectorStoreManager 생성 완료: {cache_key} - 소요시간: {end_time - start_time:.2f}초")
    else:
        logger.debug(f"캐시된 VectorStoreManager 사용: {cache_key}")
        
    return _global_vector_store_cache[cache_key]

def warm_up_vector_store_managers():
    """
    자주 사용되는 VectorStoreManager들을 사전 워밍업 (pre-warming)
    애플리케이션 시작 시 또는 필요 시 호출
    """
    global _cache_initialized
    
    if _cache_initialized:
        logger.debug("VectorStoreManager 워밍업 이미 완료됨 - 스킵")
        return
    
    logger.info("자주 사용되는 VectorStoreManager 사전 워밍업 시작")
    warmup_start_time = time.time()
    
    try:
        # 동적 임포트로 순환 참조 방지
        from common.services.embedding_models import EmbeddingModelType
        
        # Stockeasy 프로젝트에서 자주 사용되는 VectorStoreManager 설정들
        common_configs = [
            {
                "embedding_model_type": EmbeddingModelType.OPENAI_3_LARGE,
                "namespace": settings.PINECONE_NAMESPACE_STOCKEASY,
                "project_name": "stockeasy"
            },
            {
                "embedding_model_type": EmbeddingModelType.OPENAI_3_LARGE,
                "namespace": settings.PINECONE_NAMESPACE_STOCKEASY_TELEGRAM,
                "project_name": "stockeasy"
            },
            {
                "embedding_model_type": EmbeddingModelType.OPENAI_3_LARGE,
                "namespace": settings.PINECONE_NAMESPACE_STOCKEASY_INDUSTRY,
                "project_name": "stockeasy"
            },
            {
                "embedding_model_type": EmbeddingModelType.OPENAI_3_LARGE,
                "namespace": settings.PINECONE_NAMESPACE_STOCKEASY_CONFIDENTIAL_NOTE,
                "project_name": "stockeasy"
            }
            # 필요시 다른 자주 사용되는 설정들 추가 가능
        ]
        
        for config in common_configs:
            try:
                # 캐시에 미리 저장 (실제 사용 시점에 빠른 응답을 위해)
                vs_manager = get_cached_vector_store_manager(**config)
                cache_key = f"{config['embedding_model_type']}_{config['namespace']}_{config['project_name']}"
                logger.info(f"VectorStoreManager 워밍업 완료: {cache_key}")
            except Exception as e:
                logger.warning(f"VectorStoreManager 워밍업 실패: {config}, 오류: {e}")
        
        _cache_initialized = True
        
    except Exception as e:
        logger.warning(f"VectorStoreManager 워밍업 중 오류 발생: {e}")
    
    warmup_end_time = time.time()
    warmup_time = warmup_end_time - warmup_start_time
    logger.info(f"VectorStoreManager 워밍업 완료 - 소요시간: {warmup_time:.2f}초")

def clear_vector_store_cache():
    """
    글로벌 VectorStoreManager 캐시 초기화 (주로 테스트용)
    """
    global _global_vector_store_cache, _cache_initialized
    _global_vector_store_cache.clear()
    _cache_initialized = False
    logger.info("글로벌 VectorStoreManager 캐시 초기화 완료")

def get_vector_store_cache_info():
    """
    현재 캐시 상태 정보 반환
    """
    global _global_vector_store_cache, _cache_initialized
    return {
        "cache_size": len(_global_vector_store_cache),
        "cache_keys": list(_global_vector_store_cache.keys()),
        "initialized": _cache_initialized
    }

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
            "revenue_breakdown": RevenueBreakdownAgent,
            "technical_analyzer": TechnicalAnalyzerAgent,
            "knowledge_integrator": KnowledgeIntegratorAgent,
            "summarizer": SummarizerAgent,
            "response_formatter": ResponseFormatterAgent,
            "fallback_manager": FallbackManagerAgent,
            "context_response": ContextResponseAgent,
            "web_search": WebSearchAgent
        }
    
    def initialize_agents(self, db: AsyncSession = None) -> None:
        """
        모든 에이전트 초기화
        
        Args:
            db: 데이터베이스 세션 객체 (선택적)
        """
        import asyncio
        import concurrent.futures
        overall_start_time = time.time()
        logger.info("에이전트 초기화 시작")
        
        # VectorStoreManager 워밍업 (첫 번째 AgentRegistry 초기화 시에만 실행)
        warm_up_vector_store_managers()
        
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
                start_time = time.time()
                self.agents["session_manager"] = SessionManagerAgent(db=db)
                end_time = time.time()
                logger.info(f"세션 관리자 에이전트 초기화 완료 - 소요시간: {end_time - start_time:.2f}초")
            except Exception as e:
                logger.error(f"세션 관리자 에이전트 초기화 중 오류 발생: {e}", exc_info=True)
                # 빈 세션 관리자를 사용하지 않고 오류 발생
                raise ValueError("세션 관리자 에이전트 초기화 실패") from e
        else:
            # 테스트 모드 또는 임시 사용을 위한 더미 SessionManager 처리 방법 구현 필요
            logger.warning("DB 세션 없이 에이전트 초기화 - 세션 관리자는 초기화되지 않습니다.")
        
        # 핵심 에이전트들 (순차적으로 빠르게 초기화)
        core_agents = [
            ("orchestrator", OrchestratorAgent),
            ("question_analyzer", QuestionAnalyzerAgent),
        ]
        
        for agent_name, agent_class in core_agents:
            start_time = time.time()
            agent_instance = agent_class(db=db)
            agent_instance.set_registry(self)  # AgentRegistry 인스턴스 전달
            self.agents[agent_name] = agent_instance
            end_time = time.time()
            logger.info(f"{agent_name} 에이전트 초기화 완료 - 소요시간: {end_time - start_time:.2f}초")
        
        # 검색 및 분석 에이전트들 (순차 초기화 - 서버 리소스 안정성 우선)
        search_analysis_agents = [
            ("telegram_retriever", TelegramRetrieverAgent),
            ("report_analyzer", ReportAnalyzerAgent),
            ("financial_analyzer", FinancialAnalyzerAgent),
            ("industry_analyzer", IndustryAnalyzerAgent),
            ("confidential_analyzer", ConfidentialAnalyzerAgent),
            ("revenue_breakdown", RevenueBreakdownAgent),
            ("technical_analyzer", TechnicalAnalyzerAgent),
            ("web_search", WebSearchAgent),
        ]
        
        # 순차 초기화 (CPU 제한적인 환경에서 안정성 우선)
        batch_start_time = time.time()
        logger.info(f"검색/분석 에이전트 {len(search_analysis_agents)}개 순차 초기화 시작")
        
        for agent_name, agent_class in search_analysis_agents:
            start_time = time.time()
            try:
                agent_instance = agent_class(db=db)
                agent_instance.set_registry(self)  # AgentRegistry 인스턴스 전달
                self.agents[agent_name] = agent_instance
                end_time = time.time()
                logger.info(f"{agent_name} 에이전트 초기화 완료 - 소요시간: {end_time - start_time:.2f}초")
            except Exception as e:
                end_time = time.time()
                logger.error(f"{agent_name} 에이전트 초기화 실패 - 소요시간: {end_time - start_time:.2f}초, 오류: {e}")
        
        batch_end_time = time.time()
        batch_time = batch_end_time - batch_start_time
        logger.info(f"검색/분석 에이전트 순차 초기화 완료 - 총 소요시간: {batch_time:.2f}초")

        # 통합 및 응답 에이전트들 (비교적 가벼운 초기화)
        integration_response_agents = [
            ("knowledge_integrator", KnowledgeIntegratorAgent),
            ("summarizer", SummarizerAgent),
            ("response_formatter", ResponseFormatterAgent),
            ("fallback_manager", FallbackManagerAgent),
            ("context_response", ContextResponseAgent),
        ]
        
        for agent_name, agent_class in integration_response_agents:
            start_time = time.time()
            agent_instance = agent_class(db=db)
            agent_instance.set_registry(self)  # AgentRegistry 인스턴스 전달
            self.agents[agent_name] = agent_instance
            end_time = time.time()
            logger.info(f"{agent_name} 에이전트 초기화 완료 - 소요시간: {end_time - start_time:.2f}초")
        
        overall_end_time = time.time()
        total_time = overall_end_time - overall_start_time
        logger.info(f"총 {len(self.agents)} 개의 에이전트 초기화 완료 - 전체 소요시간: {total_time:.2f}초")
    
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
                agent.set_registry(self)  # AgentRegistry 인스턴스 전달
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

    def get_cached_vector_store_manager(self, embedding_model_type, namespace: str = None, project_name: str = None):
        """
        글로벌 VectorStoreManager 캐시에서 조회 (하위 호환성을 위한 래퍼)
        
        Args:
            embedding_model_type: 임베딩 모델 타입
            namespace: 네임스페이스
            project_name: 프로젝트 이름
            
        Returns:
            캐시된 또는 새로 생성된 VectorStoreManager 인스턴스
        """
        return get_cached_vector_store_manager(
            embedding_model_type=embedding_model_type,
            namespace=namespace,
            project_name=project_name
        )


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