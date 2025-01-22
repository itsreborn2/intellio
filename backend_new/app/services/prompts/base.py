import time
from typing import Dict, Any, Optional
import logging
import asyncio
import threading
import os
from openai import AsyncOpenAI
import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse
from app.core.config import settings
from app.core.cache import AsyncRedisCache, RedisCache
import json
from loguru import logger
from app.utils.common import measure_time_async

logger = logging.getLogger(__name__)

class GeminiAPI:
    """Gemini API 싱글톤"""
    _instance = None
    _model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize(self, api_key: str, **kwargs):
        """API 초기화"""
        if self._model is None:
            generation_config = kwargs.get('generation_config', {
                "temperature": 0.3,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 8192,
            })
            
            safety_settings = kwargs.get('safety_settings', [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ])
            
            logger.info("Gemini API 초기화")
            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel(
                model_name=kwargs.get('model_name', "models/gemini-2.0-flash-exp"),
                generation_config=genai.GenerationConfig(**generation_config),
                safety_settings=safety_settings
            )
            logger.info("Gemini API 초기화 완료")
    
    def generate_content(self, prompt: str) -> Optional[GenerateContentResponse]:
        """동기 컨텐츠 생성"""
        if self._model is None:
            self.initialize(settings.GEMINI_API_KEY)
            
        logger.info(f"Gemini API[Sync] 호출 - 프롬프트: {prompt[:100]}...")
        response = self._model.generate_content(prompt)
        logger.info("Gemini API 호출 완료")
        return response

    async def generate_content_async(self, prompt: str) -> Optional[GenerateContentResponse]:
        """비동기 컨텐츠 생성"""
        if self._model is None:
            self.initialize(settings.GEMINI_API_KEY)
            
        logger.info(f"Gemini API[Async] 호출 - 프롬프트: {prompt[:100]}...")
        response = await self._model.generate_content_async(prompt)
        logger.info("Gemini API 호출 완료")
        return response

