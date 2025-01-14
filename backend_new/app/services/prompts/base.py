from typing import Dict, Any, Optional
import logging
import asyncio
from openai import AsyncOpenAI
import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse
from app.core.config import settings
from app.core.cache import AsyncRedisCache

logger = logging.getLogger(__name__)

class BasePrompt:
    def __init__(self, 
                 openai_api_key: Optional[str] = None, 
                 gemini_api_key: Optional[str] = None,
                 redis_url: Optional[str] = None,
                 cache_expire: Optional[int] = None):
        """프롬프트 기본 클래스 초기화
        
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
        
        # gemini-2.0-flash-exp 모델 초기화
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

    async def process_prompt(self, prompt: str, context: Dict[str, Any]) -> str:
        """프롬프트 처리 기본 메서드
        
        Args:
            prompt: 생성된 프롬프트
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
            result = await self._process_with_openai(prompt)
            
        # 응답 캐싱
        if document_id and query:
            await self.cache.set(document_id, query, result)
        
        return result

    async def _process_with_openai(self, prompt: str) -> str:
        """OpenAI API를 사용한 프롬프트 처리 (폴백 메서드)
        
        Args:
            prompt: 생성된 프롬프트
            
        Returns:
            str: AI 응답 결과
        """
        try:
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
