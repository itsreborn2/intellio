from enum import Enum
from typing import Dict, Any, Optional, List
import aiohttp
import json
import logging
import asyncio
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.cache import AsyncRedisCache
import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse

logger = logging.getLogger(__name__)

class PromptTemplate(Enum):
    ANALYSIS = "analysis"        # 일반적인 문서 분석용
    TABLE_ANALYSIS = "table_analysis"  # 데이터 분석용
    TABLE_TITLE = "table_title"  # 테이블 제목 생성용

class PromptManager:
    def __init__(self, 
                 openai_api_key: Optional[str] = None, 
                 gemini_api_key: Optional[str] = None,
                 redis_url: Optional[str] = None,
                 cache_expire: Optional[int] = None):
        """프롬프트 매니저 초기화
        
        Args:
            openai_api_key: OpenAI API 키 (선택)
            gemini_api_key: Gemini API 키 (선택)
            redis_url: Redis 서버 URL (선택)
            cache_expire: 캐시 만료 시간 (초)
        """
        self.openai_api_key = openai_api_key or settings.OPENAI_API_KEY
        self.gemini_api_key = gemini_api_key or settings.GEMINI_API_KEY
        
        # Gemini 초기화
        logger.info("Gemini API 초기화 시작")
        genai.configure(api_key=self.gemini_api_key)
        
        # 모델 및 설정 초기화
        self.generation_config = genai.GenerationConfig(
            temperature=0.3,  # 낮은 temperature로 일관된 응답
            top_p=0.8,       # 다양성과 정확성의 균형
            top_k=40,        # 적절한 선택 범위
            max_output_tokens=2048,  # 충분한 응답 길이
            stop_sequences=[],  # 필요한 경우 중지 시퀀스 추가
        )
        
        self.safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
            },
        ]
        
        # gemini-2.0-flash-exp 모델 초기화화
        model_name = 'gemini-2.0-flash-exp'
        self.gemini_model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=self.generation_config,
            safety_settings=self.safety_settings
        )
        logger.info(f"Gemini API 초기화 완료 - 사용 모델: {model_name}")
        
        # OpenAI 클라이언트 초기화
        self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
        
        # 캐시 초기화
        self.cache = AsyncRedisCache(
            redis_url=redis_url or settings.REDIS_URL,
            expire_time=cache_expire or settings.REDIS_CACHE_EXPIRE
        )

    async def process_prompt(self, template: PromptTemplate, context: Dict[str, Any]) -> str:
        """프롬프트 처리
        
        Args:
            template: 프롬프트 템플릿
            context: 프롬프트 컨텍스트
            
        Returns:
            str: AI 응답 결과
        """
        # 캐시에서 응답 확인
        document_id = context.get("document_id", "")
        query = context.get("query", "")
        
        if document_id and query:
            cached_response = await self.cache.get(document_id, query)
            if cached_response:
                return cached_response["response"]
        
        try:
            # 프롬프트 생성
            prompt = self._generate_prompt(template, context)
            logger.info(f"Gemini API 호출 시작 - 모델: {self.gemini_model.model_name} - 프롬프트: {prompt[:200]}...")
            
            # 비동기로 Gemini API 호출
            response: GenerateContentResponse = await asyncio.to_thread(
                self.gemini_model.generate_content,
                contents=prompt,
            )
            
            if not response or response.candidates is None or len(response.candidates) == 0:
                raise Exception("No valid response from Gemini API")
            
            # 응답 처리 및 검증
            result = response.text
            if not result or len(result.strip()) == 0:
                raise Exception("Empty response from Gemini API")
                
            logger.info(f"Gemini API 응답 성공 - 결과: {result[:200]}...")
                    
        except Exception as e:
            logger.error(f"Gemini API 호출 실패: {str(e)}", exc_info=True)
            logger.info("OpenAI API로 폴백")
            result = await self._process_with_openai(template, context)
            
        # 응답 캐싱
        if document_id and query:
            await self.cache.set(document_id, query, result)
        
        return result

    def _generate_prompt(self, template: PromptTemplate, context: Dict[str, Any]) -> str:
        """템플릿별 프롬프트 생성
        
        Args:
            template: 프롬프트 템플릿
            context: 프롬프트 컨텍스트
            
        Returns:
            str: 생성된 프롬프트
        """
        query = context.get("query", "")
        content = context.get("content", "")
        patterns = context.get("patterns", {})
        query_analysis = context.get("query_analysis", {})
        
        if template == PromptTemplate.ANALYSIS:
            # 응답 형식 지정
            response_format = self._get_response_format(query_analysis)
            
            # 분석 지침 생성
            analysis_instructions = self._generate_analysis_instructions(patterns, query_analysis)
            
            return f"""다음 문서를 분석하고 질문에 답변해주세요.

문서 내용:
{content}

질문:
{query}

분석 지침:
{chr(10).join(analysis_instructions)}

응답 형식:
{response_format}"""
            
        elif template == PromptTemplate.TABLE_ANALYSIS:
            return f"""다음 문서에서 요청한 정보를 추출하여 요구형태로 가공해주세요.

문서 내용:
{content}

분석 요청:
{query}

요구사항:
- 문서에서 요청한 정보만을 정확하게 추출해주세요
- 추출한 정보는 테이블 셀에 들어갈 수 있도록 간단명료하게 정리해주세요
- 수치 데이터는 숫자 형태로 변환하여 제시해주세요
- 날짜는 YYYY-MM-DD 형식으로 통일해주세요
- 불필요한 설명이나 부가 정보는 제외해주세요

예시:
[요청] "각 부서의 2023년 4분기 매출액을 알려줘"
[응답] 42000000

[요청] "지난달 입사한 신규 직원의 이름과 부서를 알려줘"
[응답] 홍길동/영업팀

[요청] "이 계약서의 계약기간이 어떻게 되나요?"
[응답] 2024-01-01~2024-12-31

답변 형식:
- 셀에 들어갈 값만 간단히 작성
- 부가 설명 없이 데이터만 제시"""
            
        else:  # TABLE_TITLE
            return f"""사용자의 요청을 테이블 제목으로 변환해주세요.

요청 내용:
{query}

요구사항:
- 요청 내용을 2-3단어로 된 간단한 테이블 제목으로 만들어주세요
- 테이블의 목적과 내용을 잘 나타내는 단어를 선택해주세요
- 불필요한 조사나 부가 설명은 제외해주세요
- 한글로 작성해주세요

예시:
- "2023년도 분기별 매출액과 영업이익을 보여줘" -> "분기실적"
- "부서별 직원 수와 평균 연봉을 알려줘" -> "부서현황"
- "지난 3년간의 주요 제품별 판매량 추이를 분석해줘" -> "제품판매"
- "각 지역 지점의 월별 고객 만족도 점수를 보여줘" -> "만족도현황"

답변 형식:
제목만 2-3단어로 작성해주세요."""

    def _get_response_format(self, query_analysis: Dict[str, Any]) -> str:
        """쿼리 분석 결과에 따른 응답 형식 생성"""
        
        if query_analysis.get("type") == "comparison":
            return """다음 형식으로 답변해주세요:

1. 변화 요약
   - 주요 변화 포인트를 1-2줄로 요약

2. 상세 분석
   - 각 지표별 변화량과 변화율
   - 변화의 주요 원인
   
3. 시사점
   - 이 변화가 의미하는 바
   - 향후 전망"""
            
        elif query_analysis.get("focus") == "financial":
            return """다음 형식으로 답변해주세요:

1. 핵심 지표
   - 요청된 재무 지표의 현재 값
   - 해당 지표의 의미와 중요성

2. 상세 설명
   - 지표에 영향을 미친 주요 요인
   - 산업 평균 또는 경쟁사 대비 수준

3. 분석 결과
   - 재무적 관점에서의 평가
   - 개선 필요 사항 또는 강점"""
        
        else:
            return """다음 형식으로 답변해주세요:

1. 핵심 답변
   - 질문에 대한 직접적인 답변을 1-2줄로 제시

2. 상세 설명
   - 관련된 주요 정보와 데이터
   - 맥락과 배경 설명

3. 결론
   - 종합적 의견 또는 시사점"""

    def _generate_analysis_instructions(self, patterns: Dict[str, Any], query_analysis: Dict[str, Any]) -> List[str]:
        """문서 패턴과 쿼리 분석 결과에 따른 분석 지침 생성"""
        
        instructions = []
        
        # 기본 지침
        instructions.append("- 문서에서 직접 확인할 수 있는 정보만 사용하세요")
        instructions.append("- 추측이나 일반적인 설명은 제외하세요")
        
        # 쿼리 유형별 지침
        if query_analysis.get("focus") == "financial":
            instructions.append("- 재무적 맥락에서 수치를 해석하세요")
            instructions.append("- 증감의 원인과 영향을 분석하세요")
            
            if patterns.get("has_tables"):
                instructions.append("- 표의 데이터를 체계적으로 분석하세요")
                
        if query_analysis.get("time_range") == "multi_year":
            instructions.append("- 연도별 추이를 분석하세요")
            instructions.append("- 주요 변화 시점과 원인을 파악하세요")
            
        if patterns.get("common_terms"):
            terms = ", ".join(patterns["common_terms"])
            instructions.append(f"- 다음 주요 용어들과 관련된 맥락을 설명하세요: {terms}")
            
        return instructions

    async def _process_with_openai(self, template: PromptTemplate, context: Dict[str, Any]) -> str:
        """OpenAI API를 사용한 프롬프트 처리 (폴백 메서드)
        
        Args:
            template: 프롬프트 템플릿
            context: 프롬프트 컨텍스트
            
        Returns:
            str: AI 응답 결과
        """
        try:
            prompt = self._generate_prompt(template, context)
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4-1106-preview",  # GPT-4 Turbo 모델 사용
                messages=[
                    {"role": "system", "content": "당신은 문서를 분석하고 사용자의 질문에 답변하는 AI 어시스턴트입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            raise Exception(f"OpenAI API 처리 중 오류 발생: {str(e)}")
