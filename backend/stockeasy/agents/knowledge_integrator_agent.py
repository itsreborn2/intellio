"""
지식 통합기 에이전트 모듈

이 모듈은 여러 검색 에이전트(텔레그램, 기업리포트, 재무제표, 산업 분석)에서 
수집된 정보를 통합하여 응답을 생성하는 통합기 에이전트 클래스를 구현합니다.
"""

import json
from loguru import logger
from typing import Dict, List, Any, Optional, cast, Union
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage
from common.models.token_usage import ProjectType
from stockeasy.models.agent_io import RetrievedAllAgentData
from stockeasy.agents.base import BaseAgent
from sqlalchemy.ext.asyncio import AsyncSession

from langchain_core.output_parsers import JsonOutputParser
#from pydantic.v1 import BaseModel, Field
from pydantic import BaseModel, Field
from common.services.agent_llm import get_llm_for_agent, get_agent_llm
from stockeasy.prompts.knowledge_integrator_prompts import format_knowledge_integrator_prompt
from stockeasy.models.agent_io import IntegratedKnowledge, RetrievedTelegramMessage

# Pydantic 모델 정의
class CoreInsights(BaseModel):
    주요_인사이트1: Optional[str] = Field(default=None, description="통합된 첫 번째 주요 인사이트")
    주요_인사이트2: Optional[str] = Field(default=None, description="통합된 두 번째 주요 인사이트")
    주요_인사이트3: Optional[str] = Field( default=None, description="통합된 세 번째 주요 인사이트")


class ConfidenceAssessment(BaseModel):
    정보_영역1: Optional[str] = Field(default=None, description="첫 번째 정보 영역의 신뢰도 (높음/중간/낮음)")
    정보_영역2: Optional[str] = Field(default=None, description="두 번째 정보 영역의 신뢰도 (높음/중간/낮음)")
    정보_영역3: Optional[str] = Field(default=None, description="세 번째 정보 영역의 신뢰도 (높음/중간/낮음)")


class KnowledgeIntegratorOutput(BaseModel):
    핵심_결론: CoreInsights = Field(..., description="통합된 핵심 결론과 인사이트")
    신뢰도_평가: ConfidenceAssessment = Field(...,  description="정보 영역별 신뢰도 평가")
    불확실_영역: List[str] = Field(..., description="부족하거나 불확실한 정보 영역 목록")
    통합_응답: str = Field(..., description="사용자 질문에 대한 종합적인 답변")