class BasePrompt:
    """기본 프롬프트 클래스"""
    def __init__(self, 
                 openai_api_key: Optional[str] = None, 
                 gemini_api_key: Optional[str] = None,
                 redis_url: Optional[str] = None,
                 cache_expire: Optional[int] = None,
                 document_id: str = "default",  
                 **kwargs):
        """프롬프트 기본 클래스 초기화
        
        Args:
            openai_api_key: OpenAI API 키 (선택)
            gemini_api_key: Gemini API 키 (선택)
            redis_url: Redis 서버 URL (선택)
            cache_expire: 캐시 만료 시간 (초)
            document_id: 문서 ID (기본값: "default")
        """
        self.gemini_api = GeminiAPI()  # 싱글톤 인스턴스
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
                logger.info(f"[process_prompt_async] gemini_api._model : {self.gemini_api._model}")
                if self.gemini_api._model is None:
                    #self.gemini_api.initialize(settings.GEMINI_API_KEY)
                    logger.info(f"[process_prompt_async] gemini_api. initialize")
                    self.gemini_api = GeminiAPI()
                    if self.gemini_api._model is None:
                        logger.info(f"[process_prompt_async] gemini_api. initialize again")
                        self.gemini_api.initialize(settings.GEMINI_API_KEY)
                logger.info(f"Gemini API 호출 [ThreadID: {threading.get_ident()}, ProcessID: {os.getpid()}]")
                logger.info(f"Gemini API 호출 - 프롬프트: {prompt[:100]}...")
                response = await self.gemini_api._model.generate_content_async(prompt)
                logger.info("Gemini API 호출 완료")

                if response and response.text:
                    # 응답 텍스트 정리
                    text = response.text.strip()
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

                logger.error("Gemini API 응답이 비어있음")
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
                logger.error(f"Gemini API 오류: {str(e)}")
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
                #logger.info(f"[process_prompt] gemini_api._model : {self.gemini_api._model}")
                if self.gemini_api._model is None:
                    #self.gemini_api.initialize(settings.GEMINI_API_KEY)
                    logger.info(f"[process_prompt] gemini_api. initialize")
                    self.gemini_api = GeminiAPI()
                    if self.gemini_api._model is None:
                        logger.info(f"[process_prompt] gemini_api. initialize again")
                        self.gemini_api.initialize(settings.GEMINI_API_KEY)
                logger.info(f"Gemini API 호출[Sync] [ThreadID: {threading.get_ident()}, ProcessID: {os.getpid()}]")
                #logger.info(f"Gemini API 호출 - 프롬프트: {prompt[:20]}...")
                start_time = time.time()
                response = self.gemini_api._model.generate_content(prompt)
                end_time = time.time()
                execution_time = end_time - start_time
                logger.info(f"Gemini API 호출 시간: {execution_time:.2f} 초")
                
                
                logger.info("Gemini API 호출 완료")

                if response and response.text:
                    # 응답 텍스트 정리
                    text = response.text.strip()
                    try:
                        if text.startswith('{') and text.endswith('}'):
                            parsed = json.loads(text)
                            self.sync_cache.set(cache_key, prompt, parsed)
                            return json.dumps(parsed, ensure_ascii=False)

                        self.sync_cache.set(cache_key, prompt, text)
                        return text
                    except json.JSONDecodeError:
                        logger.warning(f"JSON 파싱 실패: {text[:100]}...")
                        return text

                logger.error("Gemini API 응답이 비어있음")
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
                logger.error(f"Gemini API 오류: {str(e)}")
                # OpenAI로 폴백
                # result = await self._process_with_openai(prompt)
                # if result:
                #     await self.cache.set(cache_key, prompt, result)
                #     return result
                raise
                
            raise Exception("모든 AI 서비스 호출 실패")
            
        except Exception as e:
            logger.error(f"프롬프트 처리 실패[sync]: {str(e)}")
            raise
        finally:
            # 리소스 정리
            # loop = asyncio.new_event_loop()
            # asyncio.set_event_loop(loop)
            # loop.run_until_complete(self._cleanup())
            pass
            

    async def _cleanup(self):
        """리소스 정리"""
        try:
            if hasattr(self, 'openai_client'):
                await self.openai_client.close()
        except Exception as e:
            logger.error(f"리소스 정리 중 오류 발생: {str(e)}")

    async def _generate_content(self, prompt: str) -> str:
        """Gemini API를 사용하여 컨텐츠 생성"""
        try:
            if self.gemini_api._model is None:
                #self.initialize(settings.GEMINI_API_KEY)
                self.gemini_api = GeminiAPI()
            
            logger.info(f"Gemini API 호출 - 프롬프트: {prompt[:100]}...")
            response = await self.gemini_api._model.generate_content_async(prompt)
            logger.info("Gemini API 호출 완료")
            if response and response.text:
                # 응답 텍스트 정리
                text = response.text.strip()
                
                try:
                    # JSON 형식인지 확인하고 파싱
                    import json
                    if text.startswith('{') and text.endswith('}'):
                        parsed = json.loads(text)
                        return json.dumps(parsed, ensure_ascii=False)
                    return text
                except json.JSONDecodeError:
                    logger.warning(f"JSON 파싱 실패: {text[:100]}...")
                    return text
            else:
                logger.error("Gemini API 응답이 비어있음")
                return json.dumps({
                    "content": "응답을 생성할 수 없습니다.",
                    "metadata": {
                        "confidence": 0.0,
                        "source": "error",
                        "context": "empty_response"
                    }
                }, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Gemini 컨텐츠 생성 실패: {str(e)}")
            return json.dumps({
                "content": f"컨텐츠 생성 중 오류 발생: {str(e)}",
                "metadata": {
                    "confidence": 0.0,
                    "source": "error",
                    "context": "generation_error"
                }
            }, ensure_ascii=False)

    async def _process_with_openai(self, prompt: str) -> Optional[str]:
        """OpenAI API를 사용한 프롬프트 처리 (폴백 메서드)
    
        Args:
            prompt: 생성된 프롬프트
            
        Returns:
            str: AI 응답 결과
        """
        try:
            # 캐시된 응답이 있는지 확인
            cached_response = await self.cache.get(self.document_id, prompt)
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
                    await self.cache.set(self.document_id, prompt, result)
                    logger.debug(f"응답 캐시 저장 완료 (문서 ID: {self.document_id})")
                except Exception as cache_error:
                    logger.warning(f"캐시 저장 실패 (문서 ID: {self.document_id}): {str(cache_error)}")
                return result
                
            logger.warning(f"OpenAI API 응답이 비어있음 (문서 ID: {self.document_id})")
            return None
            
        except Exception as e:
            logger.error(f"OpenAI 처리 실패 (문서 ID: {self.document_id}): {str(e)}", exc_info=True)
            return None
