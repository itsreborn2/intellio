import time
from typing import Dict, Any, Optional, List, Callable
import logging

from openai import AsyncOpenAI
import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse
from app.core.config import settings
from app.core.cache import AsyncRedisCache, RedisCache
import json
from loguru import logger
from app.utils.common import measure_time_async
from app.services.llm_models import LLMModels
from langchain_core.messages import ai


logger = logging.getLogger(__name__)

# 안씀.
class GeminiAPI:
    """Gemini API 싱글톤"""
    _instance = None
    _llm_chain = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize(self, api_key: str, **kwargs):
        """API 초기화"""
        if self._llm_chain is None:
            generation_config = kwargs.get('generation_config', {
                "temperature": 0.3,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
            })
            
            safety_settings = kwargs.get('safety_settings', [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ])
            
            logger.info("Gemini API 초기화")
            genai.configure(api_key=api_key)
            self._llm_chain = genai.GenerativeModel(
                model_name=kwargs.get('model_name', "models/gemini-2.0-flash-exp"),
                generation_config=genai.GenerationConfig(**generation_config),
                safety_settings=safety_settings
            )
            logger.info("Gemini API 초기화 완료")
    
    def generate_content(self, prompt: str) -> Optional[GenerateContentResponse]:
        """동기 컨텐츠 생성"""
        if self._llm_chain is None:
            self.initialize(settings.GEMINI_API_KEY)
            
        logger.info(f"Gemini API[Sync] 호출 - 프롬프트: {prompt[:100]}...")
        response = self._llm_chain.generate_content(prompt)
        logger.info("Gemini API 호출 완료")
        return response

    async def generate_content_async(self, prompt: str) -> Optional[GenerateContentResponse]:
        """비동기 컨텐츠 생성"""
        if self._llm_chain is None:
            self.initialize(settings.GEMINI_API_KEY)
            
        logger.info(f"Gemini API[Async] 호출 - 프롬프트: {prompt[:100]}...")
        response = await self._llm_chain.generate_content_async(prompt)
        logger.info("Gemini API 호출 완료")
        return response

    
