"""
지식 통합기 에이전트 모듈

이 모듈은 여러 검색 에이전트(텔레그램, 기업리포트, 재무제표, 산업 분석)에서 
수집된 정보를 통합하여 응답을 생성하는 통합기 에이전트 클래스를 구현합니다.
"""

import json
from loguru import logger
from typing import Dict, List, Any, Optional, cast
from datetime import datetime

from langchain_core.messages import HumanMessage

from langchain_core.output_parsers import JsonOutputParser
#from pydantic.v1 import BaseModel, Field
from pydantic import BaseModel, Field
from common.services.agent_llm import get_llm_for_agent
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


class KnowledgeIntegratorAgent:
    """
    여러 검색 에이전트에서 수집된 정보를 통합하는 지식 통합기 에이전트 클래스
    """
    
    def __init__(self):
        """
        지식 통합기 에이전트 초기화
        
        Args:
            model_name: 사용할 OpenAI 모델 이름
            temperature: 모델 출력의 다양성 조절 파라미터
        """
        #self.llm = ChatOpenAI(model_name=model_name, temperature=temperature, api_key=settings.OPENAI_API_KEY)
        self.llm, self.model_name, self.provider = get_llm_for_agent("knowledge_integrator_agent")
        self.parser = JsonOutputParser(pydantic_object=KnowledgeIntegratorOutput)
        #self.chain = self.llm.with_structured_output(KnowledgeIntegratorOutput,method="function_calling")
        # execution_plan = await self.llm.with_structured_output(ExecutionPlanModel,method="function_calling").ainvoke(
        #         [HumanMessage(content=prompt)]
        #     )
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
            if keywords:
                important_keywords = ", ".join(keywords[:3])  # 상위 3개 키워드 사용

            # 엔티티에서 종목 정보 추출
            stock_code = entities.get("stock_code", state.get("stock_code"))
            stock_name = entities.get("stock_name", state.get("stock_name"))
            
            # 새로운 구조에서 각 에이전트 결과 추출
            agent_results = state.get("agent_results", {})
            
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
                    industry_results = self._format_industry_results(industry_agent["data"])
            
            # 데이터 중요도 설정 (기본값: 5/10)
            data_importance = state.get("data_importance", {})
            telegram_importance = data_importance.get("telegram_retriever", 5)
            report_importance = data_importance.get("report_analyzer", 5)
            financial_importance = data_importance.get("financial_analyzer", 5)
            industry_importance = data_importance.get("industry_analyzer", 5)
            
                
            logger.info(f"KnowledgeIntegratorAgent integrating results for query: {query}")
            
            # 프롬프트 준비
            prompt = format_knowledge_integrator_prompt(
                query=query,
                stock_name=stock_name,
                stock_code=stock_code,
                keywords=important_keywords if important_keywords else "",
                telegram_results=telegram_results,
                report_results=report_results,
                financial_results=financial_results,
                industry_results=industry_results,
                telegram_importance=telegram_importance,
                report_importance=report_importance,
                financial_importance=financial_importance,
                industry_importance=industry_importance
            )
            
            # LLM 호출로 통합 수행
            #integration_result = await self.chain.ainvoke(prompt)
            integration_result = await self.llm.with_structured_output(KnowledgeIntegratorOutput).ainvoke(
                [HumanMessage(content=prompt)]
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
            
    def _format_telegram_results(self, telegram_data: List[RetrievedTelegramMessage]) -> str:
        """텔레그램 결과를 문자열로 포맷팅"""
        if not telegram_data:
            return "텔레그램 검색 결과 없음"
            
        formatted = "텔레그램 검색 결과:\n"
        for i, msg in enumerate(telegram_data):
            # 채널명 삭제.
            #formatted += f"[{i+1}] 출처: {msg.get('channel_name', '알 수 없음')}\n"
            formatted += f"내용: {msg.get('content', '내용 없음')}\n"
            if msg.get('message_created_at'):
                formatted += f"작성일: {msg.get('message_created_at')}\n"
            formatted += "---\n"
            
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
                
                # # 분석 정보가 있는 경우 우선적으로 사용
                # has_analysis = False
                # if "analysis" in report and report["analysis"]:
                #     analysis = report["analysis"]
                #     # llm_response 키 사용 (report_analyzer_agent의 실제 출력 키)
                #     if "llm_response" in analysis:
                #         formatted += f"분석 결과: {analysis.get('llm_response', '')}\n"
                #         has_analysis = True
                #     # 투자 의견 정보 추가
                #     if "investment_opinions" in analysis and analysis["investment_opinions"]:
                #         opinions = analysis["investment_opinions"]
                #         formatted += "투자의견: "
                #         for op in opinions[:2]:  # 처음 2개만 표시
                #             formatted += f"{op.get('source', '')}: {op.get('opinion', '없음')} (목표가: {op.get('target_price', '없음')}), "
                #         formatted += "\n"
                #     # 종합 의견이 있는 경우 추가
                #     if "opinion_summary" in analysis and analysis["opinion_summary"]:
                #         formatted += f"종합의견: {analysis.get('opinion_summary', '')}\n"
                
                # # 분석 정보가 없는 경우에만 원본 내용 추가 
                # if not has_analysis:
                #     content = report.get('content', '내용 없음')
                #     formatted += f"내용: {content}\n"
                    
                formatted += "---\n"
            
        return formatted
    
    def _format_financial_results(self, financial_data: List[Dict[str, Any]]) -> str:
        """재무 분석 결과를 문자열로 포맷팅"""
        if not financial_data:
            return "재무 분석 결과 없음"
            
        formatted = "재무 분석 결과:\n"
        for i, data in enumerate(financial_data):
            formatted += f"[{i+1}] 기간: {data.get('period', '기간 정보 없음')}\n"
            
            # 재무 지표 정보
            metrics = data.get('metrics', {})
            if metrics:
                formatted += "주요 지표:\n"
                for key, value in metrics.items():
                    formatted += f"- {key}: {value}\n"
            
            # 분석 정보
            analysis = data.get('analysis', {})
            if analysis:
                formatted += f"분석: {str(analysis)[:300]}\n"
                
            formatted += "---\n"
            
        return formatted
    
    def _format_industry_results(self, industry_data: List[Dict[str, Any]]) -> str:
        """산업 분석 결과를 문자열로 포맷팅"""
        if not industry_data or len(industry_data) == 0:
            return "산업 분석 결과 없음"
        
        raw_data = industry_data.get("raw_data", [])
        formatted = "산업 분석 결과:\n"
        for i, data in enumerate(raw_data):
            formatted += f"[{i+1}] 산업: {data.get('title', '산업 정보 없음')}\n"
            formatted += f"날짜: {data.get('date', '기간 정보 없음')}\n"
            formatted += f"내용: {data.get('content', '내용 없음')}\n"
            # 트렌드 정보
            trends = data.get('key_trends', {})
            if trends:
                formatted += "트렌드:\n"
                # 리스트인 경우와 딕셔너리인 경우 모두 처리
                if isinstance(trends, list):
                    for trend in trends:
                        formatted += f"- {trend}\n"
                elif isinstance(trends, dict):
                    for key, value in trends.items():
                        formatted += f"- {key}: {value}\n"
            
            # 경쟁사 정보
            competitors = data.get('competitors', [])
            if competitors:
                formatted += "주요 경쟁사:\n"
                for comp in competitors[:3]:  # 상위 3개만
                    formatted += f"- {comp.get('name', '이름 없음')}: {comp.get('info', '')}\n"
                    
            formatted += "---\n"
            
        return formatted
    
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