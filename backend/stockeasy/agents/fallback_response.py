"""
Fallback 매니저 및 응답 포맷터 에이전트

이 모듈은 오류 처리와 사용자 친화적인 응답 생성을 담당하는 에이전트들을 정의합니다.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from stockeasy.agents.base import BaseAgent
from stockeasy.models.agent_io import AgentState
from common.core.config import settings


class FallbackManagerAgent(BaseAgent):
    """오류 상황에서 대체 응답을 생성하는 에이전트"""
    
    def __init__(self):
        """에이전트 초기화"""
        super().__init__("fallback_manager")
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL_NAME,
            temperature=0.3,  # 대체 응답에 약간의 창의성 부여
            api_key=settings.OPENAI_API_KEY
        )
        self.parser = StrOutputParser()
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        오류 상황 처리 및 대체 응답 생성
        
        Args:
            state: 현재 상태 (query, errors 등 포함)
            
        Returns:
            업데이트된 상태 (fallback_response 추가)
        """
        try:
            query = state.get("query", "")
            stock_code = state.get("stock_code")
            stock_name = state.get("stock_name")
            errors = state.get("errors", [])
            processing_status = state.get("processing_status", {})
            
            # 가용한 데이터 확인
            available_data = {
                "telegram_messages": state.get("telegram_messages", []),
                "report_data": state.get("report_data", []),
                "financial_data": state.get("financial_data", {}),
                "industry_data": state.get("industry_data", [])
            }
            
            # 오류 유형 분석
            error_types = self._analyze_errors(errors, processing_status)
            
            # Fallback 프롬프트 생성
            prompt = self._create_prompt(
                query, stock_code, stock_name, 
                error_types, available_data, errors
            )
            
            # LLM으로 대체 응답 생성
            chain = prompt | self.llm | self.parser
            fallback_response = await chain.ainvoke({})
            
            # 상태 업데이트
            return {
                **state,
                "summary": fallback_response,  # 요약 필드에 대체 응답 저장
                "fallback_response": fallback_response,
                "used_fallback": True,
                "fallback_reason": self._get_fallback_reason(error_types),
                "processing_status": {
                    **processing_status,
                    "fallback_manager": "completed"
                }
            }
            
        except Exception as e:
            logger.error(f"Fallback 처리 중 오류 발생: {e}", exc_info=True)
            # Fallback의 Fallback: 가장 기본적인 오류 메시지 반환
            basic_fallback = "죄송합니다. 현재 요청을 처리하는 중 문제가 발생했습니다. 나중에 다시 시도해주세요."
            
            return {
                **state,
                "errors": state.get("errors", []) + [{
                    "agent": self.get_name(),
                    "error": str(e),
                    "type": type(e).__name__,
                    "timestamp": datetime.now()
                }],
                "summary": basic_fallback,
                "fallback_response": basic_fallback,
                "used_fallback": True,
                "fallback_reason": "critical_error",
                "processing_status": {
                    **state.get("processing_status", {}),
                    "fallback_manager": "error"
                }
            }
    
    def _analyze_errors(self, errors: List[Dict[str, Any]], 
                       processing_status: Dict[str, str]) -> List[str]:
        """
        오류 유형 분석
        
        Args:
            errors: 발생한 오류 목록
            processing_status: 각 단계별 처리 상태
            
        Returns:
            식별된 오류 유형 목록
        """
        error_types = []
        
        # 처리 상태 기반 분석
        for agent, status in processing_status.items():
            if status == "error":
                error_types.append(f"{agent}_error")
        
        # 오류 메시지 기반 분석
        for error in errors:
            error_msg = error.get("error", "").lower()
            error_type = error.get("type", "")
            
            if "api" in error_msg or "rate" in error_msg or "limit" in error_msg:
                error_types.append("api_error")
            elif "data" in error_msg or "not found" in error_msg or "empty" in error_msg:
                error_types.append("data_not_found")
            elif "timeout" in error_msg or "time" in error_msg:
                error_types.append("timeout_error")
            elif "permission" in error_msg or "access" in error_msg:
                error_types.append("permission_error")
        
        return list(set(error_types))  # 중복 제거
    
    def _get_fallback_reason(self, error_types: List[str]) -> str:
        """
        Fallback 이유 결정
        
        Args:
            error_types: 식별된 오류 유형 목록
            
        Returns:
            Fallback 이유
        """
        if any(et.startswith("question_analyzer") for et in error_types):
            return "질문 분석 실패"
        elif "data_not_found" in error_types:
            return "관련 정보 없음"
        elif "api_error" in error_types:
            return "외부 서비스 오류"
        elif any(et.endswith("retriever_error") for et in error_types):
            return "데이터 검색 실패"
        elif "summarizer_error" in error_types:
            return "요약 생성 실패"
        else:
            return "기타 처리 오류"
    
    def _create_prompt(self, query: str, stock_code: Optional[str], stock_name: Optional[str],
                      error_types: List[str], available_data: Dict[str, Any], 
                      errors: List[Dict[str, Any]]) -> ChatPromptTemplate:
        """Fallback 응답 생성을 위한 프롬프트 생성"""
        
        template = """
당신은 금융 정보 시스템에서 정보가 부족하거나 오류가 발생했을 때 적절한 대체 응답을 제공하는 전문가입니다.
다음 상황을 분석하고 최적의 대응 방안을 마련하세요:

사용자 질문: {query}
종목코드: {stock_code}
종목명: {stock_name}
발생한 오류 유형: {error_types}

{available_data_info}

대응 전략:
1. 정보 부족 상황을 명확히 설명하되, 전문적이고 도움이 되는 어조를 유지하세요.
2. 질문에 직접 답변할 수 없는 경우, 그 이유를 간략히 설명하세요.
3. 가능한 경우 대체 정보나 일반적인 지식을 제공하세요.
4. 질문을 더 구체화하거나 다른 접근 방식을 제안하세요.
5. 시스템 자체의 오류보다는 정보 검색 관점에서 설명하세요.

응답 형식:
- 정보 부재 설명 (한 문장)
- 가능한 이유 제시 (1-2 문장)
- 대안이나 제안 (1-2 문장)
- 다음 단계 제안 (선택적)
"""
        
        # 오류 유형을 사람이 읽기 쉬운 형태로 변환
        readable_error_types = []
        for et in error_types:
            if et == "data_not_found":
                readable_error_types.append("관련 정보를 찾을 수 없음")
            elif et == "api_error":
                readable_error_types.append("외부 서비스 연결 문제")
            elif et.endswith("_error"):
                agent_name = et.replace("_error", "")
                readable_error_types.append(f"{agent_name} 처리 오류")
        
        # 가용한 데이터 정보 형식화
        available_data_info = "현재까지 수집된 정보:\n"
        
        if not any(available_data.values()):
            available_data_info += "검색된 정보가 없습니다."
        else:
            for source, data in available_data.items():
                if data:
                    if source == "telegram_messages":
                        available_data_info += f"- 텔레그램 메시지: {len(data)}개 메시지 발견\n"
                    elif source == "report_data":
                        available_data_info += f"- 기업 리포트: {len(data)}개 리포트 발견\n"
                    elif source == "financial_data" and data:
                        available_data_info += f"- 재무 정보: 데이터 발견\n"
                    elif source == "industry_data":
                        available_data_info += f"- 산업 동향: {len(data)}개 항목 발견\n"
        
        # 프롬프트 생성
        return ChatPromptTemplate.from_template(template).partial(
            query=query,
            stock_code=stock_code or "정보 없음",
            stock_name=stock_name or "정보 없음",
            error_types=", ".join(readable_error_types) or "불특정 오류",
            available_data_info=available_data_info
        )


