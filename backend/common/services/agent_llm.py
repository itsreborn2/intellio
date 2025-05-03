"""
에이전트별 LLM 관리 모듈

이 모듈은 에이전트별 LLM 관리를 위한 기능을 제공합니다.
에이전트 이름을 기반으로 적절한 LLM 설정을 로드하고 LLM 인스턴스를 생성합니다.
"""

import time
from typing import Dict, Any, Optional, Callable, List, Tuple, Union, Awaitable, AsyncGenerator
from loguru import logger
from functools import lru_cache
import asyncio

from langchain_core.language_models import BaseChatModel
from langchain_core.callbacks import BaseCallbackHandler

from common.services.llm_config.llm_config_manager import get_agent_llm_config, llm_config_manager
from common.services.llm_factory import LLMFactory

class AgentLLM:
    """에이전트별 LLM 관리 클래스"""
    
    def __init__(self, agent_name: str):
        """
        에이전트별 LLM 관리자 초기화
        
        Args:
            agent_name: 에이전트 이름
        """
        self.agent_name = agent_name
        self.llm_config = get_agent_llm_config(agent_name)
        self.llm: Optional[BaseChatModel] = None
        self.llm_streaming: Optional[BaseChatModel] = None
        self.streaming_callback: Optional[Callable[[str], None]] = None
        self.fallback_settings = llm_config_manager.get_fallback_settings()
        
        #logger.info(f"AgentLLM 초기화: {agent_name}, provider={self.llm_config.get('provider')}, model={self.llm_config.get('model_name')}")
        
        # 폴백 설정 로그
        # if self.fallback_settings.get("enabled", False):
        #     logger.debug(f"폴백 활성화됨: 최대 재시도 횟수={self.fallback_settings.get('max_retries', 3)}, 폴백 제공자 수={len(self.fallback_settings.get('providers', []))}")
    
    def get_model_name(self) -> str:
        """
        현재 설정된 모델 이름 반환
        
        Returns:
            모델 이름
        """
        return self.llm_config.get("model_name", "")
    
    def get_provider(self) -> str:
        """
        현재 설정된 제공자 반환
        
        Returns:
            제공자 이름
        """
        return self.llm_config.get("provider", "")
    
    def get_llm(self, refresh: bool = False) -> BaseChatModel:
        """
        에이전트 LLM 인스턴스 반환
        
        Args:
            refresh: 설정 새로고침 여부
            
        Returns:
            LLM 인스턴스
        """
        # 설정 새로고침 또는 LLM이 없는 경우 LLM 생성
        if refresh or self.llm is None:
            # 설정 새로고침
            self.llm_config = get_agent_llm_config(self.agent_name)
            self.fallback_settings = llm_config_manager.get_fallback_settings()
            
            # LLM 생성 (폴백 포함)
            self.llm = self._create_llm_with_fallback()
            
            logger.debug(f"LLM 생성 완료: {self.agent_name}, provider={self.llm_config.get('provider')}, model={self.llm_config.get('model_name')}")
        
        return self.llm
    
    def get_streaming_llm(self, callback: Optional[Callable[[str], None]] = None) -> BaseChatModel:
        """
        스트리밍 LLM 인스턴스 반환
        
        Args:
            callback: 스트리밍 콜백 함수
            
        Returns:
            스트리밍 LLM 인스턴스
        """
        # 콜백 변경 또는 LLM이 없는 경우 LLM 생성
        if callback != self.streaming_callback or self.llm_streaming is None:
            # 콜백 저장
            self.streaming_callback = callback
            
            # 콜백 핸들러 설정
            callback_handler = None
            if callback:
                from langchain_core.callbacks import BaseCallbackHandler
                
                class StreamingCallback(BaseCallbackHandler):
                    def __init__(self, callback_fn):
                        self.callback_fn = callback_fn
                        
                    def on_llm_new_token(self, token: str, **kwargs):
                        if self.callback_fn:
                            self.callback_fn(token)
                
                callback_handler = StreamingCallback(callback)
            
            # 설정 새로고침
            self.llm_config = get_agent_llm_config(self.agent_name)
            self.fallback_settings = llm_config_manager.get_fallback_settings()
            
            # 스트리밍 LLM 생성 (폴백 포함)
            self.llm_streaming = self._create_llm_with_fallback(streaming=True, callback_handler=callback_handler)
            
            logger.debug(f"스트리밍 LLM 생성 완료: {self.agent_name}")
        
        return self.llm_streaming
    
    def _create_llm_with_fallback(
        self, 
        streaming: bool = False, 
        callback_handler: Optional[BaseCallbackHandler] = None
    ) -> BaseChatModel:
        """
        폴백 메커니즘을 사용하여 LLM 생성
        
        주 제공자로 LLM 생성에 실패하면 폴백 제공자를 차례로 시도합니다.
        
        Args:
            streaming: 스트리밍 활성화 여부
            callback_handler: 스트리밍 콜백 핸들러
            
        Returns:
            LLM 인스턴스
            
        Raises:
            Exception: 모든 폴백이 실패하면 마지막 예외 발생
        """
        # 폴백이 비활성화되어 있으면 그냥 LLM 생성
        if not self.fallback_settings.get("enabled", False):
            return LLMFactory.create_llm_from_config(
                self.llm_config,
                streaming=streaming,
                callback_handler=callback_handler
            )
        
        # 원래 설정으로 먼저 시도
        try:
            return LLMFactory.create_llm_from_config(
                self.llm_config,
                streaming=streaming,
                callback_handler=callback_handler
            )
        except Exception as e:
            # 원래 설정 실패 로그
            logger.warning(f"기본 LLM 생성 실패: {self.agent_name}, provider={self.llm_config.get('provider')}, 오류: {str(e)}")
            logger.info(f"폴백 시도 중: {self.agent_name}")
            
            # 마지막 예외 기록
            last_exception = e
            
            # 폴백 제공자 시도
            fallback_providers = self.fallback_settings.get("providers", [])
            max_retries = self.fallback_settings.get("max_retries", 3)
            
            for retry in range(min(max_retries, len(fallback_providers))):
                try:
                    # 재시도 간격
                    if retry > 0:
                        time.sleep(1.0)  # 1초 대기
                    
                    # 폴백 제공자 설정
                    fallback_config = fallback_providers[retry]
                    
                    logger.info(f"폴백 시도 {retry+1}/{max_retries}: {self.agent_name}, provider={fallback_config.get('provider')}, model={fallback_config.get('model_name')}")
                    
                    # 폴백으로 LLM 생성
                    return LLMFactory.create_llm_from_config(
                        fallback_config,
                        streaming=streaming,
                        callback_handler=callback_handler
                    )
                except Exception as e:
                    # 폴백 실패 로그
                    logger.warning(f"폴백 LLM 생성 실패 ({retry+1}/{max_retries}): provider={fallback_config.get('provider')}, 오류: {str(e)}")
                    last_exception = e
            
            # 모든 폴백 실패
            logger.error(f"모든 폴백 시도 실패: {self.agent_name}")
            raise last_exception
    
    def invoke_with_fallback(self, *args, **kwargs) -> Any:
        """
        폴백 메커니즘을 사용하여 LLM 동기 호출
        
        주 LLM이 실패하면 폴백 LLM을 차례로 시도합니다.
        
        Args:
            *args: LLM.invoke에 전달할 위치 인자
            **kwargs: LLM.invoke에 전달할 키워드 인자
            
        Returns:
            LLM 응답
            
        Raises:
            Exception: 모든 폴백이 실패하면 마지막 예외 발생
        """
        # 토큰 사용량 추적을 위한 매개변수 추출
        user_id = kwargs.pop("user_id", None)
        project_type = kwargs.pop("project_type", None)
        db = kwargs.pop("db", None)
        
        # 토큰 추적 설정
        use_token_tracking = user_id is not None and project_type is not None and db is not None
        
        if use_token_tracking:
            from common.services.token_usage_service import track_token_usage
            
            logger.info(f"[토큰 추적][동기] invoke_with_fallback 토큰 추적 활성화: user_id={user_id}, project_type={project_type}")
        
        # 폴백이 비활성화되어 있으면 그냥 호출
        if not self.fallback_settings.get("enabled", False):
            if use_token_tracking:
                # 토큰 추적 컨텍스트 생성
                with track_token_usage(
                    user_id=user_id,
                    project_type=project_type,
                    token_type="llm",
                    model_name=self.get_model_name(),
                    db_getter=db
                ) as tracker:
                    # LLM 호출
                    result = self.get_llm().invoke(*args, **kwargs)
                    
                    # API 응답에서 토큰 사용량 추출 시도
                    usage_info = None
                    if hasattr(result, 'usage_metadata'):
                        usage_info = {
                            "prompt_tokens": result.usage_metadata.get('input_tokens', 0),
                            "completion_tokens": result.usage_metadata.get('output_tokens', 0),
                            "total_tokens": result.usage_metadata.get('total_tokens', 0)
                        }
                    
                    if usage_info:
                        # 추출된 토큰 정보 사용
                        tracker.add_tokens(
                                prompt_tokens=usage_info['prompt_tokens'],
                                completion_tokens=usage_info['completion_tokens'],
                                total_tokens=usage_info['total_tokens']
                            )
                    
                    return result
            else:
                # 추적 없이 호출
                return self.get_llm().invoke(*args, **kwargs)
        
        # 폴백 활성화 시 재시도 로직
        last_exception = None
        base_providers = [None]  # None은 원래 설정
        fallback_providers = self.fallback_settings.get("providers", [])
        max_retries = self.fallback_settings.get("max_retries", 3)
        providers_to_try = base_providers + fallback_providers[:max_retries-1]
        
        for provider_idx, provider_config in enumerate(providers_to_try):
            try:
                # 재시도 간격
                if provider_idx > 0:
                    time.sleep(1.0)
                
                # 로깅
                if provider_idx == 0:
                    logger.info(f"기본 LLM으로 호출 시도: {self.agent_name}, provider={self.llm_config.get('provider')}")
                else:
                    logger.info(f"폴백 LLM으로 호출 시도 ({provider_idx}/{max_retries}): provider={provider_config.get('provider')}")
                
                # 토큰 추적 필요시
                if use_token_tracking:
                    # 현재 설정에 맞는 모델 이름 가져오기
                    model_name = self.get_model_name() if provider_idx == 0 else provider_config.get("model_name")
                    
                    with track_token_usage(
                        user_id=user_id,
                        project_type=project_type,
                        token_type="llm",
                        model_name=model_name,
                        db_getter=db
                    ) as tracker:
                        # 필요시 LLM 설정 변경
                        if provider_idx > 0:
                            # 임시 폴백 LLM 설정
                            self.llm_config = provider_config
                            self.llm = None  # 다음 get_llm()에서 새로 생성하게 함
                        
                        # LLM 호출
                        result = self.get_llm().invoke(*args, **kwargs)
                        
                        # API 응답에서 토큰 사용량 추출 시도
                        usage_info = None
                        if hasattr(result, 'usage_metadata'):
                            usage_info = {
                                "prompt_tokens": result.usage_metadata.get('input_tokens', 0),
                                "completion_tokens": result.usage_metadata.get('output_tokens', 0),
                                "total_tokens": result.usage_metadata.get('total_tokens', 0)
                            }
                        
                        if usage_info:
                            # 추출된 토큰 정보 사용
                            tracker.add_tokens(
                                prompt_tokens=usage_info['prompt_tokens'],
                                completion_tokens=usage_info['completion_tokens'],
                                total_tokens=usage_info['total_tokens']
                            )
                        
                        # 원래 LLM 설정 복원 (폴백 사용 후)
                        if provider_idx > 0:
                            self.llm_config = get_agent_llm_config(self.agent_name)
                            self.llm = None  # 다음 get_llm()에서 새로 생성하게 함
                        
                        return result
                else:
                    # 토큰 추적 없이 호출
                    # 필요시 LLM 설정 변경
                    if provider_idx > 0:
                        # 임시 폴백 LLM 설정
                        self.llm_config = provider_config
                        self.llm = None  # 다음 get_llm()에서 새로 생성하게 함
                    
                    # LLM 호출
                    result = self.get_llm().invoke(*args, **kwargs)
                    
                    # 원래 LLM 설정 복원 (폴백 사용 후)
                    if provider_idx > 0:
                        self.llm_config = get_agent_llm_config(self.agent_name)
                        self.llm = None  # 다음 get_llm()에서 새로 생성하게 함
                    
                    return result
                    
            except Exception as e:
                # 에러 로깅
                if provider_idx == 0:
                    logger.warning(f"기본 LLM 호출 실패: {self.agent_name}, provider={self.llm_config.get('provider')}, 오류: {str(e)}")
                else:
                    logger.warning(f"폴백 LLM 호출 실패 ({provider_idx}/{max_retries}): provider={provider_config.get('provider')}, 오류: {str(e)}")
                
                # 마지막 예외 저장 및 설정 복원
                last_exception = e
                
                # 폴백 호출 후 원래 설정 복원
                if provider_idx > 0:
                    self.llm_config = get_agent_llm_config(self.agent_name)
                    self.llm = None
                
        # 모든 시도 실패
        logger.error(f"모든 LLM 호출 시도 실패: {self.agent_name}")
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError(f"모든 LLM 호출 시도가 알 수 없는 이유로 실패했습니다.")
    
    async def ainvoke_with_fallback(self, *args, **kwargs) -> Any:
        """
        폴백 메커니즘을 사용하여 LLM 비동기 호출
        
        주 LLM이 실패하면 폴백 LLM을 차례로 시도합니다.
        
        Args:
            *args: LLM.ainvoke에 전달할 위치 인자
            **kwargs: LLM.ainvoke에 전달할 키워드 인자
            
        Returns:
            LLM 응답
            
        Raises:
            Exception: 모든 폴백이 실패하면 마지막 예외 발생
        """
        # 토큰 사용량 추적을 위한 매개변수 추출
        user_id = kwargs.pop("user_id", None)
        project_type = kwargs.pop("project_type", None)
        db = kwargs.pop("db", None)
        
        # 토큰 추적 설정
        use_token_tracking = user_id is not None and project_type is not None and db is not None
        #use_token_tracking = False
        
        if use_token_tracking:
            from common.services.token_usage_service import track_token_usage
            
            logger.info(f"[토큰 추적][비동기] ainvoke_with_fallback 토큰 추적 활성화: agent:{self.agent_name}, user_id={user_id}, project_type={project_type}")
        
        # 폴백이 비활성화되어 있으면 그냥 호출
        if not self.fallback_settings.get("enabled", False):
            if use_token_tracking:
                # 토큰 추적 컨텍스트 생성
                async with track_token_usage(
                    user_id=user_id,
                    project_type=project_type,
                    token_type="llm",
                    model_name=self.get_model_name(),
                    db_getter=db
                ) as tracker:
                    # 비동기 LLM 호출
                    result = await self.get_llm().ainvoke(*args, **kwargs)
                    
                    # API 응답에서 토큰 사용량 추출 시도
                    usage_info = None
                    if hasattr(result, 'usage_metadata'):
                        usage_info = {
                            "prompt_tokens": result.usage_metadata.get('input_tokens', 0),
                            "completion_tokens": result.usage_metadata.get('output_tokens', 0),
                            "total_tokens": result.usage_metadata.get('total_tokens', 0)
                        }
                    
                    if usage_info:
                        # 추출된 토큰 정보 사용
                        tracker.add_tokens(
                                prompt_tokens=usage_info['prompt_tokens'],
                                completion_tokens=usage_info['completion_tokens'],
                                total_tokens=usage_info['total_tokens']
                            )
                    
                    return result
            else:
                # 추적 없이 호출
                return await self.get_llm().ainvoke(*args, **kwargs)

        # 폴백 활성화 시 재시도 로직
        last_exception = None
        base_providers = [None]  # None은 원래 설정
        fallback_providers = self.fallback_settings.get("providers", [])
        max_retries = self.fallback_settings.get("max_retries", 3)
        providers_to_try = base_providers + fallback_providers[:max_retries-1]
        
        for provider_idx, provider_config in enumerate(providers_to_try):
            try:
                # 재시도 간격
                if provider_idx > 0:
                    await asyncio.sleep(1.0)  # 비동기 대기
                
                # 로깅
                if provider_idx == 0:
                    #logger.info(f"기본 LLM으로 비동기 호출: {self.agent_name}, provider={self.llm_config.get('provider')}, userid={user_id}, project_type={project_type}")
                    pass
                else:
                    logger.info(f"폴백 LLM으로 비동기 호출 시도 ({provider_idx}/{max_retries}): provider={provider_config.get('provider')}")
                
                # 토큰 추적 필요시
                if use_token_tracking:
                    # 현재 설정에 맞는 모델 이름 가져오기
                    model_name = self.get_model_name() if provider_idx == 0 else provider_config.get("model_name")
                    
                    async with track_token_usage(
                        user_id=user_id,
                        project_type=project_type,
                        token_type="llm",
                        model_name=model_name,
                        db_getter=db
                    ) as tracker:
                        # 필요시 LLM 설정 변경
                        if provider_idx > 0:
                            # 임시 폴백 LLM 설정
                            self.llm_config = provider_config
                            self.llm = None  # 다음 get_llm()에서 새로 생성하게 함
                        
                        # 비동기 LLM 호출
                        current_llm = self.get_llm()
                        #logger.info(f"[토큰 추적][비동기] agens: {current_llm.name}")
                        result = await current_llm.ainvoke(*args, **kwargs)
                        
                        result_dict = result.model_dump() if hasattr(result, 'dict') else vars(result)
                        logger.info(f"[토큰 추적][비동기] agent result[{self.agent_name}] keys: {result_dict.keys()}")
                        
                        # API 응답에서 토큰 사용량 추출 시도
                        usage_info = None
                        
                        # 1. 직접 usage_metadata 속성 확인
                        if hasattr(result, 'usage_metadata'):
                            usage_info = {
                                "prompt_tokens": result.usage_metadata.get('input_tokens', 0),
                                "completion_tokens": result.usage_metadata.get('output_tokens', 0),
                                "total_tokens": result.usage_metadata.get('total_tokens', 0)
                            }
                        # 2. _message 속성에서 확인 (구조화된 출력의 경우)
                        elif hasattr(result, '_message') and hasattr(result._message, 'usage_metadata'):
                            logger.info(f"[토큰 추적][비동기] _message 속성에서 usage_metadata 찾음")
                            usage_info = {
                                "prompt_tokens": result._message.usage_metadata.get('input_tokens', 0),
                                "completion_tokens": result._message.usage_metadata.get('output_tokens', 0),
                                "total_tokens": result._message.usage_metadata.get('total_tokens', 0)
                            }
                        # 3. underlying_response 속성에서 확인
                        elif hasattr(result, 'underlying_response') and hasattr(result.underlying_response, 'usage_metadata'):
                            logger.info(f"[토큰 추적][비동기] underlying_response 속성에서 usage_metadata 찾음")
                            usage_info = {
                                "prompt_tokens": result.underlying_response.usage_metadata.get('input_tokens', 0),
                                "completion_tokens": result.underlying_response.usage_metadata.get('output_tokens', 0),
                                "total_tokens": result.underlying_response.usage_metadata.get('total_tokens', 0)
                            }
                        # 4. _raw_response 속성에서 확인
                        elif hasattr(result, '_raw_response') and hasattr(result._raw_response, 'usage_metadata'):
                            logger.info(f"[토큰 추적][비동기] _raw_response 속성에서 usage_metadata 찾음")
                            usage_info = {
                                "prompt_tokens": result._raw_response.usage_metadata.get('input_tokens', 0),
                                "completion_tokens": result._raw_response.usage_metadata.get('output_tokens', 0),
                                "total_tokens": result._raw_response.usage_metadata.get('total_tokens', 0)
                            }
                        # 5. _original_message 속성에서 확인 (구조화된 출력 개선)
                        elif hasattr(result, '_original_message') and hasattr(result._original_message, 'usage_metadata'):
                            logger.info(f"[토큰 추적][비동기] _original_message 속성에서 usage_metadata 찾음")
                            usage_info = {
                                "prompt_tokens": result._original_message.usage_metadata.get('input_tokens', 0),
                                "completion_tokens": result._original_message.usage_metadata.get('output_tokens', 0),
                                "total_tokens": result._original_message.usage_metadata.get('total_tokens', 0)
                            }
                        # 6. 마지막으로 모든 속성을 검사하여 usage_metadata 찾기
                        else:
                            # 디버깅을 위해 모든 속성 로깅
                            all_attrs = dir(result)
                            logger.info(f"[토큰 추적][비동기] result의 모든 속성: {all_attrs}")
                            
                            # 특정 속성들이 있는지 확인하고 로깅
                            for attr_name in all_attrs:
                                if attr_name.startswith('_') and not attr_name.startswith('__'):
                                    attr_value = getattr(result, attr_name, None)
                                    if attr_value is not None:
                                        logger.info(f"[토큰 추적][비동기] 속성 {attr_name}의 타입: {type(attr_value)}")
                                        
                                        # 숨겨진 속성에서 usage_metadata 확인
                                        if hasattr(attr_value, 'usage_metadata'):
                                            logger.info(f"[토큰 추적][비동기] {attr_name}.usage_metadata 찾음!")
                                            usage_info = {
                                                "prompt_tokens": attr_value.usage_metadata.get('input_tokens', 0),
                                                "completion_tokens": attr_value.usage_metadata.get('output_tokens', 0),
                                                "total_tokens": attr_value.usage_metadata.get('total_tokens', 0)
                                            }
                                            break
                        
                        if usage_info:
                            # 추출된 토큰 정보 사용
                            tracker.add_tokens(
                                prompt_tokens=usage_info['prompt_tokens'],
                                completion_tokens=usage_info['completion_tokens'],
                                total_tokens=usage_info['total_tokens']
                            )
                        else:
                            logger.warning("[토큰 추적][비동기] usage_metadata를 찾을 수 없습니다.")
                        
                        # 원래 LLM 설정 복원 (폴백 사용 후)
                        if provider_idx > 0:
                            self.llm_config = get_agent_llm_config(self.agent_name)
                            self.llm = None  # 다음 get_llm()에서 새로 생성하게 함
                        
                        return result
                else:
                    # 토큰 추적 없이 호출
                    # 필요시 LLM 설정 변경
                    if provider_idx > 0:
                        # 임시 폴백 LLM 설정
                        self.llm_config = provider_config
                        self.llm = None  # 다음 get_llm()에서 새로 생성하게 함
                    
                    # 비동기 LLM 호출
                    result = await self.get_llm().ainvoke(*args, **kwargs)
                    
                    # 원래 LLM 설정 복원 (폴백 사용 후)
                    if provider_idx > 0:
                        self.llm_config = get_agent_llm_config(self.agent_name)
                        self.llm = None  # 다음 get_llm()에서 새로 생성하게 함
                    
                    return result
                    
            except Exception as e:
                # 에러 로깅
                if provider_idx == 0:
                    logger.info(f"기본 LLM 비동기 호출 실패: {self.agent_name}, provider={self.llm_config.get('provider')}, 오류: {str(e)}")
                else:
                    logger.info(f"폴백 LLM 비동기 호출 실패 ({provider_idx}/{max_retries}): provider={provider_config.get('provider')}, 오류: {str(e)}")
                
                # 마지막 예외 저장 및 설정 복원
                last_exception = e
                
                # 폴백 호출 후 원래 설정 복원
                if provider_idx > 0:
                    self.llm_config = get_agent_llm_config(self.agent_name)
                    self.llm = None
                
        # 모든 시도 실패
        logger.error(f"모든 LLM 비동기 호출 시도 실패: {self.agent_name}")
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError(f"모든 비동기 LLM 호출 시도가 알 수 없는 이유로 실패했습니다.")
    
    def get_config(self) -> Dict[str, Any]:
        """
        현재 LLM 설정 반환
        
        Returns:
            LLM 설정
        """
        return self.llm_config
    
    def update_config(self, new_config: Dict[str, Any]) -> None:
        """
        LLM 설정 업데이트
        
        Args:
            new_config: 새 설정
        """
        from common.services.llm_config.llm_config_manager import llm_config_manager
        
        # 설정 업데이트
        llm_config_manager.update_agent_config(self.agent_name, new_config)
        
        # 설정 새로고침
        self.llm_config = get_agent_llm_config(self.agent_name)
        
        # LLM 재생성
        self.llm = None
        self.llm_streaming = None
        
        logger.info(f"LLM 설정 업데이트: {self.agent_name}")

    def validate_config(self) -> bool:
        """
        현재 설정의 유효성을 검사
        
        Returns:
            설정이 유효하면 True, 그렇지 않으면 False
        """
        # 필수 필드 확인
        required_fields = ["provider", "model_name"]
        return all(field in self.llm_config for field in required_fields)
        
    def with_structured_output(self, schema, **kwargs):
        """
        구조화된 출력을 반환하는 LLM 생성
        
        Args:
            schema: 출력 스키마 (Pydantic 모델 또는 타입힌트)
            **kwargs: with_structured_output에 전달할 추가 인자
            
        Returns:
            구조화된 출력을 지원하는 AgentLLM 래퍼
        """
        from langchain_core.runnables import RunnableSerializable
        
        class StructuredOutputAgentLLM:
            def __init__(self, agent_llm: 'AgentLLM', schema, **kwargs):
                self.agent_llm = agent_llm
                self.schema = schema
                self.kwargs = kwargs
            
            async def ainvoke(self, *args, **kwargs):
                llm = self.agent_llm.get_llm()
                
                # 토큰 사용량 추적을 위한 매개변수 분리
                user_id = kwargs.pop("user_id", None)
                project_type = kwargs.pop("project_type", None)
                db = kwargs.pop("db", None)
                
                # 1단계: 일반 LLM으로 호출하여 AIMessage 응답 받기
                # LLM에게 schema에 맞는 JSON 반환하도록 요청
                from langchain_core.messages import HumanMessage
                
                # 입력이 리스트가 아니면 (즉, 그냥 문자열이나 다른 형식이면) 메시지로 변환
                if args and not isinstance(args[0], list):
                    # LLM에게 JSON 형식으로 응답하도록 요청하는 프리픽스 추가
                    schema_str = self.schema.model_json_schema() if hasattr(self.schema, 'model_json_schema') else str(self.schema)
                    json_instruction = f"\n반드시 다음 JSON 스키마에 맞는 형식으로 응답하고, 요청하지 않은 데이터값은 응답하지 마시오. {schema_str}\n\n중요: 절대로 Markdown 코드 블록(```)을 사용하지 마세요. 코드 블록 표시 없이 순수한 JSON 형식으로만 응답해주세요. 응답의 시작과 끝에 ```json이나 ``` 기호를 포함하지 마세요.\n\n"
                    
                    if isinstance(args[0], str):
                        args = ([HumanMessage(content=args[0]+ json_instruction )],) + args[1:]
                
                
                raw_response = await self.agent_llm.ainvoke_with_fallback(
                    *args,
                    user_id=user_id,
                    project_type=project_type,
                    db=db,
                    **kwargs
                )
                # 2단계: 응답 내용을 수동으로 Pydantic 모델로 파싱
                try:
                    content = raw_response.content if hasattr(raw_response, 'content') else str(raw_response)
                    
                    # Markdown 코드 블록 제거 - 다양한 패턴 처리
                    import re
                    # 전체 문자열이 코드 블록으로 감싸진 경우
                    content = re.sub(r'^```(?:json)?\s*\n?(.*?)\n?```\s*$', r'\1', content, flags=re.DOTALL)
                    # 시작 부분에 ```json이 있는 경우
                    content = re.sub(r'^```(?:json)?\s*\n?', '', content, flags=re.DOTALL)
                    # 끝 부분에 ``` 가 있는 경우
                    content = re.sub(r'\n?```\s*$', '', content, flags=re.DOTALL)
                    # 문자열 앞뒤 공백 제거
                    content = content.strip()
                    
                    #logger.info(f"[구조화된 출력] 파싱 시도: {type(self.schema)}")
                    
                    # Pydantic 모델로 파싱
                    if hasattr(self.schema, 'model_validate_json'):
                        parsed_response = self.schema.model_validate_json(content)
                    elif hasattr(self.schema, 'parse_raw'):  # Pydantic v1 지원
                        parsed_response = self.schema.parse_raw(content)
                    else:
                        # JSON으로 파싱한 후 객체 생성
                        import json
                        data = json.loads(content)
                        parsed_response = self.schema(**data)
                    
                    # 원본 메타데이터 보존을 위해 Pydantic 모델에 _original_message 속성 추가
                    setattr(parsed_response, '_original_message', raw_response)
                    
                    logger.info(f"[구조화된 출력] 파싱 성공: {type(parsed_response)}")
                    return parsed_response
                    
                except Exception as e:
                    logger.error(f"[구조화된 출력] 파싱 오류: {str(e)}")
                    # 파싱 실패 시 원본 응답 반환
                    return raw_response
            
            def invoke(self, *args, **kwargs):
                llm = self.agent_llm.get_llm()
                
                # 토큰 사용량 추적을 위한 매개변수 분리
                user_id = kwargs.pop("user_id", None)
                project_type = kwargs.pop("project_type", None)
                db = kwargs.pop("db", None)
                
                # 1단계: 일반 LLM으로 호출하여 응답 받기
                # LLM에게 schema에 맞는 JSON 반환하도록 요청
                from langchain_core.messages import HumanMessage
                
                # 입력이 리스트가 아니면 (즉, 그냥 문자열이나 다른 형식이면) 메시지로 변환
                if args and not isinstance(args[0], list):
                    # LLM에게 JSON 형식으로 응답하도록 요청하는 프리픽스 추가
                    schema_str = self.schema.model_json_schema() if hasattr(self.schema, 'model_json_schema') else str(self.schema)
                    json_instruction = f"반드시 다음 JSON 스키마에 맞는 형식으로 응답하고, 요청하지 않은 데이터값은 응답하지 마시오.\n{schema_str}\n\n중요: 절대로 Markdown 코드 블록(```)을 사용하지 마세요. 코드 블록 표시 없이 순수한 JSON 형식으로만 응답해주세요. 응답의 시작과 끝에 ```json이나 ``` 기호를 포함하지 마세요.\n\n"
                    
                    if isinstance(args[0], str):
                        args = ([HumanMessage(content=json_instruction + args[0])],) + args[1:]
                
                logger.info(f"[구조화된 출력][invoke] 원본 응답 획득을 위한 LLM 호출")

                raw_response = self.agent_llm.invoke_with_fallback(
                    *args,
                    user_id=user_id,
                    project_type=project_type,
                    db=db,
                    **kwargs
                )

                
                
                # 2단계: 응답 내용을 수동으로 Pydantic 모델로 파싱
                try:
                    content = raw_response.content if hasattr(raw_response, 'content') else str(raw_response)
                    
                    # Markdown 코드 블록 제거 - 다양한 패턴 처리
                    import re
                    # 전체 문자열이 코드 블록으로 감싸진 경우
                    content = re.sub(r'^```(?:json)?\s*\n?(.*?)\n?```\s*$', r'\1', content, flags=re.DOTALL)
                    # 시작 부분에 ```json이 있는 경우
                    content = re.sub(r'^```(?:json)?\s*\n?', '', content, flags=re.DOTALL)
                    # 끝 부분에 ``` 가 있는 경우
                    content = re.sub(r'\n?```\s*$', '', content, flags=re.DOTALL)
                    # 문자열 앞뒤 공백 제거
                    content = content.strip()
                    
                    #logger.info(f"[구조화된 출력] 파싱 시도: {type(self.schema)}")
                    
                    # Pydantic 모델로 파싱
                    if hasattr(self.schema, 'model_validate_json'):
                        parsed_response = self.schema.model_validate_json(content)
                    elif hasattr(self.schema, 'parse_raw'):  # Pydantic v1 지원
                        parsed_response = self.schema.parse_raw(content)
                    else:
                        # JSON으로 파싱한 후 객체 생성
                        import json
                        data = json.loads(content)
                        parsed_response = self.schema(**data)
                    
                    # 원본 메타데이터 보존을 위해 Pydantic 모델에 _original_message 속성 추가
                    setattr(parsed_response, '_original_message', raw_response)
                    
                    logger.info(f"[구조화된 출력] 파싱 성공: {type(parsed_response)}")
                    return parsed_response
                    
                except Exception as e:
                    logger.error(f"[구조화된 출력] 파싱 오류: {str(e)}")
                    # 파싱 실패 시 원본 응답 반환
                    return raw_response
        
        return StructuredOutputAgentLLM(self, schema, **kwargs)

    async def stream(self, input, **kwargs) -> AsyncGenerator[Any, None]:
        """
        LLM을 스트리밍 모드로 호출하고 생성된 토큰을 AsyncGenerator로 반환합니다.
        
        Args:
            input: LLM에 전달할 입력
            **kwargs: LLM에 전달할 추가 키워드 인자
                - user_id: 사용자 ID (선택적, 토큰 사용량 추적용)
                - project_type: 프로젝트 타입 (선택적, 토큰 사용량 추적용)
            
        Returns:
            토큰 청크를 반환하는 AsyncGenerator
        """
        try:
            # 토큰 사용량 추적 관련 매개변수 추출
            user_id = kwargs.pop("user_id", None)
            project_type = kwargs.pop("project_type", None)
            db = kwargs.pop("db", None)
            
            # 토큰 추적 설정
            use_token_tracking = user_id is not None and project_type is not None and db is not None
            if use_token_tracking:
                from common.services.token_usage_service import track_token_usage
                logger.info(f"[스트리밍][토큰 추적] 토큰 추적 활성화: agent={self.agent_name}, user_id={user_id}, project_type={project_type}")
            
            # LLM 가져오기
            llm = self.get_llm()
            
            # astream 메서드가 있는지 확인
            if not hasattr(llm, 'astream'):
                logger.warning(f"LLM {self.get_provider()}/{self.get_model_name()}이 스트리밍을 지원하지 않습니다. ainvoke로 대체합니다.")
                # 스트리밍을 지원하지 않는 경우 ainvoke 호출 후 전체 응답을 한 번에 반환
                result = await self.ainvoke_with_fallback(input, user_id=user_id, project_type=project_type, db=db, **kwargs)
                yield result
                return
            
            # 스트리밍 호출
            logger.info(f"스트리밍 시작: {self.agent_name}, provider={self.get_provider()}, model={self.get_model_name()}")
            
            # 토큰 사용량 누적 변수
            total_prompt_tokens = 0
            total_completion_tokens = 0
            total_tokens = 0
            token_metadata_found = False
            
            # 스트리밍 호출
            if use_token_tracking:
                async with track_token_usage(
                    user_id=user_id,
                    project_type=project_type,
                    token_type="llm",
                    model_name=self.get_model_name(),
                    db_getter=db
                ) as tracker:
                    async for chunk in llm.astream(input, **kwargs):
                        # 토큰 사용량 메타데이터 확인 및 누적
                        if hasattr(chunk, 'usage_metadata'):
                            token_metadata_found = True
                            metadata = chunk.usage_metadata
                            # 메타데이터가 있는 경우만 누적
                            if metadata:
                                input_tokens = metadata.get('input_tokens', 0)
                                output_tokens = metadata.get('output_tokens', 0)
                                tokens = metadata.get('total_tokens', 0)
                                
                                # 기존보다 큰 값만 업데이트 (일부 청크에서만 메타데이터 제공)
                                if input_tokens > total_prompt_tokens:
                                    total_prompt_tokens = input_tokens
                                if output_tokens > total_completion_tokens:
                                    total_completion_tokens = output_tokens
                                if tokens > total_tokens:
                                    total_tokens = tokens
                                
                                logger.debug(f"[스트리밍][토큰 추적] 청크 메타데이터: input={input_tokens}, output={output_tokens}, total={tokens}")
                        
                        yield chunk
                    
                    # 스트리밍 완료 후 토큰 사용량 저장
                    if token_metadata_found:
                        logger.info(f"[스트리밍][토큰 추적] 최종 토큰 사용량: input={total_prompt_tokens}, output={total_completion_tokens}, total={total_tokens}")
                        tracker.add_tokens(
                            prompt_tokens=total_prompt_tokens,
                            completion_tokens=total_completion_tokens,
                            total_tokens=total_tokens
                        )
                    else:
                        logger.warning(f"[스트리밍][토큰 추적] 메타데이터를 찾을 수 없습니다.")
            else:
                # 토큰 추적 없이 스트리밍
                async for chunk in llm.astream(input, **kwargs):
                    yield chunk
            
            logger.info(f"스트리밍 종료: {self.agent_name}")
            
        except Exception as e:
            logger.error(f"스트리밍 중 오류 발생: {self.agent_name}, 오류: {str(e)}", exc_info=True)
            # 오류가 발생해도 오류 메시지 반환
            yield f"스트리밍 오류: {str(e)}"
            # 예외를 다시 발생시켜서 호출자가 처리할 수 있게 함
            raise

