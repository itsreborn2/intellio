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
            # 데이터 타입별 포맷 지침
            format_rules = []
            if query_analysis.get("data_type") == "numeric":
                format_rules.append("- 숫자: 순수 숫자만 (42000000)")
            elif query_analysis.get("data_type") == "date":
                format_rules.append("- 날짜: YYYY-MM-DD (2024-01-01)")
            
            return f"""문서에서 요청한 정보만을 정확히 추출하여 반환하세요.

문서 내용:
{content}

분석 요청:
{query}

필수 규칙:
- 문서에 있는 정보만 추출
- 추론이나 예측 금지
- 설명이나 부가 정보 제외
- 없는 정보는 "N/A"
{chr(10).join(format_rules)}

예시:
Q: 2023년 4분기 매출액
A: 42000000

Q: 계약시작일
A: 2024-01-01

Q: 담당자/부서
A: 홍길동/영업팀

답변:
데이터값만 작성"""
            
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

    def _analyze_query(self, query: str) -> Dict[str, Any]:
        """쿼리 분석 - 사용자 질문의 의도와 필요한 정보를 파악"""
        try:
            normalized_query = self._normalize_query(query)
            
            # 기본 분석 결과
            analysis = {
                "type": "general",      
                "focus": "general",     
                "time_range": None,     
                "data_type": "text",    
                "comparison": False,    
                "trend": False          
            }
            
            # 분석 유형 결정
            if any(keyword in normalized_query for keyword in FINANCIAL_KEYWORDS):
                analysis["focus"] = "financial"
            elif any(keyword in normalized_query for keyword in OPERATIONAL_KEYWORDS):
                analysis["focus"] = "operational"
            elif any(keyword in normalized_query for keyword in STRATEGIC_KEYWORDS):
                analysis["focus"] = "strategic"
                
            # 시간 범위 분석
            for time_range, keywords in TIME_KEYWORDS.items():
                if any(keyword in normalized_query for keyword in keywords):
                    analysis["time_range"] = time_range
                    break
                    
            # 비교 분석 여부 확인
            comparison_keywords = ['대비', '비교', '차이', '증감', '변화']
            if any(keyword in normalized_query for keyword in comparison_keywords):
                analysis["comparison"] = True
                
            # 추세 분석 여부 확인
            trend_keywords = ['추이', '트렌드', '변화', '흐름']
            if any(keyword in normalized_query for keyword in trend_keywords):
                analysis["trend"] = True
                
            # 데이터 타입 분석
            if any(char.isdigit() for char in normalized_query):
                analysis["data_type"] = "numeric"
            elif any(word in normalized_query for word in ['날짜', '일자', '기간']):
                analysis["data_type"] = "date"
                
            return analysis
            
        except Exception as e:
            logger.error(f"쿼리 분석 실패: {str(e)}")
            # 기본값 반환
            return {
                "type": "general",
                "focus": "general",
                "time_range": None,
                "data_type": "text",
                "comparison": False,
                "trend": False
            }

    def _get_response_format(self, query_analysis: Dict[str, Any]) -> str:
        """쿼리 분석 결과에 따른 응답 형식 생성"""
        
        # 기본 응답 구조
        base_format = """다음 형식으로 답변해주세요:

1. 핵심 답변
   - 질문에 대한 직접적인 답변
   {core_metrics}
   
2. 상세 분석
   {detail_format}
   
3. 결론
   - 주요 시사점
   - {conclusion_focus}"""
        
        # 분석 유형별 상세 포맷
        detail_formats = {
            "financial": """
   - 주요 재무 지표 분석
   - 증감 원인 분석
   - 산업 평균 대비 수준""",
               
            "operational": """
   - 운영 효율성 분석
   - 주요 개선점
   - 리스크 요인""",
            
            "strategic": """
   - 시장 환경 분석
   - 경쟁사 대비 포지션
   - 전략적 시사점""",
               
            "general": """
   - 주요 내용 분석
   - 핵심 포인트
   - 관련 맥락 설명"""
        }
        
        # 결론 포커스
        conclusion_focuses = {
            "financial": "재무적 개선 방향",
            "operational": "운영 효율화 방안",
            "strategic": "전략적 제언",
            "general": "주요 시사점"
        }
        
        # 핵심 지표 포맷
        core_metrics = ""
        if query_analysis.get("data_type") == "numeric":
            core_metrics = "\n   - 관련 수치 데이터"
        if query_analysis.get("comparison"):
            core_metrics += "\n   - 비교 분석 결과"
        if query_analysis.get("trend"):
            core_metrics += "\n   - 주요 변화 추이"
        
        focus = query_analysis.get("focus", "general")
        if focus not in detail_formats:
            focus = "general"
            
        return base_format.format(
            core_metrics=core_metrics,
            detail_format=detail_formats[focus],
            conclusion_focus=conclusion_focuses[focus]
        )

    def _generate_analysis_instructions(self, patterns: Dict[str, Any], query_analysis: Dict[str, Any]) -> List[str]:
        """문서 패턴과 쿼리 분석 결과에 따른 분석 지침 생성"""
        
        instructions = [
            "- 문서의 직접적인 정보만 사용하세요",
            "- 추측성 정보는 제외하세요"
        ]
        
        # 분석 유형별 지침
        focus = query_analysis.get("focus")
        if focus == "financial":
            instructions.extend([
                "- 수치는 정확한 값으로 인용하세요",
                "- 증감률은 %로 표시하세요",
                "- 주요 재무비율을 계산하여 제시하세요"
            ])
        elif focus == "operational":
            instructions.extend([
                "- 구체적인 수치와 함께 설명하세요",
                "- 개선 가능한 부분을 지적하세요",
                "- 리스크 요인을 명시하세요"
            ])
        elif focus == "strategic":
            instructions.extend([
                "- 시장 상황을 고려하여 분석하세요",
                "- 경쟁사 정보를 포함하세요",
                "- 중장기 관점에서 평가하세요"
            ])
            
        # 시간 범위별 지침
        time_range = query_analysis.get("time_range")
        if time_range == "multi_year":
            instructions.extend([
                "- 연도별 추이를 분석하세요",
                "- 주요 변화 시점을 파악하세요"
            ])
        elif time_range in ["monthly", "quarterly"]:
            instructions.extend([
                "- 기간별 변화를 상세히 분석하세요",
                "- 특이사항이 있는 기간을 표시하세요"
            ])
            
        # 비교 분석 지침
        if query_analysis.get("comparison"):
            instructions.extend([
                "- 명확한 비교 기준을 제시하세요",
                "- 주요 차이점을 구체적으로 설명하세요"
            ])
            
        # 데이터 타입별 지침
        data_type = query_analysis.get("data_type")
        if data_type == "numeric":
            instructions.extend([
                "- 모든 수치는 정확히 표기하세요",
                "- 단위를 명확히 표시하세요"
            ])
        elif data_type == "date":
            instructions.extend([
                "- 날짜 형식을 YYYY-MM-DD로 통일하세요",
                "- 기간을 명확히 표시하세요"
            ])
            
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

# 분석 관련 상수 정의
FINANCIAL_KEYWORDS = [
    '매출', '이익', '손실', '비용', '자산', '부채', '자본', 
    'ROI', 'ROE', '수익', '영업이익', '당기순이익', '매출액',
    '재무', '투자', '예산', '원가'
]

OPERATIONAL_KEYWORDS = [
    '생산', '공정', '품질', '재고', '효율', '운영', '프로세스',
    '생산성', '불량', '납기', '가동', '설비', '인력', '자원'
]

STRATEGIC_KEYWORDS = [
    '전략', '계획', '목표', '경쟁', '시장', '성장', '확장',
    '개발', '혁신', '리스크', '기회', '위험', '전망'
]

TIME_KEYWORDS = {
    'single_point': ['현재', '현황', '상태', '지금'],
    'monthly': ['월간', '매월', '월별'],
    'quarterly': ['분기', '분기별'],
    'yearly': ['연간', '연도별', '년간'],
    'multi_year': ['추이', '트렌드', '변화', '연도별']
}
