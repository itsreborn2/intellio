"""
LLM 팩토리 모듈

이 모듈은 설정에 따라 다양한 LLM 제공자(OpenAI, Gemini, Anthropic 등)의 
LLM 인스턴스를 생성하는 기능을 제공합니다.
"""

import os
from typing import Dict, Any, Optional, List, Union, Callable
from pydantic import BaseModel
from loguru import logger

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.callbacks import BaseCallbackHandler

from common.core.config import settings

class LLMFactory:
    """LLM 객체를 생성하는 팩토리 클래스"""
    
    @staticmethod
    def create_llm(
        provider: str,
        model_name: str,
        temperature: float = 0,
        max_tokens: int = 2048,
        top_p: float = 0.7,
        streaming: bool = False,
        callback_handler: Optional[BaseCallbackHandler] = None,
        api_key_env: Optional[str] = None,
        thinking_budget: Optional[int] = None,
        **kwargs
    ) -> BaseChatModel:
        """
        LLM 인스턴스 생성
        
        Args:
            provider: LLM 제공자 (openai, gemini, anthropic 등)
            model_name: 모델 이름
            temperature: 생성 다양성 조절 (0.0 ~ 1.0)
            max_tokens: 최대 생성 토큰 수
            top_p: 토큰 확률 임계값 (0.0 ~ 1.0)
            streaming: 스트리밍 활성화 여부
            callback_handler: 스트리밍 콜백 핸들러
            api_key_env: API 키 환경 변수 이름
            thinking_budget: Gemini 2.5+ 모델의 thinking budget (선택적)
            **kwargs: 추가 설정
            
        Returns:
            LLM 인스턴스
            
        Raises:
            ValueError: 지원하지 않는 LLM 제공자인 경우
        """
        provider = provider.lower()
        
        # API 키 가져오기
        api_key = None
        
        # 1. 환경 변수에서 API 키 가져오기 (api_key_env 지정된 경우)
        if api_key_env:
            api_key = os.getenv(api_key_env)
            #logger.info(f"환경변수 {api_key_env}에서 API 키 가져오기 시도")
        
        # 콜백 설정
        callbacks = None
        if callback_handler:
            callbacks = [callback_handler]
        
        # OpenAI 모델 생성
        if provider == "openai":
            # 2. 기본 환경 변수 이름에서 가져오기
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            #logger.info(f"환경변수 {api_key_env}에서 API 키 가져오기 시도")

            # 3. settings 객체에서 가져오기
            if not api_key and hasattr(settings, "OPENAI_API_KEY"):
                api_key = settings.OPENAI_API_KEY
                #logger.info(f"설정에서 OPENAI_API_KEY 가져오기 시도")

            if not api_key:
                raise ValueError("OpenAI API 키가 설정되지 않았습니다.")
                
            return ChatOpenAI(
                model=model_name,
                openai_api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                streaming=streaming,
                callbacks=callbacks,
                **kwargs
            )
            
        # Google Gemini 모델 생성
        elif provider == "gemini":
            # 2. 기본 환경 변수 이름에서 가져오기
            api_key = api_key or os.getenv("GEMINI_API_KEY")
            
            # 3. settings 객체에서 가져오기
            if not api_key and hasattr(settings, "GEMINI_API_KEY"):
                api_key = settings.GEMINI_API_KEY
                
            if not api_key:
                raise ValueError("Google API 키가 설정되지 않았습니다.")
            
            # Gemini LLM 생성 파라미터 설정
            gemini_params = {
                "model": model_name,
                "google_api_key": api_key,
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "top_p": top_p,
                "callbacks": callbacks,
                "model_kwargs": {"streaming": streaming},  # streaming은 model_kwargs로 이동
                **kwargs
            }
            
            # thinking_budget이 설정된 경우에만 추가 (Gemini 2.5+ 모델 지원)
            if thinking_budget is not None:
                gemini_params["thinking_budget"] = thinking_budget
                logger.info(f"Gemini LLM에 thinking_budget 설정: {thinking_budget}")
                
            return ChatGoogleGenerativeAI(**gemini_params)
            
        # Anthropic Claude 모델 생성
        elif provider == "anthropic":
            # 2. 기본 환경 변수 이름에서 가져오기
            api_key = api_key or os.getenv("CLAUDE_API_KEY")
            
            # 3. settings 객체에서 가져오기
            if not api_key and hasattr(settings, "CLAUDE_API_KEY"):
                api_key = settings.ANTHROPIC_API_KEY
                
            if not api_key:
                raise ValueError("Anthropic API 키가 설정되지 않았습니다.")
                
            return ChatAnthropic(
                model=model_name,
                anthropic_api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                streaming=streaming,
                callbacks=callbacks,
                **kwargs
            )
            
        # Google VertexAI 모델 생성
        elif provider == "vertexai":
            # 설정에서 VertexAI 관련 값들 가져오기
            project_id = kwargs.get("project_id", None)
            location = kwargs.get("location", None)
            
            if not project_id and hasattr(settings, "GOOGLE_PROJECT_ID_VERTEXAI"):
                project_id = settings.GOOGLE_PROJECT_ID_VERTEXAI
                
            if not location and hasattr(settings, "GOOGLE_LOCATION_VERTEXAI"):
                location = settings.GOOGLE_LOCATION_VERTEXAI
                
            if not project_id or not location:
                raise ValueError("Google VertexAI 설정이 완전하지 않습니다.")
                
            from langchain_google_vertexai import ChatVertexAI
            
            return ChatVertexAI(
                model=model_name,
                project=project_id,
                location=location,
                temperature=temperature,
                max_output_tokens=max_tokens,
                top_p=top_p,
                streaming=streaming,
                callbacks=callbacks,
                **kwargs
            )
            
        # Upstage 모델 생성
        elif provider == "upstage":
            # 2. 기본 환경 변수 이름에서 가져오기
            api_key = api_key or os.getenv("UPSTAGE_API_KEY")
            
            # 3. settings 객체에서 가져오기
            if not api_key and hasattr(settings, "UPSTAGE_API_KEY"):
                api_key = settings.UPSTAGE_API_KEY
                
            if not api_key:
                raise ValueError("Upstage API 키가 설정되지 않았습니다.")
            
            return ChatOpenAI(
                base_url="https://api.upstage.ai/v1/solar",
                model=model_name, # "solar-pro"
                openai_api_key=api_key,
                temperature=temperature,
                top_p=top_p,
                streaming=streaming,
                callbacks=callbacks,
                **kwargs
            )
            
            # Upstage는 현재 공식 langchain 통합이 없음
            # 필요시 CustomLLM 클래스로 구현 필요
            #raise NotImplementedError("Upstage 모델은 아직 지원되지 않습니다.")
            
        # 지원하지 않는 LLM 제공자인 경우
        else:
            raise ValueError(f"지원하지 않는 LLM 제공자입니다: {provider}")
    
    @staticmethod
    def create_llm_from_config(
        config: Dict[str, Any],
        streaming: bool = False,
        callback_handler: Optional[BaseCallbackHandler] = None
    ) -> BaseChatModel:
        """
        설정에서 LLM 생성
        
        Args:
            config: LLM 설정
            streaming: 스트리밍 활성화 여부
            callback_handler: 스트리밍 콜백 핸들러
            
        Returns:
            LLM 인스턴스
        """
        return LLMFactory.create_llm(
            provider=config.get("provider", "openai"),
            model_name=config.get("model_name", "gpt-4o-mini"),
            temperature=config.get("temperature", 0),
            max_tokens=config.get("max_tokens", 2048),
            top_p=config.get("top_p", 0.7),
            streaming=streaming,
            callback_handler=callback_handler,
            api_key_env=config.get("api_key_env", None),
            thinking_budget=config.get("thinking_budget", None)
        )

# 편의 함수
def create_llm_from_config(
    config: Dict[str, Any],
    streaming: bool = False,
    callback_handler: Optional[BaseCallbackHandler] = None
) -> BaseChatModel:
    """
    설정에서 LLM 생성 (편의 함수)
    
    Args:
        config: LLM 설정
        streaming: 스트리밍 활성화 여부
        callback_handler: 스트리밍 콜백 핸들러
        
    Returns:
        LLM 인스턴스
    """
    return LLMFactory.create_llm_from_config(config, streaming, callback_handler) 