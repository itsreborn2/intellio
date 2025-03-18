"""
질문 분석기 에이전트 모듈

이 모듈은 사용자 질문을 분석하여 의도, 엔티티, 키워드 등의 
중요한 정보를 추출하는 QuestionAnalyzerAgent 클래스를 구현합니다.
"""

import json
from loguru import logger
from typing import Dict, List, Any, Optional, Literal, cast
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List, Optional as PydanticOptional
from common.services.agent_llm import get_llm_for_agent
from stockeasy.prompts.question_analyzer_prompts import format_question_analyzer_prompt
from common.core.config import settings
from stockeasy.models.agent_io import (
    QuestionAnalysisResult, ExtractedEntity, QuestionClassification, 
    DataRequirement, pydantic_to_typeddict
)


class Entities(BaseModel):
    """추출된 엔티티 정보"""
    stock_name: PydanticOptional[str] = Field(None, description="종목명 또는 null")
    stock_code: PydanticOptional[str] = Field(None, description="종목코드 또는 null")
    sector: PydanticOptional[str] = Field(None, description="산업/섹터 또는 null")
    time_range: PydanticOptional[str] = Field(None, description="시간범위 또는 null")
    financial_metric: PydanticOptional[str] = Field(None, description="재무지표 또는 null")
    competitor: PydanticOptional[str] = Field(None, description="경쟁사 또는 null")
    product: PydanticOptional[str] = Field(None, description="제품/서비스 또는 null")


class Classification(BaseModel):
    """질문 분류 정보"""
    primary_intent: Literal["종목기본정보", "성과전망", "재무분석", "산업동향", "기타"] = Field(
        ..., description="주요 질문 의도"
    )
    complexity: Literal["단순", "중간", "복합", "전문가급"] = Field(
        ..., description="질문 복잡도"
    )
    expected_answer_type: Literal["사실형", "추론형", "비교형", "예측형", "설명형"] = Field(
        ..., description="기대하는 답변 유형"
    )


class DataRequirements(BaseModel):
    """데이터 요구사항"""
    telegram_needed: bool = Field(..., description="텔레그램 데이터 필요 여부")
    reports_needed: bool = Field(..., description="리포트 데이터 필요 여부")
    financial_statements_needed: bool = Field(..., description="재무제표 데이터 필요 여부")
    industry_data_needed: bool = Field(..., description="산업 데이터 필요 여부")


class QuestionAnalysis(BaseModel):
    """질문 분석 결과"""
    entities: Entities = Field(..., description="추출된 엔티티 정보")
    classification: Classification = Field(..., description="질문 분류 정보")
    data_requirements: DataRequirements = Field(..., description="필요한 데이터 소스 정보")
    keywords: List[str] = Field(..., description="중요 키워드 목록")
    detail_level: Literal["간략", "보통", "상세"] = Field(..., description="요구되는 상세도")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "entities": {
                        "stock_name": "삼성전자",
                        "stock_code": "005930",
                        "sector": "전자",
                        "time_range": "최근",
                        "financial_metric": "실적",
                        "competitor": None,
                        "product": None
                    },
                    "classification": {
                        "primary_intent": "성과전망",
                        "complexity": "단순",
                        "expected_answer_type": "사실형"
                    },
                    "data_requirements": {
                        "telegram_needed": True,
                        "reports_needed": True,
                        "financial_statements_needed": True,
                        "industry_data_needed": False
                    },
                    "keywords": ["삼성전자", "실적", "최근", "재무"],
                    "detail_level": "보통"
                }
            ]
        }
    }


class QuestionAnalyzerAgent:
    """
    사용자 질문을 분석하여 의도, 엔티티, 키워드 등의 중요 정보를 추출하는 질문 분석기 에이전트
    
    이 에이전트는 워크플로우의 초기 단계에서 실행되어 질문의 '내용'을 분석하고,
    오케스트레이터가 워크플로우를 설계하는 데 필요한 정보를 제공합니다.
    """
    
    def __init__(self):
        """
        질문 분석기 에이전트 초기화
        
        Args:
            model_name: 사용할 OpenAI 모델 이름
            temperature: 모델 출력의 다양성 조절 파라미터
        """
        #self.llm = ChatOpenAI(model_name=model_name, temperature=temperature, api_key=settings.OPENAI_API_KEY)
        self.llm, self.model_name, self.provider = get_llm_for_agent("question_analyzer_agent")
        logger.info(f"QuestionAnalyzerAgent initialized with provider: {self.provider}, model: {self.model_name}")
        
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        사용자 질문을 분석하여 중요 정보를 추출하고 상태를 업데이트합니다.
        
        Args:
            state: 현재 상태 정보를 포함하는 딕셔너리
            
        Returns:
            업데이트된 상태 딕셔너리
        """
        try:
            # 성능 측정 시작
            start_time = datetime.now()
            logger.info(f"QuestionAnalyzerAgent starting processing")
            
            # 현재 사용자 쿼리 추출
            query = state.get("query", "")
            
            if not query:
                logger.warning("Empty query provided to QuestionAnalyzerAgent")
                self._add_error(state, "질문이 비어 있습니다.")
                return state
            
            logger.info(f"QuestionAnalyzerAgent analyzing query: {query}")
            
            # 프롬프트 준비
            prompt = format_question_analyzer_prompt(query=query)
            
            # LLM 호출로 분석 수행 - structured output 사용
            response:QuestionAnalysis = await self.llm.with_structured_output(QuestionAnalysis).ainvoke(
                [HumanMessage(content=prompt)]
            )
            
            # 분석 결과 로깅
            logger.info(f"Analysis result: {response}")
            
            # QuestionAnalysisResult 객체 생성 - 유틸리티 함수 사용
            question_analysis: QuestionAnalysisResult = {
                "entities": response.entities.dict(),
                "classification": response.classification.dict(),
                "data_requirements": response.data_requirements.dict(),
                "keywords": response.keywords,
                "detail_level": response.detail_level
            }
            
            # 상태에 저장
            state["question_analysis"] = question_analysis
            
            # 성능 지표 업데이트
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 메트릭 기록
            state["metrics"] = state.get("metrics", {})
            state["metrics"]["question_analyzer"] = {
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "status": "completed",
                "error": None,
                "model_name": self.model_name
            }
            
            # 처리 상태 업데이트
            state["processing_status"] = state.get("processing_status", {})
            state["processing_status"]["question_analyzer"] = "completed"
            
            logger.info(f"QuestionAnalyzerAgent completed in {duration:.2f} seconds")
            return state
            
        except Exception as e:
            logger.exception(f"Error in QuestionAnalyzerAgent: {str(e)}")
            self._add_error(state, f"질문 분석기 에이전트 오류: {str(e)}")
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
            "agent": "question_analyzer",
            "error": error_message,
            "type": "processing_error",
            "timestamp": datetime.now(),
            "context": {"query": state.get("query", "")}
        })
        
        # 처리 상태 업데이트
        state["processing_status"] = state.get("processing_status", {})
        state["processing_status"]["question_analyzer"] = "failed" 