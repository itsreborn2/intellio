"""
응답 포맷터 에이전트 모듈

이 모듈은 통합된 지식 정보를 사용자에게 이해하기 쉬운 
형태로 포맷팅하는 응답 포맷터 에이전트 클래스를 구현합니다.
"""

import json
from loguru import logger
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator

from langchain_core.messages import HumanMessage, AIMessage
from common.services.agent_llm import get_agent_llm, get_llm_for_agent
from stockeasy.prompts.response_formatter_prompts import FRIENDLY_RESPONSE_FORMATTER_SYSTEM_PROMPT, FRIENDLY_RESPONSE_FORMATTER_SYSTEM_PROMPT2, format_response_formatter_prompt
from langchain_core.output_parsers import StrOutputParser
from common.models.token_usage import ProjectType
from stockeasy.agents.base import BaseAgent
from sqlalchemy.ext.asyncio import AsyncSession
from common.schemas.chat_components import (
    HeadingComponent, ParagraphComponent, ListComponent, ListItemComponent,
    CodeBlockComponent, BarChartComponent, LineChartComponent, ImageComponent,
    TableComponent, TableHeader, TableData, BarChartData, LineChartData
)
import re

class ResponseFormatterAgent(BaseAgent):
    """
    최종 응답을 형식화하는 에이전트
    
    이 에이전트는 knowledge_integrator 또는 summarizer의 결과를 받아
    사용자 친화적인 형태로 가공합니다.
    """
    
    def __init__(self, name: Optional[str] = None, db: Optional[AsyncSession] = None):
        """
        응답 형식화 에이전트 초기화
        
        Args:
            name: 에이전트 이름 (지정하지 않으면 클래스명 사용)
            db: 데이터베이스 세션 객체 (선택적)
        """
        super().__init__(name, db)
        #self.llm, self.model_name, self.provider = get_llm_for_agent("response_formatter_agent")
        self.agent_llm = get_agent_llm("response_formatter_agent")
        logger.info(f"ResponseFormatterAgent initialized with provider: {self.agent_llm.get_provider()}, model: {self.agent_llm.get_model_name()}")
        self.parser = StrOutputParser()
        self.prompt_template = FRIENDLY_RESPONSE_FORMATTER_SYSTEM_PROMPT

    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        통합된 정보를 기반으로 사용자에게 이해하기 쉬운 응답을 생성합니다.
        
        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리
            
        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 현재 사용자 쿼리 및 종목 정보 추출
            query = state.get("query", "")
            stock_code = state.get("stock_code")
            stock_name = state.get("stock_name")
            
            # 통합된 응답 및 인사이트 추출
            integrated_knowledge = state.get("integrated_knowledge", {})
            
            integrated_response = integrated_knowledge.get("integrated_response", state.get("integrated_response", ""))
            core_insights = integrated_knowledge.get("core_insights", [])
            
            analysis = integrated_knowledge.get("analysis", {})
            confidence_assessment = analysis.get("confidence_assessment", {})
            uncertain_areas = analysis.get("uncertain_areas", [])
            
            logger.info(f"ResponseFormatterAgent formatting response for query: {query}")
            
            summary = state.get("summary", "")
            processing_status = state.get("processing_status", {})
            summarizer_status = processing_status.get("summarizer", "not_started")

            context_response_agent = state["agent_results"].get("context_response_agent", {})
            context_based_answer = ""
            if context_response_agent:
                context_based_answer = context_response_agent.get("answer", "")
                summary = context_based_answer
            
            # 통합된 응답이 없는 경우 처리
            if not context_based_answer and (not summary or summarizer_status != "completed"):
                logger.warning(f"No summary response available.")
                logger.warning(f"processing_status: {processing_status}")
                logger.warning(f"Summarizer status: {summarizer_status}")
                state["formatted_response"] = "죄송합니다. 현재 요청에 대한 정보를 찾을 수 없습니다. 다른 질문을 해 주시거나 나중에 다시 시도해 주세요."
                state["answer"] = "죄송합니다. 현재 요청에 대한 정보를 찾을 수 없습니다. 다른 질문을 해 주시거나 나중에 다시 시도해 주세요."
                return state
            
            # 1. 상태에서 커스텀 프롬프트 템플릿 확인
            custom_prompt_from_state = state.get("custom_prompt_template")
            # 2. 속성에서 커스텀 프롬프트 템플릿 확인 
            custom_prompt_from_attr = getattr(self, "prompt_template_test", None)
            # 커스텀 프롬프트 사용 우선순위: 상태 > 속성 > 기본값
            system_prompt = None
            if custom_prompt_from_state:
                system_prompt = custom_prompt_from_state
                logger.info(f"ResponseFormatterAgent using custom prompt from state : {custom_prompt_from_state}")
            elif custom_prompt_from_attr:
                system_prompt = custom_prompt_from_attr
                logger.info(f"ResponseFormatterAgent using custom prompt from attribute")

            # 프롬프트 준비
            prompt = format_response_formatter_prompt(
                query=query,
                stock_name=stock_name,
                stock_code=stock_code,
                integrated_response=summary,
                core_insights=core_insights,
                confidence_assessment=confidence_assessment,
                uncertain_areas=uncertain_areas,
                system_prompt=system_prompt
            )
            
            user_context = state.get("user_context", {})
            user_id = user_context.get("user_id", None)
            
            # 스트리밍 콜백 확인 또는 생성
            streaming_callback = state.get("streaming_callback")
            #logger.info(f"상태에서 전달받은 streaming_callback: {streaming_callback}, 타입: {type(streaming_callback).__name__ if streaming_callback else 'None'}")
            
            # 스트리밍 콜백이 없으면 더미 콜백 생성
            if not streaming_callback or not callable(streaming_callback):
                logger.info("스트리밍 콜백이 없어 더미 콜백을 생성합니다.")
                # 더미 스트리밍 콜백 - 실제로는 아무것도 하지 않음
                async def dummy_streaming_callback(chunk: str):
                    pass
                streaming_callback = dummy_streaming_callback
                logger.warning("주의: 더미 콜백을 사용하여 실제 스트리밍이 클라이언트에게 전달되지 않습니다.")
            else:
                logger.info(f"유효한 스트리밍 콜백 함수가 발견되었습니다: {streaming_callback.__name__ if hasattr(streaming_callback, '__name__') else '이름 없는 함수'}")
            
            #logger.info("스트리밍 모드로 응답 생성 시작")
            # 스트리밍 모드로 호출
            isStreaming = False
            formatted_response = ""
            
            try:
                if not isStreaming:
                    logger.info("일반 모드로 폴백")
                    response:AIMessage = await self.agent_llm.ainvoke_with_fallback(
                        input=prompt.format_prompt(),
                        user_id=user_id,
                        project_type=ProjectType.STOCKEASY,
                        db=self.db
                    )
                    formatted_response = response.content
                else:
                    # 새로 구현된 stream 메서드 사용
                    async for chunk in self.agent_llm.stream(
                        input=prompt.format_prompt().to_string(),
                        user_id=user_id,
                        project_type=ProjectType.STOCKEASY,
                        db=self.db
                    ):
                        # 청크 내용 추출
                        if hasattr(chunk, 'content'):
                            chunk_content = chunk.content
                        else:
                            chunk_content = str(chunk)
                        
                        # 콜백 호출하여 청크 전송
                        try:
                            #print(chunk_content, end="", flush=True)
                            #logger.info(f"스트리밍 콜백 호출: 청크 길이={len(chunk_content)}, callback={streaming_callback.__name__ if hasattr(streaming_callback, '__name__') else type(streaming_callback).__name__}")
                            await streaming_callback(chunk_content)
                            #logger.info(f"스트리밍 콜백 호출 완료: 청크 길이={len(chunk_content)}")
                        except Exception as callback_error:
                            logger.error(f"스트리밍 콜백 호출 중 오류: {str(callback_error)}", exc_info=True)
                        
                        # 전체 응답 누적
                        formatted_response += chunk_content
                
                #logger.info("스트리밍 응답 생성 완료")
            except Exception as e:
                # 스트리밍 중 오류 발생 시 간단한 오류 처리
                logger.error(f"스트리밍 응답 생성 중 오류 발생: {str(e)}")
                # 부분 응답이 없으면 일반 모드로 폴백
                if not formatted_response:
                    logger.info("일반 모드로 폴백")
                    response:AIMessage = await self.agent_llm.ainvoke_with_fallback(
                        input=prompt.format_prompt(),
                        user_id=user_id,
                        project_type=ProjectType.STOCKEASY,
                        db=self.db
                    )
                    formatted_response = response.content
            
            # 포맷팅된 응답 저장
            state["formatted_response"] = formatted_response
            state["answer"] = formatted_response

            # 구조화된 컴포넌트 생성
            components = await self.make_components(state)
            
            # 결과 저장
            state["components"] = [comp.dict() for comp in components]
            state["answer"] = formatted_response  # 기졸 방식과의 호환성 유지
            
            # 오류 제거 (성공적으로 처리됨)
            if "error" in state:
                del state["error"]
                
            # 처리 상태 업데이트
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["response_formatter"] = "completed"
                
            return state
            
        except Exception as e:
            logger.exception(f"Error in ResponseFormatterAgent: {str(e)}")
            state["error"] = f"응답 포맷터 에이전트 오류: {str(e)}"
            state["formatted_response"] = "죄송합니다. 응답을 포맷팅하는 중 오류가 발생했습니다."
            state["answer"] = state["formatted_response"]
            return state 

    async def make_components(self, state: Dict[str, Any]):
        """
        포맷팅된 응답을 구조화된 컴포넌트로 변환합니다.
        """
        components = []
        
        # 상태에서 정보 추출
        stock_name = state.get("stock_name", "삼성전자")
        stock_code = state.get("stock_code", "005930")
        formatted_response = state.get("formatted_response", "")
        
        # 1. 헤딩 컴포넌트 (여러 레벨)
        components.append(HeadingComponent(
            level=1,
            content=f"{stock_name}({stock_code}) 분석 결과"
        ))
        
        # 2. 단락 컴포넌트
        components.append(ParagraphComponent(
            content=f"{stock_name}의 최근 실적과 시장 동향을 분석한 결과입니다. 아래 데이터를 참고하여 투자 결정에 활용하시기 바랍니다."
        ))
        
        # 3. 부제목 (2단계 헤딩)
        components.append(HeadingComponent(
            level=2,
            content="주요 재무 지표"
        ))
        
        # 4. 목록 컴포넌트 (순서 없는 목록)
        components.append(ListComponent(
            ordered=False,
            items=[
                ListItemComponent(content="최근 분기 매출액: 7.8조원 (전년 대비 5.2% 증가)"),
                ListItemComponent(content="영업이익률: 15.3% (전년 대비 2.1%p 상승)"),
                ListItemComponent(content="ROE: 12.7% (업계 평균 대비 양호)"),
                ListItemComponent(content="부채비율: 45.2% (안정적인 재무구조 유지)")
            ]
        ))
        
        # 5. 두 번째 부제목
        components.append(HeadingComponent(
            level=2,
            content="실적 추이"
        ))
        
        # 6. 바차트 컴포넌트
        components.append(BarChartComponent(
            title="분기별 매출 및 영업이익 추이",
            data=BarChartData(
                labels=["1Q 2023", "2Q 2023", "3Q 2023", "4Q 2023", "1Q 2024"],
                datasets=[
                    {
                        "label": "매출액(조원)",
                        "data": [63.7, 67.4, 71.2, 74.8, 78.5],
                        "backgroundColor": "#4C9AFF"
                    },
                    {
                        "label": "영업이익(조원)",
                        "data": [8.2, 9.1, 10.3, 11.2, 12.0],
                        "backgroundColor": "#FF5630"
                    }
                ]
            )
        ))
        
        # 7. 차트 설명 단락
        components.append(ParagraphComponent(
            content=f"위 차트는 {stock_name}의 최근 5개 분기 매출액과 영업이익 추이를 보여줍니다. 지속적인 성장세를 유지하고 있습니다."
        ))
        
        # 8. 세 번째 부제목
        components.append(HeadingComponent(
            level=2,
            content="주가 동향"
        ))
        
        # 9. 라인차트 컴포넌트
        components.append(LineChartComponent(
            title="최근 6개월 주가 추이",
            data=LineChartData(
                labels=["11월", "12월", "1월", "2월", "3월", "4월"],
                datasets=[
                    {
                        "label": "주가(원)",
                        "data": [67000, 70200, 72800, 69500, 74200, 76800],
                        "borderColor": "#36B37E",
                        "tension": 0.1
                    },
                    {
                        "label": "KOSPI(pt)",
                        "data": [2450, 2520, 2580, 2510, 2650, 2700],
                        "borderColor": "#FF8B00",
                        "tension": 0.1,
                        "borderDash": [5, 5]
                    }
                ]
            )
        ))
        
        # 10. 네 번째 부제목
        components.append(HeadingComponent(
            level=2,
            content="주요 재무제표"
        ))
        
        # 11. 테이블 컴포넌트
        components.append(TableComponent(
            title="요약 재무제표",
            data=TableData(
                headers=[
                    TableHeader(key="item", label="항목"),
                    TableHeader(key="2022", label="2022년"),
                    TableHeader(key="2023", label="2023년"),
                    TableHeader(key="yoy", label="증감률(%)")
                ],
                rows=[
                    {"item": "매출액", "2022": "280조원", "2023": "302조원", "yoy": "+7.9%"},
                    {"item": "영업이익", "2022": "36.5조원", "2023": "42.8조원", "yoy": "+17.3%"},
                    {"item": "당기순이익", "2022": "28.1조원", "2023": "33.7조원", "yoy": "+19.9%"},
                    {"item": "자산총계", "2022": "420.2조원", "2023": "456.8조원", "yoy": "+8.7%"},
                    {"item": "부채총계", "2022": "187.5조원", "2023": "195.2조원", "yoy": "+4.1%"},
                    {"item": "자본총계", "2022": "232.7조원", "2023": "261.6조원", "yoy": "+12.4%"}
                ]
            )
        ))
        
        # 12. 다섯 번째 부제목
        components.append(HeadingComponent(
            level=2,
            content="산업 비교 분석"
        ))
        
        # 13. 순서 있는 목록
        components.append(ListComponent(
            ordered=True,
            items=[
                ListItemComponent(content="시장점유율: 글로벌 시장에서 1위 유지 (점유율 22.3%)"),
                ListItemComponent(content="기술 경쟁력: 주요 경쟁사 대비 R&D 투자금액 15% 이상 높음"),
                ListItemComponent(content="수익성: 업계 평균 영업이익률 9.7% 대비 5.6%p 높은 수준"),
                ListItemComponent(content="성장성: 2024년 예상 성장률 8.5%로 업계 평균(5.2%) 상회")
            ]
        ))
        
        # 14. 여섯 번째 부제목
        components.append(HeadingComponent(
            level=2,
            content="코드 예시"
        ))
        
        # 15. 코드 블록 컴포넌트
        components.append(CodeBlockComponent(
            language="python",
            content="""
import pandas as pd
import matplotlib.pyplot as plt

# 삼성전자 재무데이터 로드
df = pd.read_csv('samsung_financial.csv')

# 분기별 매출 추이 차트
plt.figure(figsize=(12, 6))
plt.plot(df['quarter'], df['revenue'], marker='o')
plt.title('삼성전자 분기별 매출 추이')
plt.grid(True)
plt.show()
            """
        ))
        
        # 16. 일곱 번째 부제목
        components.append(HeadingComponent(
            level=2,
            content="투자 의견"
        ))
        
        # 17. 마지막 단락
        components.append(ParagraphComponent(
            content=f"{stock_name}는 안정적인 재무구조와 지속적인 성장세를 보이고 있으며, 업계 내 경쟁우위를 유지하고 있습니다. 단기적인 시장 변동성에도 불구하고 중장기 성장 잠재력이 높다고 판단됩니다. 다만, 글로벌 경제 불확실성과 산업 내 경쟁 심화는 리스크 요인으로 작용할 수 있습니다."
        ))
        
        # 18. 이미지 컴포넌트 (샘플)
        components.append(ImageComponent(
            url="https://example.com/chart_image.png",
            alt="삼성전자 사업부문별 매출 비중",
            caption="2023년 사업부문별 매출 비중"
        ))
        
        # 19. 면책조항
        components.append(ParagraphComponent(
            content="※ 위 정보는 투자 참고 목적으로 제공되며, 투자 결정은 개인의 판단에 따라 신중하게 이루어져야 합니다."
        ))
        
        return components