class ResponseFormatterAgent(BaseAgent):
    """최종 응답을 사용자 친화적인 형태로 변환하는 에이전트"""
    
    def __init__(self):
        """에이전트 초기화"""
        super().__init__("response_formatter")
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL_NAME,
            temperature=0.2,
            api_key=settings.OPENAI_API_KEY
        )
        self.parser = StrOutputParser()
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        최종 응답 형식화
        
        Args:
            state: 현재 상태 (summary, fallback_response 등 포함)
            
        Returns:
            업데이트된 상태 (formatted_response 추가)
        """
        try:
            query = state.get("query", "")
            stock_code = state.get("stock_code")
            stock_name = state.get("stock_name")
            classification = state.get("classification", {})
            summary = state.get("summary", "")
            used_fallback = state.get("used_fallback", False)
            fallback_reason = state.get("fallback_reason", "")
            
            if not summary:
                return {
                    **state,
                    "errors": state.get("errors", []) + [{
                        "agent": self.get_name(),
                        "error": "형식화할 요약이 없습니다.",
                        "type": "InvalidInputError",
                        "timestamp": datetime.now()
                    }],
                    "processing_status": {
                        **state.get("processing_status", {}),
                        "response_formatter": "error"
                    },
                    "formatted_response": "죄송합니다. 응답을 생성할 수 없습니다."
                }
            
            # Fallback 응답은 이미 형식화되어 있으므로 그대로 사용
            if used_fallback:
                return {
                    **state,
                    "formatted_response": summary,
                    "processing_status": {
                        **state.get("processing_status", {}),
                        "response_formatter": "completed"
                    }
                }
            
            # 응답 형식화 프롬프트 생성
            prompt = self._create_prompt(query, stock_code, stock_name, classification, summary)
            
            # LLM으로 형식화된 응답 생성
            chain = prompt | self.llm | self.parser
            formatted_response = await chain.ainvoke({})
            
            # 상태 업데이트
            return {
                **state,
                "formatted_response": formatted_response,
                "processing_status": {
                    **state.get("processing_status", {}),
                    "response_formatter": "completed"
                }
            }
            
        except Exception as e:
            logger.error(f"응답 형식화 중 오류 발생: {e}", exc_info=True)
            # 오류가 발생하면 원본 요약 그대로 반환
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
                    "response_formatter": "error"
                },
                "formatted_response": state.get("summary", "응답을 형식화할 수 없습니다.")
            }
    
    def _create_prompt(self, query: str, stock_code: Optional[str], stock_name: Optional[str],
                      classification: Dict[str, Any], summary: str) -> ChatPromptTemplate:
        """응답 형식화를 위한 프롬프트 생성"""
        
        template = """
