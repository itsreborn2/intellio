"""
대화 컨텍스트 응답 에이전트 모듈

이 모듈은 이전 대화 컨텍스트를 활용하여 후속 질문에 답변하는 에이전트를 정의합니다.
"""

import json
from loguru import logger
from typing import Dict, List, Any, Optional, Literal
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from common.models.token_usage import ProjectType
from common.services.agent_llm import get_llm_for_agent, get_agent_llm
from stockeasy.agents.base import BaseAgent
from sqlalchemy.ext.asyncio import AsyncSession


class ContextResponseAgent(BaseAgent):
    """
    이전 대화 컨텍스트를 활용하여 후속 질문에 답변하는 에이전트
    
    이 에이전트는 다음을 수행합니다:
    1. 이전 대화 컨텍스트와 현재 질문을 분석
    2. 컨텍스트를 고려한 구체적인 응답 생성
    3. 이전 응답에서 언급된 정보를 활용해 연속적인 대화 유지
    """
    
    def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
        """
        컨텍스트 응답 에이전트 초기화
        
        Args:
            name: 에이전트 이름 (지정하지 않으면 클래스명 사용)
            db: 데이터베이스 세션 객체 (선택적)
        """
        super().__init__(name, db)
        self.llm, self.model_name, self.provider = get_llm_for_agent("context_response_agent")
        self.agent_llm = get_agent_llm("context_response_agent")
        logger.info(f"ContextResponseAgent initialized with provider: {self.provider}, model: {self.model_name}")
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        대화 컨텍스트를 바탕으로 질문을 분석하고 응답을 생성합니다.
        
        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리
            
        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 성능 측정 시작
            start_time = datetime.now()
            logger.info("ContextResponseAgent 처리 시작")
            
            # 현재 사용자 쿼리 및 분석 결과 추출
            query = state.get("query", "")
            

            stock_code = state.get("stock_code", "")
            stock_name = state.get("stock_name", "")
            context_analysis = state.get("context_analysis", {})
            conversation_history = state.get("conversation_history", [])
            modified_query = f"종목명: {stock_name} 종목코드: {stock_code} 질문: {query}"
            
            if not query:
                logger.warning("빈 쿼리가 ContextResponseAgent에 제공됨")
                self._add_error(state, "질문이 비어 있습니다.")
                return state
            
            if not context_analysis:
                logger.warning("컨텍스트 분석 결과가 없음")
                self._add_error(state, "컨텍스트 분석 결과가 없습니다.")
                return state
            
            if not conversation_history or len(conversation_history) < 2:
                logger.warning("대화 기록이 충분하지 않음")
                self._add_error(state, "대화 기록이 충분하지 않습니다.")
                return state
            
            # 대화 기록 포맷팅 (최근 5번의 대화만 사용)
            formatted_history = ""
            recent_history = conversation_history[-10:] if len(conversation_history) >= 10 else conversation_history
            
            for i, msg in enumerate(recent_history):
                role = "사용자" if msg.type == "human" else "AI"
                formatted_history += f"{role}: {msg.content}\n\n"
            # 백업 가이드라인이 사실 의미가 없을 수 있으나, fallback 예외처리 느낌.
            # 왜냐면 문서에 없거나 문맥에 없다면, 이 에이전트로 안올 가능성이 높음.
            
            # 컨텍스트 응답 프롬프트 구성
            system_prompt = """
당신은 주식 분석 전문가로서 사용자와의 대화 맥락을 이해하고 응답하는 역할을 합니다.

이전 대화 내용을 고려하여 사용자의 현재 질문에 답변해 주세요. 사용자가 이전 대화에서 언급된 내용에 기반하여 질문할 때, 
그 맥락을 제대로 파악하고 관련 정보를 연결하여 일관된 응답을 제공해야 합니다.

A. 주요 가이드라인
 1. 이전 대화에서 언급된 정보를 정확히 참조하세요.
 2. 대명사(이것, 그것 등)가 무엇을 가리키는지 명확히 이해하고 응답하세요.
 3. 새로운 정보를 추가할 때는 이전 대화와 자연스럽게 연결되도록 하세요.
 4. 사용자가 이전 답변에 대해 더 깊은 설명을 요청할 때, 관련 세부 정보를 제공하세요.
 5. 종목명/코드를 포함해 핵심 정보를 유지하며 일관성 있는 답변을 제공하세요.
 6. 너무 반복적이지 않도록 주의하세요. 이전 답변의 내용을 그대로 반복하지 말고, 새로운 가치를 추가하세요.
 7. 전문적인 주식 분석가로서 정확하고 유용한 정보를 제공하세요.
 8. 문서나 데이터베이스에 없는 내용에 대해 질문을 받았을 경우, 명확하게 "해당 정보를 찾을 수 없습니다"라고 밝히세요. 추측이나 가정에 기반한 답변을 제공하지 마세요.
 9. 사용자가 요청한 정보의 일부만 확인 가능한 경우, 확인 가능한 부분만 답변하고 확인할 수 없는 부분은 명시적으로 언급하세요.
 10. 질문의 맥락이 불명확할 경우, 즉각적으로 추가 질문을 하기보다 이전 대화에서 관련 정보를 최대한 활용하여 의도를 파악하세요.
 11. 주식 시장의 미래 움직임에 대해 단정적인 예측을 피하고, 데이터에 기반한 분석과 가능성을 제시하세요.
 
 사용자의 질문이 이전 대화와 관련된 후속 질문인 경우, 이전 대화에서 제공한 정보를 활용하여 보다 맥락화된 심층적인 답변을 제공하세요. 
 정보가 불충분하거나 확인할 수 없는 내용에 대해서는 솔직하게 한계를 인정하고, 추측이나 허위 정보를 제공하지 마세요.
 제공된 문서로 답변을 할 수 없다면, B. 백업 가이드라인의 절차를 준수하세요.

B. 백업 가이드라인(A 실패 시)
 1. 이전 대화에서 언급된 정보로 답변을 생성할 수 없다면, 사용자의 질문에 대한 일반적인 답변을 제공하세요.
 2. 답변의 끝에는 문서에 없는 내용이므로 추가적인 사실 확인이 필요하다고 언급하세요.
"""
            
            user_prompt = f"""
종목명: {stock_name}
종목코드: {stock_code}

이전 대화 내용:
{formatted_history}

현재 질문:
{modified_query}

위 대화 맥락을 고려하여 현재 질문에 답변해주세요.
"""
            
            # user_id 추출
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)
            
            
            # LLM 호출로 컨텍스트 기반 응답 생성
            analysis_prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            logger.info(f"컨텍스트 기반 응답 생성 시작: {query}")
            response = await self.agent_llm.ainvoke_with_fallback(
                analysis_prompt.format_prompt(),
                user_id=user_id,
                project_type=ProjectType.STOCKEASY,
                db=self.db
            )
            
            # 응답 추출
            answer = response.content
            logger.info(f"컨텍스트 응답 생성 완료: {len(answer)} 자")
            
            # 응답을 상태에 저장 
            # summary에 저장하면, response에서 이걸 읽는다.

            state["agent_results"]["context_response_agent"] = {
                "answer": answer,
                "based_on_context": True,
                "reference_length": len(conversation_history)
            }
            
            # answer 필드 업데이트 (최종 응답 제공용)
            #state["answer"] = answer
            
            # 성능 지표 업데이트
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 메트릭 기록
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["context_response"] = {
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "status": "completed",
                "error": None,
                "model_name": self.model_name
            }
            
            # 처리 상태 업데이트
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["context_response"] = "completed"
            state["next"] = "response_formatter"  # 다음 단계로 응답 포맷터 지정
            
            logger.info(f"ContextResponseAgent 완료: {duration:.2f}초 소요")
            return state
            
        except Exception as e:
            logger.exception(f"ContextResponseAgent 오류: {str(e)}")
            self._add_error(state, f"컨텍스트 응답 에이전트 오류: {str(e)}")
            # 오류가 발생하더라도 플로우 계속 진행
            state["next"] = "response_formatter"
            return state
    
    def _add_error(self, state: Dict[str, Any], error_message: str) -> None:
        """
        상태 객체에 오류 정보를 추가합니다.
        
        Args:
            state: 상태 객체
            error_message: 오류 메시지
        """
        state["errors"] = state.get("errors", [])
        state["errors"].append({
            "agent": "context_response",
            "error": error_message,
            "type": "processing_error",
            "timestamp": datetime.now(),
            "context": {"query": state.get("query", "")}
        })
        
        # 처리 상태 업데이트
        state["processing_status"] = state.get("processing_status", {})
        state["processing_status"]["context_response"] = "failed" 