# 에이전트별 LLM 캐시
agent_llm_cache: Dict[str, AgentLLM] = {}
# 마지막 캐시 검사 시간 (성능 최적화용)
_last_cache_check_time = 0
# 캐시 검사 간격 (초) - 너무 자주 체크하면 성능에 영향을 줄 수 있음
_CACHE_CHECK_INTERVAL = 60  # 5초마다 설정 파일 변경 여부 확인

def refresh_agent_llm_cache(force: bool = False) -> None:
    """
    에이전트 LLM 캐시를 새로고침합니다.
    이 함수는 설정 파일이 변경된 경우에만 캐시를 갱신합니다.
    
    Args:
        force: 강제 새로고침 여부
    """
    global _last_cache_check_time
    
    current_time = time.time()
    
    # 마지막 체크 이후 일정 시간이 지났거나 강제 새로고침인 경우에만 체크
    if force or (current_time - _last_cache_check_time) > _CACHE_CHECK_INTERVAL:
        # 설정 파일 변경 확인
        config_modified_time = llm_config_manager._get_file_modified_time()
        manager_last_modified = llm_config_manager._last_modified_time
        
        # 설정 파일이 변경되었거나 강제 새로고침인 경우에만 캐시 갱신
        if force or config_modified_time > manager_last_modified:
            logger.info(f"LLM 설정 파일 변경 감지: 마지막={manager_last_modified}, 현재={config_modified_time}")
            
            # 설정 관리자 새로고침
            llm_config_manager.refresh()
            
            # 캐시된 모든 에이전트 LLM 초기화
            for agent_name, agent_llm in agent_llm_cache.items():
                # LLM 객체와 설정 초기화
                agent_llm.llm_config = get_agent_llm_config(agent_name)
                agent_llm.llm = None
                agent_llm.llm_streaming = None
                logger.info(f"에이전트 LLM 캐시 초기화: {agent_name}")
        
        # 마지막 체크 시간 업데이트
        _last_cache_check_time = current_time

