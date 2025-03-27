import time
from typing import Dict, Any, Optional, List, Callable
import logging

from openai import AsyncOpenAI

from common.core.config import settings
from common.core.cache import AsyncRedisCache, RedisCache
import json
from loguru import logger
from common.utils.util import measure_time_async
from common.services.llm_models import LLMModels
from langchain_core.messages import ai
from common.models.user import Session
from common.models.token_usage import ProjectType

logger = logging.getLogger(__name__)

class BasePrompt:
    prompt_mode = None
    """기본 프롬프트 클래스"""
    def __init__(self, 
                 session: Optional[Session] = None,
                 streaming_callback: Optional[Callable[[str], None]] = None,
                 **kwargs):
        """프롬프트 기본 클래스 초기화
        
        Args:
            session: 사용자 세션 정보 (토큰 사용량 추적에 사용)
            streaming_callback: 스트리밍 응답을 처리할 콜백 함수
        """
        # 구조가 매우 이상하다.
        # 프롬프트 클래스가 왜 LLM Models를 가지고 있지?
        self.session = session
        self.LLM = LLMModels(streaming_callback=streaming_callback)  # 싱글톤 인스턴스
       
        # 캐시 초기화
        self.async_cache = AsyncRedisCache(
            redis_url=settings.REDIS_URL,
            expire_time=settings.REDIS_CACHE_EXPIRE
        )
        self.sync_cache = RedisCache(
            redis_url=settings.REDIS_URL,
            expire_time=settings.REDIS_CACHE_EXPIRE
        )

    async def process_prompt_async(self, user_query: str, prompt_context:str) -> str:
        """프롬프트 처리 기본 메서드
        
        Args:
            prompt: 생성된 프롬프트
            context: 프롬프트 컨텍스트
            
        Returns:
            str: AI 응답 결과
        """
        try:
            # 캐시 키 생성
            # cache_key = f"prompt:{hash(user_query)}"
            # logger.info(f"[process_prompt_async] cache_key : {cache_key}")
            # # 캐시된 결과 확인
            # cached_result = await self.async_cache.get(cache_key, user_query)
            # if cached_result:
            #     logger.info(f"[process_prompt_async] cached_result : {cached_result}")
            #     return cached_result
            # Gemini API로 시도
            try:
                #self.session
                model_info = self.LLM.get_current_llm_info()
                model_name = model_info["model"]
                logger.info(f"[process_prompt_async] {model_name} API 호출 - 프롬프트: {user_query[:100]}...")
                response = await self.generate_content_async(user_query, prompt_context)
                logger.info(f"[process_prompt_async] {model_name} API 호출 완료")

                #response는 그냥 문자열이다.
                if response :
                    # 응답 텍스트 정리
                    #text = response.text.strip()
                    text = response.strip()
                    try:
                        if text.startswith('{') and text.endswith('}'):
                            parsed = json.loads(text)
                            return json.dumps(parsed, ensure_ascii=False)
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
                                
                raise Exception("모든 AI 서비스 호출 실패")
            
        except Exception as e:
            logger.error(f"프롬프트 처리 실패[async]: {str(e)}")
            raise
        finally:
            # 리소스 정리
            #await self._cleanup()
            pass
    @measure_time_async
    def process_prompt(self, user_query:str, prompt_context: str) -> str:
        """프롬프트 처리 기본 메서드
        
        Args:
            prompt: 생성된 프롬프트
            context: 프롬프트 컨텍스트
            
        Returns:
            str: AI 응답 결과
        """
        try:
            # 캐시 키 생성
            cache_key = f"prompt:{hash(user_query)}" # 해시키를 사용자 질문과 매칭.
            
            # #캐시된 결과 확인
            # start_time = time.time()
            cached_result = self.sync_cache.get(cache_key, user_query)
            # end_time = time.time()
            # execution_time = end_time - start_time
            # logger.info(f"캐시 확인 시간: {execution_time:.2f} 초")
            # if cached_result:
            #     logger.info(f"hit cache")
            #     return cached_result
            
            # Gemini API로 시도
            try:
                #logger.info(f"Gemini API 호출 - 프롬프트: {prompt[:20]}...")
                start_time = time.time()
                
                content = self.generate_content(user_query, prompt_context)
                end_time = time.time()
                execution_time = end_time - start_time
                logger.info(f"Gemini API 호출 시간: {execution_time:.2f} 초")

                if content:
                    #self.sync_cache.set(cache_key, user_query, content) # 사용자의 질문:AI응답을 캐시에 저장.
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

    def generate_content(self,  user_query: str, prompt_context: str) -> str:
        """LLM API를 사용하여 컨텐츠 생성"""
        try:
            # self.user_id를 먼저 쓰고, 그 다음에 base.의 self.session.user_id를 쓴다.
            if hasattr(self, 'user_id'):
                user_id = self.user_id
            else:
                user_id = self.session.user_id if self.session else None


            response: ai.AIMessage = self.LLM.generate(
                user_query, 
                prompt_context,
                user_id=user_id,
                project_type=ProjectType.DOCEASY
            )        
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
                if hasattr(self, 'user_id'):
                    user_id = self.user_id
                else:
                    user_id = self.session.user_id if self.session else None

                response: ai.AIMessage = self.LLM.generate(
                    user_query, 
                    prompt_context,
                    user_id=user_id,
                    project_type=ProjectType.DOCEASY
                )        
                if response:
                    # 응답 텍스트 정리
                    text = response.content
                    return text
                return "죄송합니다. 응답을 생성할 수 없습니다."
            except Exception as e:
                #여기서도 에러나면 raise
                raise
                
    async def generate_content_async(self, user_query: str, prompt_context: str) -> str:
        """LLM API를 사용하여 컨텐츠 생성"""
        try:
            # self.user_id를 먼저 쓰고, 그 다음에 base.의 self.session.user_id를 쓴다.
            if hasattr(self, 'user_id'):
                user_id = self.user_id
            else:
                user_id = self.session.user_id if self.session else None

            response: ai.AIMessage = await self.LLM.agenerate(
                user_query, 
                prompt_context,
                user_id=user_id,
                project_type=ProjectType.DOCEASY
            )        
            if response:
                text = response.content
                return text
            return "죄송합니다. 응답을 생성할 수 없습니다."
        except Exception as e:
            self.LLM.select_next_llm() # 다음 우선순위 llm 선택
            try:
                # self.user_id를 먼저 쓰고, 그 다음에 base.의 self.session.user_id를 쓴다.
                if hasattr(self, 'user_id'):
                    user_id = self.user_id
                else:
                    user_id = self.session.user_id if self.session else None
                    
                response: ai.AIMessage = await self.LLM.agenerate(
                    user_query, 
                    prompt_context,
                    user_id=user_id,
                    project_type=ProjectType.DOCEASY
                )        
                if response:
                    # 응답 텍스트 정리
                    text = response.content
                    return text
                return "죄송합니다. 응답을 생성할 수 없습니다."
            except Exception as e:
                #여기서도 에러나면 raise
                raise
    async def generate_content_streaming_async(self, user_query: str, prompt_context: str):
        """LLM API를 사용하여 streaming 컨텐츠 생성"""
        
        try:
            # self.user_id를 먼저 쓰고, 그 다음에 base.의 self.session.user_id를 쓴다.
            if hasattr(self, 'user_id'):
                user_id = self.user_id
            else:
                user_id = self.session.user_id if self.session else None
                
            async for chunk in self.LLM.agenerate_stream(
                user_query, 
                prompt_context,
                user_id=user_id,
                project_type=ProjectType.DOCEASY
            ):
                if hasattr(chunk, 'content'):
                    yield chunk.content
        except Exception as e:
            self.LLM.select_next_llm() # 다음 우선순위 llm 선택
            try:
                # self.user_id를 먼저 쓰고, 그 다음에 base.의 self.session.user_id를 쓴다.
                if hasattr(self, 'user_id'):
                    user_id = self.user_id
                else:
                    user_id = self.session.user_id if self.session else None
                
                async for chunk in self.LLM.agenerate_stream(
                    user_query, 
                    prompt_context,
                    user_id=user_id,
                    project_type=ProjectType.DOCEASY
                ):
                    if hasattr(chunk, 'content'):
                        yield chunk.content
            except Exception as e:
                #여기서도 에러나면 raise
                raise