class BasePrompt:
    prompt_mode = None
    """기본 프롬프트 클래스"""
    def __init__(self, 
                 openai_api_key: Optional[str] = None, 
                 gemini_api_key: Optional[str] = None,
                 redis_url: Optional[str] = None,
                 cache_expire: Optional[int] = None,
                 document_id: str = "default",  
                 streaming_callback: Optional[Callable[[str], None]] = None,
                 **kwargs):
        """프롬프트 기본 클래스 초기화
        
        Args:
            openai_api_key: OpenAI API 키 (선택)
            gemini_api_key: Gemini API 키 (선택)
            redis_url: Redis 서버 URL (선택)
            cache_expire: 캐시 만료 시간 (초)
            document_id: 문서 ID (기본값: "default")
            streaming_callback: 스트리밍 응답을 처리할 콜백 함수
        """
        #self.gemini_api = GeminiAPI()  # 싱글톤 인스턴스
        self.LLM = LLMModels(streaming_callback=streaming_callback)  # 싱글톤 인스턴스
        self.gemini_api_key = gemini_api_key or settings.GEMINI_API_KEY
        self.openai_api_key = openai_api_key or settings.OPENAI_API_KEY
        self.document_id = document_id
        
        # OpenAI 클라이언트 초기화
        self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
        
        # 캐시 초기화
        self.async_cache = AsyncRedisCache(
            redis_url=redis_url or settings.REDIS_URL,
            expire_time=cache_expire or settings.REDIS_CACHE_EXPIRE
        )
        self.sync_cache = RedisCache(
            redis_url=redis_url or settings.REDIS_URL,
            expire_time=cache_expire or settings.REDIS_CACHE_EXPIRE
        )

    async def process_prompt_async(self, prompt: str, context: Dict[str, Any]) -> str:
        """프롬프트 처리 기본 메서드
        
        Args:
            prompt: 생성된 프롬프트
            context: 프롬프트 컨텍스트
            
        Returns:
            str: AI 응답 결과
        """
        try:
            # 캐시 키 생성
            cache_key = f"prompt:{hash(prompt)}"
            logger.info(f"[process_prompt_async] cache_key : {cache_key}")
            # 캐시된 결과 확인
            cached_result = await self.async_cache.get(cache_key, prompt)
            if cached_result:
                logger.info(f"[process_prompt_async] cached_result : {cached_result}")
                return cached_result
            # Gemini API로 시도
            try:
                #self.LLM.change_llm("kf-deberta", None)
                model_info = self.LLM.get_current_llm_info()
                model_name = model_info["model"]
                logger.info(f"{model_name} API 호출 - 프롬프트: {prompt[:100]}...")
                #response = await self.gemini_api._llm_chain.generate_content_async(prompt)
                if self.prompt_mode == "chat":
                    response = await self.generate_content_streaming_async(prompt)
                else:   
                    response = await self.generate_content_async(prompt)
                logger.info(f"{model_name} API 호출 완료")

                #response는 그냥 문자열이다.
                if response :
                    # 응답 텍스트 정리
                    #text = response.text.strip()
                    text = response.strip()
                    try:
                        if text.startswith('{') and text.endswith('}'):
                            parsed = json.loads(text)
                            await self.async_cache.set(cache_key, prompt, parsed)
                            return json.dumps(parsed, ensure_ascii=False)

                        await self.async_cache.set(cache_key, prompt, text)
                        return text
                    except json.JSONDecodeError:
                        logger.warning(f"JSON 파싱 실패: {text[:100]}...")
                        return text

                logger.error(f"{model_name} API 응답이 비어있음")
                return json.dumps({
                    "content": "응답을 생성할 수 없습니다.",
                    "metadata": {
                        "confidence": 0.0,
                        "source": "error",
                        "context": "empty_response"
                    }
                }, ensure_ascii=False)

                #result = await self._generate_content(prompt)
                # if result:
                #     # 결과 캐시 저장
                #     await self.cache.set(cache_key, prompt, result)
                #     return result
            except Exception as e:
                logger.error(f"{model_name} API 오류: {str(e)}")
                # OpenAI로 폴백
                result = await self._process_with_openai(prompt)
                if result:
                    await self.cache.set(cache_key, prompt, result)
                    return result
                
            raise Exception("모든 AI 서비스 호출 실패")
            
        except Exception as e:
            logger.error(f"프롬프트 처리 실패[async]: {str(e)}")
            raise
        finally:
            # 리소스 정리
            await self._cleanup()
    @measure_time_async
    def process_prompt(self, prompt: str, context: Dict[str, Any]) -> str:
        """프롬프트 처리 기본 메서드
        
        Args:
            prompt: 생성된 프롬프트
            context: 프롬프트 컨텍스트
            
        Returns:
            str: AI 응답 결과
        """
        try:
            # 캐시 키 생성
            cache_key = f"prompt:{hash(prompt)}"
            
            #캐시된 결과 확인
            start_time = time.time()
            cached_result = self.sync_cache.get(cache_key, prompt)
            end_time = time.time()
            execution_time = end_time - start_time
            logger.info(f"캐시 확인 시간: {execution_time:.2f} 초")
            if cached_result:
                logger.info(f"hit cache")
                return cached_result
            
            # Gemini API로 시도
            try:
                #logger.info(f"Gemini API 호출 - 프롬프트: {prompt[:20]}...")
                start_time = time.time()
                content = self.generate_content(prompt)
                end_time = time.time()
                execution_time = end_time - start_time
                logger.info(f"Gemini API 호출 시간: {execution_time:.2f} 초")

                if content:
                    self.sync_cache.set(cache_key, prompt, content)
                    return content

                logger.error("Gemini API 응답이 비어있음")
                return "죄송합니다. 응답을 생성할 수 없습니다"
                
            except Exception as e:
                logger.error(f"Gemini API 오류: {str(e)}")
                raise
                
            raise Exception("모든 AI 서비스 호출 실패")
            
        except Exception as e:
            logger.error(f"프롬프트 처리 실패[sync]: {str(e)}")
            raise
        finally:
            pass
            

    async def _cleanup(self):
        """리소스 정리"""
        try:
            if hasattr(self, 'openai_client'):
                await self.openai_client.close()
        except Exception as e:
            logger.error(f"리소스 정리 중 오류 발생: {str(e)}")
    def generate_content(self, prompt: str) -> str:
        """LLM API를 사용하여 컨텐츠 생성"""
        try:
            response: ai.AIMessage = self.LLM.generate(prompt)        
            if response:
                # 응답 텍스트 정리
                text = response.content
                #logger.info(f"Gemini API 응답 text: {text}")
                # 파싱 필요 없음.
                return text
            return "죄송합니다. 응답을 생성할 수 없습니다."
        except Exception as e:
            self.LLM.select_next_llm() # 다음 우선순위 llm 선택
            try:
                response: ai.AIMessage = self.LLM.generate(prompt)        
                if response:
                    # 응답 텍스트 정리
                    text = response.content
                    return text
                return "죄송합니다. 응답을 생성할 수 없습니다."
            except Exception as e:
                #여기서도 에러나면 raise
                raise
    async def generate_content_async(self, prompt: str) -> str:
        """LLM API를 사용하여 컨텐츠 생성"""
        try:
            response: ai.AIMessage = await self.LLM.agenerate(prompt)        
            if response:
                text = response.content
                return text
            return "죄송합니다. 응답을 생성할 수 없습니다."
        except Exception as e:
            self.LLM.select_next_llm() # 다음 우선순위 llm 선택
            try:
                response: ai.AIMessage = await self.LLM.agenerate(prompt)        
                if response:
                    # 응답 텍스트 정리
                    text = response.content
                    return text
                return "죄송합니다. 응답을 생성할 수 없습니다."
            except Exception as e:
                #여기서도 에러나면 raise
                raise
    async def generate_content_streaming_async(self, prompt: str):
        """LLM API를 사용하여 streaming 컨텐츠 생성"""
        try:
            async for chunk in self.LLM.agenerate_stream(prompt=prompt):
                if hasattr(chunk, 'content'):
                    yield chunk.content
        except Exception as e:
            self.LLM.select_next_llm() # 다음 우선순위 llm 선택
            try:
                async for chunk in self.LLM.agenerate_stream(prompt=prompt):
                    if hasattr(chunk, 'content'):
                        yield chunk.content
            except Exception as e:
                #여기서도 에러나면 raise
                raise


    async def _process_with_openai(self, prompt: str) -> Optional[str]:
        """OpenAI API를 사용한 프롬프트 처리 (폴백 메서드)
    
        Args:
            prompt: 생성된 프롬프트
            
        Returns:
            str: AI 응답 결과
        """
        try:
            # 캐시된 응답이 있는지 확인
            cached_response = await self.async_cache.get(self.document_id, prompt)
            if cached_response:
                logger.debug(f"캐시된 응답 사용 (문서 ID: {self.document_id})")
                return cached_response

            # OpenAI API 호출
            logger.debug(f"OpenAI API 호출 시작 (문서 ID: {self.document_id})")
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{
                    "role": "system",
                    "content": "You are a helpful assistant that processes prompts and provides concise responses."
                }, {
                    "role": "user",
                    "content": prompt
                }],
                temperature=0.3,
                max_tokens=1000
            )
            
            if response and response.choices:
                result = response.choices[0].message.content.strip()
                # 응답을 캐시에 저장
                try:
                    await self.async_cache.set(self.document_id, prompt, result)
                    logger.debug(f"응답 캐시 저장 완료 (문서 ID: {self.document_id})")
                except Exception as cache_error:
                    logger.warning(f"캐시 저장 실패 (문서 ID: {self.document_id}): {str(cache_error)}")
                return result
                
            logger.warning(f"OpenAI API 응답이 비어있음 (문서 ID: {self.document_id})")
            return None
            
        except Exception as e:
            logger.error(f"OpenAI 처리 실패 (문서 ID: {self.document_id}): {str(e)}", exc_info=True)
            return None