당신은 금융 정보 분석 결과를 사용자 친화적인 형태로 변환하는 전문가입니다.
다음 요약 내용을 가독성 높고 명확한 형태로 재구성하세요:

원본 요약:
{summary}

사용자 질문: {query}
종목코드: {stock_code}
종목명: {stock_name}
질문 유형: {question_type}
답변 수준: {answer_level}

포맷팅 전략:
1. 명확한 섹션과 소제목을 사용하여 구조화하세요.
2. 핵심 정보는 굵은 글씨나 중요 표시로 강조하세요.
3. 수치 정보는 가독성 높게 표현하세요.
4. 전문 용어는 필요시 간단한 설명을 추가하세요.
5. 정보의 출처와 시점을 명확히 표시하세요.
6. 부정확하거나 불확실한 정보가 있다면 그 한계를 명시하세요.

답변 수준에 따른 포맷:
- 간단한답변: 한 문단 내외의 간결한 요약
- 긴설명요구: 섹션별 구조화된 상세 설명
- 종합적판단: 다양한 관점을 균형있게 포함한 심층 분석
- 전문가분석: 전문적 용어와 상세한 분석이 포함된 심층 리포트

원본 요약의 내용을 유지하되, 가독성과 이해도를 높이는 방향으로 재구성하세요.
"""
        
        # 질문 유형 및 답변 수준 매핑
        question_types = ["종목기본정보", "전망", "재무분석", "산업동향", "기타"]
        answer_levels = ["간단한답변", "긴설명요구", "종합적판단", "전문가분석"]
        
        question_type_idx = classification.get("질문주제", 4)
        answer_level_idx = classification.get("답변수준", 1)
        
        question_type = question_types[question_type_idx] if 0 <= question_type_idx < len(question_types) else "기타"
        answer_level = answer_levels[answer_level_idx] if 0 <= answer_level_idx < len(answer_levels) else "긴설명요구"
        
        # 프롬프트 생성
        return ChatPromptTemplate.from_template(template).partial(
            query=query,
            stock_code=stock_code or "정보 없음",
            stock_name=stock_name or "정보 없음",
            question_type=question_type,
            answer_level=answer_level,
            summary=summary
        ) 