def get_agent_llm(agent_name: str, refresh: bool = False) -> AgentLLM:
    """
    에이전트별 LLM 인스턴스 반환
    
    Args:
        agent_name: 에이전트 이름
        refresh: 설정 새로고침 여부
        
    Returns:
        AgentLLM 인스턴스
    """
    # 필요시 캐시 새로고침
    refresh_agent_llm_cache(force=refresh)
    
    # 캐시에 없으면 새로 생성
    if agent_name not in agent_llm_cache:
        agent_llm_cache[agent_name] = AgentLLM(agent_name)
    elif refresh:
        # 강제 새로고침인 경우 설정과 LLM 초기화
        agent_llm_cache[agent_name].llm_config = get_agent_llm_config(agent_name)
        agent_llm_cache[agent_name].llm = None
        agent_llm_cache[agent_name].llm_streaming = None
    
    return agent_llm_cache[agent_name]

# 편의 함수
def get_llm_for_agent(agent_name: str, refresh: bool = False) -> Union[BaseChatModel, Tuple[BaseChatModel, str, str]]:
    """
    에이전트별 LLM 인스턴스와 모델 정보 반환 (편의 함수)
    
    Args:
        agent_name: 에이전트 이름
        refresh: 설정 새로고침 여부
        
    Returns:
        LLM 인스턴스, 모델 이름, 제공자 이름의 튜플
    """
    agent_llm = get_agent_llm(agent_name, refresh=refresh)
    return agent_llm.get_llm(), agent_llm.get_model_name(), agent_llm.get_provider() 