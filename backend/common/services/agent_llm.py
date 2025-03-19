"""
에이전트별 LLM 관리 모듈

이 모듈은 에이전트별 LLM 관리를 위한 기능을 제공합니다.
에이전트 이름을 기반으로 적절한 LLM 설정을 로드하고 LLM 인스턴스를 생성합니다.
"""

import time
from typing import Dict, Any, Optional, Callable, List, Tuple, Union
from loguru import logger
from functools import lru_cache

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
        
        logger.info(f"AgentLLM 초기화: {agent_name}, provider={self.llm_config.get('provider')}, model={self.llm_config.get('model_name')}")
        
        # 폴백 설정 로그
        if self.fallback_settings.get("enabled", False):
            logger.debug(f"폴백 활성화됨: 최대 재시도 횟수={self.fallback_settings.get('max_retries', 3)}, 폴백 제공자 수={len(self.fallback_settings.get('providers', []))}")
    
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
        폴백 메커니즘을 사용하여 LLM 호출
        
        주 LLM이 실패하면 폴백 LLM을 차례로 시도합니다.
        
        Args:
            *args: LLM.invoke에 전달할 위치 인자
            **kwargs: LLM.invoke에 전달할 키워드 인자
            
        Returns:
            LLM 응답
            
        Raises:
            Exception: 모든 폴백이 실패하면 마지막 예외 발생
        """
        # 폴백이 비활성화되어 있으면 그냥 호출
        if not self.fallback_settings.get("enabled", False):
            return self.get_llm().invoke(*args, **kwargs)
        
        # 원래 LLM으로 먼저 시도
        try:
            return self.get_llm().invoke(*args, **kwargs)
        except Exception as e:
            # 원래 LLM 실패 로그
            logger.warning(f"기본 LLM 호출 실패: {self.agent_name}, provider={self.llm_config.get('provider')}, 오류: {str(e)}")
            logger.info(f"폴백 호출 시도 중: {self.agent_name}")
            
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
                    
                    logger.info(f"폴백 호출 시도 {retry+1}/{max_retries}: {self.agent_name}, provider={fallback_config.get('provider')}, model={fallback_config.get('model_name')}")
                    
                    # 폴백 LLM 생성
                    fallback_llm = LLMFactory.create_llm_from_config(fallback_config)
                    
                    # 폴백 LLM으로 호출
                    return fallback_llm.invoke(*args, **kwargs)
                except Exception as e:
                    # 폴백 실패 로그
                    logger.warning(f"폴백 LLM 호출 실패 ({retry+1}/{max_retries}): provider={fallback_config.get('provider')}, 오류: {str(e)}")
                    last_exception = e
            
            # 모든 폴백 실패
            logger.error(f"모든 폴백 호출 시도 실패: {self.agent_name}")
            raise last_exception
    
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
        # 폴백이 비활성화되어 있으면 그냥 호출
        if not self.fallback_settings.get("enabled", False):
            return await self.get_llm().ainvoke(*args, **kwargs)
        
        # 원래 LLM으로 먼저 시도
        try:
            return await self.get_llm().ainvoke(*args, **kwargs)
        except Exception as e:
            # 원래 LLM 실패 로그
            logger.warning(f"기본 LLM 비동기 호출 실패: {self.agent_name}, provider={self.llm_config.get('provider')}, 오류: {str(e)}")
            logger.info(f"폴백 비동기 호출 시도 중: {self.agent_name}")
            
            # 마지막 예외 기록
            last_exception = e
            
            # 폴백 제공자 시도
            fallback_providers = self.fallback_settings.get("providers", [])
            max_retries = self.fallback_settings.get("max_retries", 3)
            
            for retry in range(min(max_retries, len(fallback_providers))):
                try:
                    # 재시도 간격
                    if retry > 0:
                        import asyncio
                        await asyncio.sleep(1.0)  # 1초 대기
                    
                    # 폴백 제공자 설정
                    fallback_config = fallback_providers[retry]
                    
                    logger.info(f"폴백 비동기 호출 시도 {retry+1}/{max_retries}: {self.agent_name}, provider={fallback_config.get('provider')}, model={fallback_config.get('model_name')}")
                    
                    # 폴백 LLM 생성
                    fallback_llm = LLMFactory.create_llm_from_config(fallback_config)
                    
                    # 폴백 LLM으로 호출
                    return await fallback_llm.ainvoke(*args, **kwargs)
                except Exception as e:
                    # 폴백 실패 로그
                    logger.warning(f"폴백 LLM 비동기 호출 실패 ({retry+1}/{max_retries}): provider={fallback_config.get('provider')}, 오류: {str(e)}")
                    last_exception = e
            
            # 모든 폴백 실패
            logger.error(f"모든 폴백 비동기 호출 시도 실패: {self.agent_name}")
            raise last_exception
    
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
        현재 설정이 유효한지 확인
        
        Returns:
            설정 유효성 여부
        """
        try:
            # LLM 생성해보기
            llm = LLMFactory.create_llm_from_config(self.llm_config)
            return True
        except Exception as e:
            logger.error(f"LLM 설정 검증 실패: {self.agent_name}, 오류: {str(e)}")
            return False

# 에이전트별 LLM 캐시
agent_llm_cache: Dict[str, AgentLLM] = {}

def get_agent_llm(agent_name: str) -> AgentLLM:
    """
    에이전트별 LLM 인스턴스 반환
    
    Args:
        agent_name: 에이전트 이름
        
    Returns:
        AgentLLM 인스턴스
    """
    # 캐시에 없으면 새로 생성
    if agent_name not in agent_llm_cache:
        agent_llm_cache[agent_name] = AgentLLM(agent_name)
    
    return agent_llm_cache[agent_name]

# 편의 함수
def get_llm_for_agent(agent_name: str) -> Union[BaseChatModel, Tuple[BaseChatModel, str, str]]:
    """
    에이전트별 LLM 인스턴스와 모델 정보 반환 (편의 함수)
    
    Args:
        agent_name: 에이전트 이름
        
    Returns:
        LLM 인스턴스, 모델 이름, 제공자 이름의 튜플
    """
    agent_llm = get_agent_llm(agent_name)
    return agent_llm.get_llm(), agent_llm.get_model_name(), agent_llm.get_provider() 