class KnowledgeIntegratorAgent(BaseAgent):
    """여러 검색 에이전트에서 수집된 정보를 통합하는 에이전트"""
    
    def __init__(self, db: AsyncSession = None):
        """
        지식 통합 에이전트의 초기화 메서드
        
        Args:
            db: 데이터베이스 세션
        """
        super().__init__(db=db)
        self.llm, self.model_name, self.provider = get_llm_for_agent("knowledge_integrator_agent")
        self.agent_llm = get_agent_llm("knowledge_integrator_agent")
        self.parser = JsonOutputParser(pydantic_object=KnowledgeIntegratorOutput)
        logger.info(f"KnowledgeIntegratorAgent initialized with provider: {self.provider}, model: {self.model_name}")
        
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        여러 검색 에이전트에서 수집된 정보를 통합하고 응답을 생성합니다.
        
        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리
            
        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 성능 측정 시작
            start_time = datetime.now()
            
            # 현재 사용자 쿼리 및 종목 정보 추출
            query = state.get("query", "")
            
            # 질문 분석 결과 추출
            question_analysis = state.get("question_analysis", {})
            entities = question_analysis.get("entities", {})
            keywords = question_analysis.get("keywords", [])
            important_keywords = ""
            if keywords:
                important_keywords = ", ".join(keywords[:3])  # 상위 3개 키워드 사용

            # 엔티티에서 종목 정보 추출
            stock_code = entities.get("stock_code", state.get("stock_code"))
            stock_name = entities.get("stock_name", state.get("stock_name"))
            
            # 새로운 구조에서 각 에이전트 결과 추출 및 검증
            agent_results = state.get("agent_results", {})
            
            # 중요: 현재 세션이 초기화되었는지 확인 - 세션 ID와 함께 로깅
            session_id = state.get("session_id", "unknown_session")
            if "knowledge_integrator" in agent_results and session_id:
                logger.warning(f"세션 {session_id}에서 knowledge_integrator 에이전트 결과가 이미 존재합니다. 이전 결과를 유지하지 않고 새로운 결과를 생성합니다.")
                # 기존 knowledge_integrator 결과 제거 (다른 에이전트 결과는 유지)
                agent_results.pop("knowledge_integrator", None)
            
            # agent_results에 있는 각 에이전트 결과가 유효한지 검증
            # 1. 관련 없는 종목 정보가 포함된 결과 필터링
            # 2. 이전 세션에서 잘못 포함된 결과 필터링
            validated_agent_results = {}
            
            for agent_name, agent_result in agent_results.items():
                # 기본적인 유효성 검사
                if not agent_result or agent_result.get("status") != "success" or not agent_result.get("data"):
                    continue
                
                # 에이전트 메타데이터 검증 (가능한 경우)
                metadata = agent_result.get("metadata", {})
                result_stock_name = metadata.get("stock_name")
                result_stock_code = metadata.get("stock_code")
                
                # 종목 정보가 있는 경우 현재 종목과 일치하는지 확인
                if (result_stock_name and stock_name and result_stock_name != stock_name) or \
                   (result_stock_code and stock_code and result_stock_code != stock_code):
                    logger.warning(f"에이전트 {agent_name}의 결과가 현재 쿼리의 종목과 일치하지 않습니다. 건너뜁니다.")
                    continue
                
                # 에이전트 결과 검증 통과 - 유효한 결과로 저장
                validated_agent_results[agent_name] = agent_result
            
            # 검증된 에이전트 결과로 원래 agent_results 업데이트
            agent_results = validated_agent_results
            
            # 검증된 agent_results를 상태에 다시 저장 (중요: 이후 다른 에이전트들이 사용할 수 있게)
            state["agent_results"] = agent_results
            
            # 텔레그램 검색 결과 추출
            telegram_results = "정보 없음"
            if "telegram_retriever" in agent_results:
                telegram_agent = agent_results["telegram_retriever"]
                if telegram_agent.get("status") == "success" and telegram_agent.get("data"):
                    telegram_results = self._format_telegram_results(telegram_agent["data"])
            
            # 기업 리포트 결과 추출
            report_results = "정보 없음"
            if "report_analyzer" in agent_results:
                report_agent = agent_results["report_analyzer"]
                if report_agent.get("status") == "success" and report_agent.get("data"):
                    report_results = self._format_report_results(report_agent)#report_agent["data"])
            
            # 재무 분석 결과 추출
            financial_results = "정보 없음"
            if "financial_analyzer" in agent_results:
                financial_agent = agent_results["financial_analyzer"]
                if financial_agent.get("status") == "success" and financial_agent.get("data"):
                    financial_results = self._format_financial_results(financial_agent["data"])
            
            # 산업 분석 결과 추출
            industry_results = "정보 없음"
            if "industry_analyzer" in agent_results:
                industry_agent = agent_results["industry_analyzer"]
                if industry_agent.get("status") == "success" and industry_agent.get("data"):
                    #logger.info(f"산업 분석 결과: {industry_agent['data']}")
                    analysis = industry_agent["data"].get("analysis", {})
                    if analysis:
                        if isinstance(analysis, dict):
                            content = analysis.get("llm_response", "")
                            industry_results = content if content else "산업 분석 결과 없음"
                        else:
                            industry_results = self._format_industry_results(analysis)
                    else:
                        industry_results = self._format_industry_results(industry_agent["data"])

            confidential_results = "정보 없음"
            if "confidential_analyzer" in agent_results:
                confidential_agent = agent_results["confidential_analyzer"]
                if confidential_agent.get("status") == "success" and confidential_agent.get("data"):
                    confidential_results = self._format_confidential_results(confidential_agent)

            
            # 검증 결과 로깅
            logger.info(f"쿼리 '{query}'에 대한 검증된 에이전트 결과: {list(agent_results.keys())}")
            
            # 데이터 중요도 설정 (기본값: 5/10)
            data_importance = state.get("data_importance", {})
            telegram_importance = data_importance.get("telegram_retriever", 5)
            report_importance = data_importance.get("report_analyzer", 5)
            financial_importance = data_importance.get("financial_analyzer", 5)
            industry_importance = data_importance.get("industry_analyzer", 5)
            confidential_importance = data_importance.get("confidential_analyzer", 5)
                
            logger.info(f"KnowledgeIntegratorAgent integrating results for query: {query}")
            
            # 프롬프트 준비
            prompt = format_knowledge_integrator_prompt(
                query=query,
                stock_name=stock_name,
                stock_code=stock_code,
                keywords=important_keywords,
                telegram_results=telegram_results,
                report_results=report_results,
                financial_results=financial_results,
                industry_results=industry_results,
                confidential_results=confidential_results,
                telegram_importance=telegram_importance,
                report_importance=report_importance,
                financial_importance=financial_importance,
                industry_importance=industry_importance,
                confidential_importance=confidential_importance
            )
            
            # user_id 추출
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)
            
            # LLM 호출로 통합 수행
            #integration_result = await self.chain.ainvoke(prompt)
            integration_result = await self.agent_llm.with_structured_output(KnowledgeIntegratorOutput).ainvoke(
                prompt,
                user_id=user_id,
                project_type=ProjectType.STOCKEASY,
                db=self.db
            )
            logger.info("Knowledge integration completed successfully")
            
            # 형식 변환: Pydantic 모델을 IntegratedKnowledge 타입으로 변환
            # 핵심 인사이트 변환
            core_insights = []
            if integration_result.핵심_결론.주요_인사이트1:
                core_insights.append(integration_result.핵심_결론.주요_인사이트1)
            if integration_result.핵심_결론.주요_인사이트2:
                core_insights.append(integration_result.핵심_결론.주요_인사이트2)
            if integration_result.핵심_결론.주요_인사이트3:
                core_insights.append(integration_result.핵심_결론.주요_인사이트3)
            
            # 신뢰도 평가 정보를 analysis 딕셔너리에 포함
            confidence_info = integration_result.신뢰도_평가.dict()
            
            # 통합된 지식 베이스 생성 (IntegratedKnowledge 타입 형식으로)
            integrated_knowledge: IntegratedKnowledge = {
                "integrated_response": integration_result.통합_응답,
                "core_insights": core_insights,
                "facts": [],  # 현재 모델에서는 별도 facts를 제공하지 않음
                "opinions": [],  # 현재 모델에서는 별도 opinions를 제공하지 않음
                "analysis": {
                    "confidence_assessment": confidence_info,
                    "uncertain_areas": integration_result.불확실_영역
                },
                "sources": {
                    "telegram": self._extract_sources(agent_results, "telegram_retriever"),
                    "reports": self._extract_sources(agent_results, "report_analyzer"),
                    "financial": self._extract_sources(agent_results, "financial_analyzer"),
                    "industry": self._extract_sources(agent_results, "industry_analyzer")
                }
            }
            
            # 통합된 지식 저장 # 굳이 AgentState 최상위에 둘 필요없음.
            #state["integrated_knowledge"] = integrated_knowledge
            
            # 추가 정보 (API 호환성 유지)
            #state["integrated_response"] = integration_result.통합_응답
            
            # 에이전트 결과 업데이트
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["knowledge_integrator"] = {
                "agent_name": "knowledge_integrator",
                "status": "success",
                "data": integrated_knowledge,
                # "data": {
                #     "integrated_response": integration_result.통합_응답,
                #     "core_insights": core_insights,
                #     "uncertain_areas": integration_result.불확실_영역,
                #     "confidence_assessment": confidence_info
                # },
                "error": None,
                "execution_time": (datetime.now() - start_time).total_seconds(),
                "metadata": {
                    "total_sources": len(self._extract_sources(agent_results, "telegram_retriever")) +
                                    len(self._extract_sources(agent_results, "report_analyzer")) +
                                    len(self._extract_sources(agent_results, "financial_analyzer")) +
                                    len(self._extract_sources(agent_results, "industry_analyzer"))
                }
            }
            
            # 성능 지표 업데이트
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 메트릭 기록
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["knowledge_integrator"] = {
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "status": "completed",
                "error": None,
                "model_name": self.model_name
            }
            
            # 처리 상태 업데이트
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["knowledge_integrator"] = "completed"
            
            logger.info(f"KnowledgeIntegratorAgent completed in {duration:.2f} seconds")
            
            # 오류 제거 (성공적으로 처리됨)
            if "error" in state:
                del state["error"]
                
            return state
            
        except Exception as e:
            logger.exception(f"Error in KnowledgeIntegratorAgent: {str(e)}")
            
            # 오류 정보 추가
            state["errors"] = state.get("errors", [])
            state["errors"].append({
                "agent": "knowledge_integrator",
                "error": str(e),
                "type": "processing_error",
                "timestamp": datetime.now(),
                "context": {"query": state.get("query", "")}
            })
            
            # 에이전트 결과 업데이트 (오류)
            state["agent_results"] = state.get("agent_results", {})
            state["agent_results"]["knowledge_integrator"] = {
                "agent_name": "knowledge_integrator",
                "status": "failed",
                "data": {},
                "error": str(e),
                "execution_time": (datetime.now() - start_time).total_seconds() if 'start_time' in locals() else 0,
                "metadata": {}
            }
            
            # 처리 상태 업데이트
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["knowledge_integrator"] = "failed"
            
            # 응답에 오류 메시지 추가
            state["integrated_response"] = "죄송합니다. 정보를 통합하는 중 오류가 발생했습니다."
            return state
            
    def _format_telegram_results(self, telegram_data: Dict[str, Any]) -> str:
        """텔레그램 결과를 문자열로 포맷팅"""
        if not telegram_data:
            return "내부DB 검색 결과 없음"
        
        summary = telegram_data.get("summary", "")
        messages: List[RetrievedTelegramMessage] = telegram_data.get("messages", [])
        
        # "summary": summary,
        # "messages": messages
        formatted = ""
        if summary:
            formatted += f"내부DB 검색 결과 요약:\n{summary}\n"
        else:
            if messages:
                formatted += "내부DB 검색 결과 상세:\n"
                for i, msg in enumerate(messages):
                    # 채널명 삭제.
                    #formatted += f"[{i+1}] 출처: {msg.get('channel_name', '알 수 없음')}\n"
                    formatted += f"내용: {msg.get('content', '내용 없음')}\n"
                    if msg.get('message_created_at'):
                        formatted += f"작성일: {msg.get('message_created_at')}\n"
                    formatted += "---\n"
            else:
                formatted += "내부DB 검색 결과 없음\n"
            
        return formatted
    
    def _format_report_results(self, report_agent: List[Dict[str, Any]]) -> str:
        """기업 리포트 결과를 문자열로 포맷팅"""

        report_data = report_agent["data"]
        if not report_data:
            return "기업 리포트 검색 결과 없음"
        analysis = report_data.get("analysis", None)
        searched_reports = report_data.get("searched_reports", [])
            
        formatted = f"기업 리포트 검색 결과[{len(searched_reports)}개]:\n"
        if analysis: # 분석결과가 있으면 결과만 리턴.
            #analysis = report["analysis"]
            # llm_response 키 사용 (report_analyzer_agent의 실제 출력 키)
            if "llm_response" in analysis:
                formatted += f"분석 결과: {analysis.get('llm_response', '')}\n"
            # 투자 의견 정보 추가
            if "investment_opinions" in analysis and analysis["investment_opinions"]:
                opinions = analysis["investment_opinions"]
                formatted += "투자의견: "
                for op in opinions[:2]:  # 처음 2개만 표시
                    formatted += f"{op.get('source', '')}: {op.get('opinion', '없음')} (목표가: {op.get('target_price', '없음')}), "
                formatted += "\n"
            # 종합 의견이 있는 경우 추가
            if "opinion_summary" in analysis and analysis["opinion_summary"]:
                formatted += f"종합의견: {analysis.get('opinion_summary', '')}\n"
        else:
            # 분석결과가 없다면, 찾은 문서 내용을 리턴.
            for i, report in enumerate(searched_reports):
                formatted += f"[{i+1}] 제목: {report.get('title', '제목 없음')}\n"
                formatted += f"출처: {report.get('source', '알 수 없음')}\n"
                formatted += f"날짜: {report.get('date', '날짜 정보 없음')}\n"
                content = report.get('content', '내용 없음')
                formatted += f"내용: {content}\n"
                
                   
                formatted += "---\n"
            
        return formatted
    def _format_confidential_results(self, confidential_agent: List[Dict[str, Any]]) -> str:
        """기업 리포트 결과를 문자열로 포맷팅"""

        confidential_data = confidential_agent["data"]
        if not confidential_data:
            return "비공개 자료 검색 결과 없음"
        analysis = confidential_data.get("analysis", None)
        searched_reports = confidential_data.get("searched_reports", [])
            
        formatted = f"비공개 자료 검색 결과[{len(searched_reports)}개]:\n"
        if analysis: # 분석결과가 있으면 결과만 리턴.
            if "llm_response" in analysis:
                formatted += f"분석 결과: {analysis.get('llm_response', '')}\n"
        else:
            # 분석결과가 없다면, 찾은 문서 내용을 리턴.
            for i, report in enumerate(searched_reports):
                formatted += f"[{i+1}] 제목: {report.get('title', '제목 없음')}\n"
                formatted += f"출처: 비공개자료\n"
                #formatted += f"날짜: {report.get('date', '날짜 정보 없음')}\n"
                content = report.get('content', '내용 없음')
                formatted += f"내용: {content}\n"
                
                formatted += "---\n"
            
        return formatted
    
    def _format_financial_results(self, financial_data: Dict[str, Any]) -> str:
        """
        재무 분석 결과를 문자열로 포맷팅합니다.
        
        Args:
            financial_data: {
                "llm_response": str,
                "extracted_data": {
                    "stock_code": str,
                    "stock_name": str,
                    "report_count": int,
                    "date_range": {
                        "start_date": str,
                        "end_date": str,
                        "included_years": List[int]
                    }
                },
                "raw_financial_data": List[Dict]
            }
        """
        if not financial_data:
            return "재무 분석 결과 없음"
            
        formatted = "재무 분석 결과:\n"
        
        # LLM 분석 결과 추가
        llm_response = financial_data.get("llm_response", "")
        if llm_response and llm_response != "분석 결과를 생성할 수 없습니다.":
            formatted += f"{llm_response}\n\n"
            
        # 추출된 데이터 정보 추가
        extracted_data = financial_data.get("extracted_data", {})
        if extracted_data:
            date_range = extracted_data.get("date_range", {})
            if date_range:
                start_date = date_range.get("start_date", "")
                end_date = date_range.get("end_date", "")
                if start_date and end_date:
                    formatted += f"분석 기간: {start_date} ~ {end_date}\n"
                # 후속 처리를 위해 included_years 정보도 유지
                included_years = date_range.get("included_years", [])
                if included_years:
                    formatted += f"포함된 연도: {', '.join(map(str, included_years))}\n"
                    
            report_count = extracted_data.get("report_count", 0)
            if report_count:
                formatted += f"분석된 보고서 수: {report_count}개\n\n"
                
        # 원본 재무 데이터 추가 (최대 3개)
        raw_data = financial_data.get("raw_financial_data", [])
        if raw_data:
            formatted += "상세 보고서 정보:\n"
            for i, report in enumerate(raw_data, 1):
                formatted += f"[{i}] {report.get('source', '보고서 정보 없음')}\n"
                if report.get('financial_indicators'):
                    formatted += "주요 지표:\n"
                    for metric, value in report['financial_indicators'].items():
                        formatted += f"- {metric}: {value[:200] if len(value) > 200 else value}\n"
                formatted += "---\n"
                
        return formatted.strip()
    
    def _format_industry_results(self, industry_data: Union[List[Dict[str, Any]], Dict[str, Any], str]) -> str:
        """산업 분석 결과를 문자열로 포맷팅"""
        # 문자열인 경우 그대로 반환
        if isinstance(industry_data, str):
            return industry_data
            
        # 데이터가 없는 경우
        if not industry_data:
            return "산업 분석 결과 없음"
            
        # 딕셔너리인 경우
        if isinstance(industry_data, dict):
            analysis = industry_data.get("analysis", {})
            content = analysis.get("llm_response", "")
            return content
            
        # 리스트인 경우 첫 번째 항목 처리
        if isinstance(industry_data, list) and len(industry_data) > 0:
            first_item = industry_data[0]
            if isinstance(first_item, dict):
                analysis = first_item.get("analysis", {})
                if isinstance(analysis, dict):
                    content = analysis.get("llm_response", "")
                    if content:
                        return content
                        
        # 다른 형식의 경우 기본 문자열 변환 시도
        try:
            return str(industry_data)
        except:
            return "산업 분석 결과 포맷팅 오류"
    
    def _extract_sources(self, agent_results: Dict[str, Any], agent_name: str) -> List[str]:
        """에이전트 결과에서 소스 목록 추출"""
        sources = []
        if agent_name in agent_results:
            agent_data = agent_results[agent_name]
            if agent_data.get("status") == "success" and agent_data.get("data"):
                for item in agent_data["data"]:
                    if "source" in item:
                        sources.append(item["source"])
                    elif "title" in item:
                        sources.append(item["title"])
        return sources 