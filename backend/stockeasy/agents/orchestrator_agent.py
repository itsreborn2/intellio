"""
오케스트레이터 에이전트 모듈

이 모듈은 질문 분석 결과를 바탕으로 전체 워크플로우를 설계하고,
데이터 검색 및 통합 과정을 조율하는 OrchestratorAgent 클래스를 구현합니다.
"""

import json
import uuid
from loguru import logger
from typing import Dict, List, Any, Optional, Literal, Union
from datetime import datetime, timedelta

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field, field_validator
from common.utils.util import measure_time_async
from common.services.embedding_models import EmbeddingModelType
from common.services.retrievers.models import RetrievalResult
from common.services.retrievers.semantic import SemanticRetriever, SemanticRetrieverConfig
from common.services.vector_store_manager import VectorStoreManager
from common.services.agent_llm import get_llm_for_agent, get_agent_llm
from stockeasy.models.agent_io import QuestionAnalysisResult
from stockeasy.prompts.orchestrator_prompts import format_orchestrator_prompt
from common.core.config import settings
from stockeasy.agents.base import BaseAgent
from sqlalchemy.ext.asyncio import AsyncSession
from common.models.token_usage import ProjectType

class AgentConfigModel(BaseModel):
    """에이전트 실행 설정"""
    agent_name: str = Field(..., description="에이전트 이름")
    enabled: bool = Field(..., description="활성화 여부")
    priority: int = Field(..., description="우선순위 (1-10)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="에이전트별 매개변수")

    @field_validator('parameters', mode='before')
    @classmethod
    def validate_parameters(cls, v):
        """
        parameters 필드가 문자열 형태로 들어왔을 경우 딕셔너리로 변환합니다.
        """
        if isinstance(v, str):
            # 빈 문자열이나 "{}" 문자열인 경우 빈 딕셔너리로 변환
            if v == "{}" or not v:
                return {}
            # JSON 문자열을 파싱하여 딕셔너리로 변환 시도
            try:
                return json.loads(v)
            except Exception:
                # 파싱 실패 시 빈 딕셔너리로 대체
                return {}
        return v


class ExecutionPlanModel(BaseModel):
    """실행 계획"""
    agents: List[AgentConfigModel] = Field(..., description="실행할 에이전트 목록")
    execution_order: List[str] = Field(..., description="실행 순서")
    integration_strategy: str = Field(..., description="정보 통합 전략")
    expected_output: str = Field(..., description="예상 출력물")
    fallback_strategy: str = Field(..., description="실패 시 대응 전략")


class OrchestratorAgent(BaseAgent):
    """
    워크플로우 설계 및 조율을 담당하는 오케스트레이터 에이전트
    
    이 에이전트는 질문분류기의 결과를 바탕으로 다음을 수행합니다:
    1. 필요한 에이전트 목록 결정
    2. 에이전트 실행 순서 및 우선순위 설정
    3. 데이터 통합 전략 수립
    4. 예외 상황 대응 계획 마련
    """
    
    def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
        """
        오케스트레이터 에이전트 초기화
        
        Args:
            name: 에이전트 이름 (지정하지 않으면 클래스명 사용)
            db: 데이터베이스 세션 객체 (선택적)
        """
        super().__init__(name, db)
        self.agent_llm = get_agent_llm("orchestrator_agent")
        logger.info(f"OrchestratorAgent initialized with provider: {self.agent_llm.get_provider()}, model: {self.agent_llm.get_model_name()}")
        
        self.web_search_threshold = 3
        # 사용 가능한 에이전트 목록
        self.available_agents = {
            "web_search": "웹 검색 에이전트",
            "telegram_retriever": "내부DB 검색 에이전트",
            "report_analyzer": "기업 리포트 검색 및 분석 에이전트",
            "financial_analyzer": "재무 데이터 분석 에이전트",
            "revenue_breakdown": "매출 및 수주 현황 분석 에이전트",
            "industry_analyzer": "산업 동향 분석 에이전트",
            "confidential_analyzer": "비공개 자료 검색 및 분석 에이전트",
            "technical_analyzer": "기술적 분석 에이전트",
            "knowledge_integrator": "정보 통합 에이전트",
            "summarizer": "요약 에이전트",
            "response_formatter": "응답 형식화 에이전트",
            "fallback_manager": "오류 처리 에이전트"
        }
        # VectorStoreManager 지연 초기화 (실제 사용 시점에 초기화)
        self.vs_manager = None
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        질문 분석 결과를 바탕으로 워크플로우를 설계합니다.
        
        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리
            
        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 성능 측정 시작
            start_time = datetime.now()
            logger.info(f"OrchestratorAgent starting processing")
            
            # 상태 업데이트 - 콜백 함수 사용
            if "update_processing_status" in state and "agent_name" in state:
                state["update_processing_status"](state["agent_name"], "processing")
            else:
                # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["orchestrator"] = "processing"
            
            # 질문 분석 결과 추출
            query = state.get("query", "")
            stock_code = state.get("stock_code", "")
            stock_name = state.get("stock_name", "")
            question_analysis:QuestionAnalysisResult = state.get("question_analysis", {})
            
            if not question_analysis:
                logger.warning("Question analysis not found in state")
                self._add_error(state, "질문 분석 결과가 없습니다.")
                return self._create_default_plan(state)
            
            # 필요한 정보 추출
            entities = question_analysis.get("entities", {})
            classification = question_analysis.get("classification", {})
            data_requirements =question_analysis.get("data_requirements", {})
            technical_analysis_needed = data_requirements.get("technical_analysis_needed", False)
            keywords = question_analysis.get("keywords", [])
            detail_level = question_analysis.get("detail_level", "보통")
            
            # 로깅
            logger.info(f"OrchestratorAgent processing query: {query}")
            logger.info(f"Classification: {classification}")
            logger.info(f"Data requirements: {data_requirements}")
            
            
            # user_id 추출
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)
            
            # 계획 변경, 모든 에이전트 다 실행
            # LLM 호출로 계획 수립
            # execution_plan = await self.agent_llm.with_structured_output(ExecutionPlanModel).ainvoke(
            #     prompt,
            #     user_id=user_id,
            #     project_type=ProjectType.STOCKEASY,
            #     db=self.db
            # )
            
            # # 실행 계획 로깅
            # logger.info(f"Execution plan created: {execution_plan.dict()}")
            
            # # 최종 실행 계획 구성
            # plan_id = str(uuid.uuid4())
            # final_plan = {
            #     "plan_id": plan_id,
            #     "created_at": datetime.now(),
            #     "agents": [
            #         {
            #             "agent_name": agent.agent_name,
            #             "enabled": agent.enabled,
            #             "priority": agent.priority,
            #             "parameters": agent.parameters or {}
            #         } 
            #         for agent in execution_plan.agents
            #     ],
            #     "execution_order": execution_plan.execution_order,
            #     "integration_strategy": execution_plan.integration_strategy,
            #     "expected_output": execution_plan.expected_output,
            #     "fallback_strategy": execution_plan.fallback_strategy
            # }
            start_time = datetime.now()
            report_cnt = await self.get_report_cnt(query, stock_code, stock_name, user_id)
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.info(f"[오케스트레이터] 기업리포트 검색 시간: {duration:.2f} 초")
            logger.info(f"[오케스트레이터] Report count: {report_cnt}")
            # 기본 실행 계획 생성 및 상태 업데이트
            if report_cnt >= self.web_search_threshold:
                final_plan = self._create_default_plan(report_cnt, technical_analysis_needed)
                state["question_analysis"]["data_requirements"]["web_search_needed"] = False
            else:
                logger.info("[오케스트레이터] 웹 검색 에이전트를 활성화합니다.")
                final_plan = self._create_default_plan(report_cnt, technical_analysis_needed) # 웹검색 모드 On
                state["question_analysis"]["data_requirements"]["web_search_needed"] = True
            state["execution_plan"] = final_plan
            
            # 처리 상태 업데이트
            if "update_processing_status" in state and "agent_name" in state:
                state["update_processing_status"](state["agent_name"], "completed_with_default_plan")
            else:
                # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["orchestrator"] = "completed_with_default_plan"
            
            # 성능 지표 업데이트
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 메트릭 기록
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["orchestrator"] = {
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "status": "completed",
                "error": None,
                "model_name": self.agent_llm.get_model_name()
            }
            
            logger.info(f"OrchestratorAgent completed in {duration:.2f} seconds")
            return state
            
        except Exception as e:
            logger.exception(f"Error in OrchestratorAgent: {str(e)}")
            self._add_error(state, f"오케스트레이터 에이전트 오류: {str(e)}")
            
            # 기본 실행 계획 생성 및 상태 업데이트
            execution_plan = self._create_default_plan(state)
            state["execution_plan"] = execution_plan
            
            # 처리 상태 업데이트
            if "update_processing_status" in state and "agent_name" in state:
                state["update_processing_status"](state["agent_name"], "completed_with_default_plan")
            else:
                # 기존 방식으로 상태 업데이트 (콜백 함수가 없는 경우)
                state["processing_status"] = state.get("processing_status", {})
                state["processing_status"]["orchestrator"] = "completed_with_default_plan"
            
            return state
    
    def _create_default_plan(self,report_cnt: int, technical_analysis_needed: bool = False) -> Dict[str, Any]:
        """
        기본 실행 계획을 생성합니다 (오류 발생 시 fallback).
        
        Args:
            state: 현재 상태
            
        Returns:
            기본 계획 딕셔너리
        """
        logger.info("Creating default execution plan")
        
        web_search_mode = True if report_cnt < self.web_search_threshold else False

        # 모든 에이전트를 포함하는 기본 계획 생성
        agents_list = []


        # 에이전트별 우선순위 설정        
        if web_search_mode:
            priority_map = {
                "web_search": 10,
                "telegram_retriever": 9,
                "financial_analyzer": 8,
                "revenue_breakdown": 7,
                "knowledge_integrator": 4,
                "summarizer": 3,
                "response_formatter": 2,
                "fallback_manager": 1
            }
            
            # report_cnt > 0인 경우 report_analyzer 추가
            if report_cnt > 0:
                priority_map["report_analyzer"] = 9.5  # telegram_retriever와 financial_analyzer 사이 우선순위
        else:
            priority_map = {
                "telegram_retriever": 10,
                "report_analyzer": 9,
                "financial_analyzer": 8,
                "revenue_breakdown": 7,
                "industry_analyzer": 6,
                "knowledge_integrator": 4,
                "summarizer": 3,
                "response_formatter": 2,
                "fallback_manager": 1
            }
            if report_cnt < 7: # 리포트가 6개 이하이면, 비공개 자료도 검색
                priority_map["confidential_analyzer"] = 5
                priority_map["technical_analyzer"] = 4.5

        if technical_analysis_needed:
            priority_map["technical_analyzer"] = 5.5
        
        # 실행 순서 조정 (일반적인 흐름에 맞게)
        if web_search_mode:
            execution_order = [
                "web_search",
                "telegram_retriever",
                "financial_analyzer",
                "revenue_breakdown",
                "knowledge_integrator",
                "summarizer",
                "response_formatter",
                "fallback_manager"
            ]
            
            # report_cnt > 0인 경우 report_analyzer 추가
            if report_cnt > 0:
                # telegram_retriever 다음에 report_analyzer 삽입
                execution_order.insert(execution_order.index("telegram_retriever") + 1, "report_analyzer")
        else:
            execution_order = [
                "telegram_retriever",
                "report_analyzer",
                "financial_analyzer",
                "revenue_breakdown",
                "industry_analyzer",
                "knowledge_integrator",
                "summarizer",
                "response_formatter",
                "fallback_manager"
            ]
            if report_cnt < 7: # 리포트가 6개 이하이면, 비공개 자료도 검색
                execution_order.insert(execution_order.index("industry_analyzer") + 1, "confidential_analyzer")
                
        if technical_analysis_needed:
            execution_order.insert(execution_order.index("knowledge_integrator") - 1, "technical_analyzer")

        # 기능 테스트 모드용. 기술적 분석 에이전트만 실행
        test_mode = True
        if test_mode:
            priority_map = {
                "technical_analyzer": 6,
                "knowledge_integrator": 4,
                "summarizer": 3,
                "response_formatter": 2,
                "fallback_manager": 1
            }
            execution_order = [
                "technical_analyzer",
                "knowledge_integrator",
                "summarizer",
                "response_formatter",
                "fallback_manager"
            ]
        
         # execution_order에 있는 것만 포함.
        for agent_name in self.available_agents.keys():
            if agent_name in execution_order:
                agents_list.append({
                    "agent_name": agent_name,
                    "enabled": True,
                    "priority": priority_map.get(agent_name, 1),
                    "parameters": {}
                })
        
        

        default_plan = {
            "plan_id": str(uuid.uuid4()),
            "created_at": datetime.now(),
            "agents": agents_list,
            "execution_order": execution_order,
            "integration_strategy": "모든 검색 결과를 종합하여 통합된 응답 생성",
            "expected_output": "다양한 소스의 정보를 종합한 종합적인 분석 결과",
            "fallback_strategy": "일부 에이전트 실패 시에도 가용한 데이터를 기반으로 최선의 답변 제공"
        }
        
        # 상태 객체를 직접 업데이트하지 않고 계획만 반환
        return default_plan
    
    def _add_error(self, state: Dict[str, Any], error_message: str) -> None:
        """
        상태 객체에 오류 정보를 추가합니다.
        
        Args:
            state: 상태 객체
            error_message: 오류 메시지
        """
        state["errors"] = state.get("errors", [])
        state["errors"].append({
            "agent": "orchestrator",
            "error": error_message,
            "type": "processing_error",
            "timestamp": datetime.now(),
            "context": {
                "query": state.get("query", ""),
                "question_analysis": state.get("question_analysis", {})
            }
        })

    @measure_time_async
    async def get_report_cnt(self, query: str, stock_code: str, stock_name: str,
                             user_id: Optional[Union[str, uuid.UUID]] = None) -> int:
        """
        파인콘 DB에서 기업리포트 검색
        
        Args:
            query: 검색 쿼리
            k: 검색할 최대 결과 수
            threshold: 유사도 임계값
            metadata_filter: 메타데이터 필터
            
        Returns:
            검색된 리포트 목록
        """
        try:
            # VectorStoreManager 캐시된 인스턴스 사용 (AgentRegistry에서 관리)
            if self.vs_manager is None:
                logger.debug("글로벌 캐시에서 VectorStoreManager 가져오기 시작")
                
                # 글로벌 캐시 함수를 직접 사용
                from stockeasy.graph.agent_registry import get_cached_vector_store_manager
                
                self.vs_manager = get_cached_vector_store_manager(
                    embedding_model_type=EmbeddingModelType.OPENAI_3_LARGE,
                    namespace=settings.PINECONE_NAMESPACE_STOCKEASY,
                    project_name="stockeasy"
                )
                logger.debug("글로벌 캐시에서 VectorStoreManager 가져오기 완료")
            
            metadata_filter = {}
            # 벡터 스토어 연결
            # vs_manager = VectorStoreManager(
            #     embedding_model_type=EmbeddingModelType.OPENAI_3_LARGE,
            #     project_name="stockeasy",
            #     namespace=settings.PINECONE_NAMESPACE_STOCKEASY
            # )

            # UUID 변환 로직: 문자열이면 UUID로 변환, UUID 객체면 그대로 사용, None이면 None
            if user_id != "test_user":
                parsed_user_id = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            else:
                parsed_user_id = None

            try:
                # 시맨틱 검색 설정. 조건 느슨하게
                semantic_retriever = SemanticRetriever(
                    config=SemanticRetrieverConfig(min_score=0.05,
                                                user_id=parsed_user_id,
                                                project_type=ProjectType.STOCKEASY),
                    vs_manager=self.vs_manager
                )
                
                metadata_filter["stock_code"] = {"$eq": stock_code}
                # 오늘로부터 6개월 이전까지.
                six_months_ago = datetime.now() - timedelta(days=180)
                six_months_ago_str = six_months_ago.strftime('%Y%m%d')
                six_months_ago_int = int(six_months_ago_str)
                metadata_filter["document_date"] = {"$gte": six_months_ago_int}
                # 검색 수행
                retrieval_result: RetrievalResult = await semantic_retriever.retrieve(
                    query=query, 
                    top_k=200,
                    filters=metadata_filter
                )

                # 문서의 개수 카운트. 중복 제거
                unique_file_names = set()
                for doc in retrieval_result.documents:
                    if hasattr(doc, 'metadata') and 'file_name' in doc.metadata:
                        unique_file_names.add(doc.metadata['file_name'])
                
                logger.info(f"{stock_name}({stock_code}) 기업리포트 청크 수 : {len(retrieval_result.documents)} 청크, 문서 개수 : {len(unique_file_names)} 개")

                return len(unique_file_names)
            except Exception as e:
                logger.warning(f"[오케스트레이터, 기업리포트 검색] retriever 실행 중 오류 발생: {str(e)}")
                raise
            finally:
                # 캐시된 VectorStoreManager를 사용하므로 개별 에이전트에서 close하지 않음
                # await semantic_retriever.aclose()
                pass

        except Exception as e:
            logger.error(f"오케스트레이터, 기업리포트 검색 중 오류 발생: {str(e)}", exc_info=True)
            raise