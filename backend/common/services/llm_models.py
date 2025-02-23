import asyncio
from typing import Any, List, Optional, Union, Callable, Dict, Iterator, AsyncIterator

from langchain_core.messages import BaseMessage, AIMessage, ChatMessage, AIMessageChunk
from langchain_core.messages.base import BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult, ChatGenerationChunk
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.callbacks.manager import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
from langchain_core.callbacks import BaseCallbackHandler

from langchain_openai import ChatOpenAI
from langchain_google_vertexai import ChatVertexAI

import torch
from transformers import AutoModel, AutoTokenizer
from google.oauth2 import service_account
import json
#from loguru import logger
from common.core.config import settings
import logging

logger = logging.getLogger(__name__)
class StreamingCallbackHandler(BaseCallbackHandler):
    """스트리밍 응답을 처리하는 콜백 핸들러"""
    
    def __init__(self, on_new_token: Callable[[str], None]):
        self.on_new_token = on_new_token
        logger.info(f"StreamingCallbackHandler 초기화 - 콜백 함수: {on_new_token}")

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """새로운 토큰이 생성될 때마다 호출되는 메서드"""
        logger.debug(f"New token received: {token}")
        if self.on_new_token:
            self.on_new_token(token)

class LLMModels:
    """AI Model을 랭체인에 맞게 구현"""
    _instance = None  # 클래스 변수로 이동
    
    def __new__(cls, streaming_callback: Optional[Callable[[str], None]] = None, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # __init__에서 초기화하도록 변경
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, streaming_callback: Optional[Callable[[str], None]] = None, **kwargs):
        if not self._initialized:  # 한 번만 초기화되도록
            self._llm_chain = None
            self._llm_type = "gemini"
            self._llm = None
            self._llm_streaming = None
            self._current_model_idx = 0
            self._streaming_callback = streaming_callback
            self._should_stop = False
            self._current_task: Optional[asyncio.Task] = None
            self._stream_lock = asyncio.Lock()
            
            # 초기화 실행
            self.initialize([
                {"model":"gemini", "api_key":settings.GEMINI_API_KEY },
                {"model":"openai", "api_key":settings.OPENAI_API_KEY },
            ], **kwargs)
            
            self._initialized = True


    def initialize(self, llm_list:list, **kwargs):
        """LangChain 초기화"""
        if self._llm_chain is None:
            self._llm_list = llm_list

            # 첫 번째 모델로 초기화
            model_info = llm_list[self._current_model_idx]
            self._llm = self.get_llm(model_info["model"], model_info["api_key"], **kwargs)
            self._llm_type = model_info["model"]
            self._llm.model
            # streaming callback이 있는 경우 StreamingCallbackHandler 생성
            callback_handler = None
            if self._streaming_callback:
                callback_handler = StreamingCallbackHandler(self._streaming_callback)
            
                self._llm_streaming = self.get_llm(
                    model_info["model"], 
                    model_info["api_key"], 
                    streaming=True, 
                    callback_handler=callback_handler,
                    **kwargs
                )
                logger.warn(f"LLMModels : {model_info['model']} Streaming")
            logger.warn(f"LLMModels : {model_info['model']} API 초기화")
    def set_streaming_callback(self, streaming_callback: Optional[Callable[[str], None]] = None):
        """스트리밍 콜백 설정"""
        self._streaming_callback = streaming_callback
        model_info = self._llm_list[self._current_model_idx]
        callback_handler = StreamingCallbackHandler(self._streaming_callback)

        self._llm_streaming = self.get_llm(
            model_info["model"], 
            model_info["api_key"], 
            streaming=True, 
            callback_handler=callback_handler,
        )
        logger.warn(f"LLMModels : {model_info['model']} Streaming")


    def get_llm(self, model_name: str, 
                    api_key: str | None, 
                    streaming: bool = False, 
                    callback_handler: Optional[BaseCallbackHandler] = None,
                    **kwargs) -> BaseChatModel:
        if model_name == "openai":
            callbacks = [callback_handler] if callback_handler else None
            return ChatOpenAI(
                        model="gpt-4-0125-preview",
                        openai_api_key=api_key,
                        temperature=kwargs.get("temperature", 0.2),
                        max_tokens=kwargs.get("max_output_tokens", 2048),
                        top_p=kwargs.get("top_p", 0.7),
                        streaming=streaming,
                        callbacks=callbacks,
                    )
        elif model_name == "gemini":
            # 모델 이름: models/gemini-2.0-flash-exp
            # 표시 이름: Gemini 2.0 Flash Experimental
            # ---
            # 모델 이름: models/gemini-2.0-flash
            # 표시 이름: Gemini 2.0 Flash
            # ---
            # 모델 이름: models/gemini-2.0-flash-001
            # 표시 이름: Gemini 2.0 Flash 001
            # ---
            # 모델 이름: models/gemini-2.0-flash-lite-preview
            # 표시 이름: Gemini 2.0 Flash-Lite Preview
            # ---
            # 모델 이름: models/gemini-2.0-flash-lite-preview-02-05
            # 표시 이름: Gemini 2.0 Flash-Lite Preview 02-05
            # ---
            # 모델 이름: models/gemini-2.0-pro-exp
            # 표시 이름: Gemini 2.0 Pro Experimental
            # ---
            # 모델 이름: models/gemini-2.0-pro-exp-02-05
            # 표시 이름: Gemini 2.0 Pro Experimental 02-05
            # ---
            # 모델 이름: models/gemini-exp-1206
            # 표시 이름: Gemini Experimental 1206
            # ---
            # 모델 이름: models/gemini-2.0-flash-thinking-exp-01-21
            # 표시 이름: Gemini 2.0 Flash Thinking Experimental 01-21
            # ---
            # 모델 이름: models/gemini-2.0-flash-thinking-exp
            # 표시 이름: Gemini 2.0 Flash Thinking Experimental 01-21
            # ---
            # 모델 이름: models/gemini-2.0-flash-thinking-exp-1219
            # 표시 이름: Gemini 2.0 Flash Thinking Experimental            
            callbacks = [callback_handler] if callback_handler else None
            return ChatGoogleGenerativeAI(
                        #model="models/gemini-2.0-flash-001",
                        model="models/gemini-2.0-pro-exp-02-05",
                        #model="models/gemini-2.0-pro-exp-02-05", # 추론모델 시간 오래걸림.
                        google_api_key=api_key,
                        temperature=kwargs.get("temperature", 0.2),
                        max_output_tokens=kwargs.get("max_output_tokens", 2048),
                        top_p=kwargs.get("top_p", 0.7),
                        top_k=kwargs.get("top_k", 20),
                        streaming=streaming,
                        callbacks=callbacks,
                    )
        elif model_name == "gemini_vertex":
            callbacks = [callback_handler] if callback_handler else None
            
            # 서비스 계정 키 JSON 파일에서 credentials 생성
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_APPLICATION_CREDENTIALS_VERTEXAI,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
            except Exception as e:
                logger.error(f"서비스 계정 credentials 생성 실패: {str(e)}")
                raise
                
            return ChatVertexAI(
                model_name="gemini-pro",
                temperature=kwargs.get("temperature", 0.2),
                max_output_tokens=kwargs.get("max_output_tokens", 2048),
                top_p=kwargs.get("top_p", 0.7),
                top_k=kwargs.get("top_k", 20),
                project=settings.GOOGLE_PROJECT_ID_VERTEXAI,
                location=settings.GOOGLE_LOCATION_VERTEXAI,
                credentials=credentials,
                streaming=streaming,
                callbacks=callbacks,
            )
        else:
            raise ValueError("Unsupported model")
        
        raise ValueError(f"지원되지 않는 LLM 타입입니다: {self._llm_type}")
    def change_llm(self, llm_type: str, api_key: str, **kwargs):
        try:
            # 현재 모델 인덱스 업데이트
            for idx, model_info in enumerate(self._llm_list):
                if model_info["model"].lower() == llm_type.lower():
                    self._current_model_idx = idx
                    break
            else:
                raise ValueError(f"지원되지 않는 LLM 타입입니다: {llm_type}")
            
            # LLM 모델 전환
            self._llm_type = llm_type
            self._llm = self.get_llm(llm_type, api_key, **kwargs)
            
            # API 키 업데이트
            self._llm_list[self._current_model_idx]["api_key"] = api_key
            
            logger.info(f"LLM 모델 전환 완료: {llm_type}")
            
        except Exception as e:
            logger.error(f"LLM 모델 전환 실패: {str(e)}")
            # 실패 시 다음 가능한 모델로 자동 전환
            self.select_next_llm()
            raise

    def select_next_llm(self):
        """다음 LLM 모델로 전환"""
        self._current_model_idx = (self._current_model_idx + 1) % len(self._llm_list)
        model_info = self._llm_list[self._current_model_idx]
        self._llm = self.get_llm(model_info["model"], model_info["api_key"])
        logger.info(f"LLM 모델 전환: {model_info['model']}")
    def get_current_llm_info(self) -> dict:
        """현재 사용 중인 LLM 모델 정보 반환"""
        return {
            "model": self._llm_list[self._current_model_idx]["model"],
            "current_index": self._current_model_idx,
            "total_models": len(self._llm_list)
        }

    def get_available_models(self) -> list:
        """사용 가능한 모든 LLM 모델 목록 반환"""
        return [model_info["model"] for model_info in self._llm_list]
        

    def generate(self, user_query: str, prompt_context: str) -> Optional[AIMessage]:
        """동기 컨텐츠 생성"""
        try:
            logger.info(f"LANGCHAIN_TRACING_V2[Settings]: {settings.LANGCHAIN_TRACING_V2}")
            import os
            logger.info(f"LANGCHAIN_TRACING_V2[OS]: {os.getenv('LANGCHAIN_TRACING_V2')}")
            truncated = prompt_context[:100] + "..." if len(prompt_context) > 100 else prompt_context
            logger.info(f" {self._llm_type} full[Sync] 호출 - 프롬프트: {truncated[:100]}...")
            # 프롬프트 템플릿 설정
            system_message_prompt = SystemMessagePromptTemplate.from_template(prompt_context)
            user_message_prompt = HumanMessagePromptTemplate.from_template(user_query)
            prompt_template = ChatPromptTemplate.from_messages([system_message_prompt, user_message_prompt])
            formatted_messages = prompt_template.format_messages(context=prompt_context, question=user_query)

            
            # API 호출 및 전체 응답 받기
            # 응답 타입(Google) : 'langchain_core.messages.ai.AIMessage'
            full_response = self._llm.invoke(formatted_messages)
            
            logger.info(f"응답 타입: {type(full_response)}")
            # content='## 분석 결과 어쩌고 저쩌고..'
            # 응답 메세지 상세.
            #  additional_kwargs={}
            #  response_metadata={
            #    'prompt_feedback': {'block_reason': 0, 'safety_ratings': []}, 
            #    'finish_reason': 'STOP', 
            #    'safety_ratings': [
            #           {'category': 'HARM_CATEGORY_HATE_SPEECH', 'probability': 'NEGLIGIBLE', 'blocked': False}, 
            #           {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'probability': 'NEGLIGIBLE', 'blocked': False}, 
            #           {'category': 'HARM_CATEGORY_HARASSMENT', 'probability': 'NEGLIGIBLE', 'blocked': False}, 
            #           {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'probability': 'NEGLIGIBLE', 'blocked': False}]}
            #  id='run-cd10c37c-c733-4607-a9e4-b543bbecbb2c-0' 
            #  usage_metadata={'input_tokens': 1827, 'output_tokens': 818, 'total_tokens': 2645, 'input_token_details': {'cache_read': 0}}

            # 여기서는 full_response를 리턴하자. 메세지를 재조립하는것은 위에서 알아서 할일.
            logger.info(f"{self._llm_type} API 호출 완료")
        except Exception as e:
            logger.error(f"{self._llm_type} 호출 실패: {str(e)}")
            raise
        return full_response
    
    def generate_stream(self, user_query: str, prompt_context: str):
        """동기 스트리밍 컨텐츠 생성"""
        truncated = prompt_context[:100] + "..." if len(prompt_context) > 100 else prompt_context
        logger.info(f"Gemini API stream[Sync] 호출 - 프롬프트: {truncated}")
        system_message_prompt = SystemMessagePromptTemplate.from_template(prompt_context)
        user_message_prompt = HumanMessagePromptTemplate.from_template(f"{user_query}")
        prompt_template = ChatPromptTemplate.from_messages([system_message_prompt, user_message_prompt])
        formatted_messages = prompt_template.format_messages(context=prompt_context, question=user_query)
        
        # 스트리밍 응답 생성
        for chunk in self._llm_streaming.stream(formatted_messages):
            yield chunk
    
    async def agenerate(self, user_query: str, prompt_context: str) -> Optional[AIMessage]:
        #prompt_template = ChatPromptTemplate.from_template("{prompt}")
        ## 프롬프트 생성
        #messages = prompt_template.format_messages(prompt=prompt)
        try:
            truncated = prompt_context[:100] + "..." if len(prompt_context) > 100 else prompt_context
            logger.info(f"{self._llm_type} API [Async] 호출 - 프롬프트: {truncated}")
            system_message_prompt = SystemMessagePromptTemplate.from_template(prompt_context)
            user_message_prompt = HumanMessagePromptTemplate.from_template(f"{user_query}")
            prompt_template = ChatPromptTemplate.from_messages([system_message_prompt, user_message_prompt])
            formatted_messages = prompt_template.format_messages(context=prompt_context, question=user_query)

            # API 호출 및 전체 응답 받기
            full_response = await self._llm.ainvoke(formatted_messages)
        except Exception as e:
            logger.error(f"{self._llm_type}[agenerate] 호출 실패: {str(e)}")
            raise
        

        return full_response
    
    async def agenerate_stream(self, user_query: str, prompt_context: str):
        """비동기 스트리밍 컨텐츠 생성"""
        truncated = prompt_context[:100] + "..." if len(prompt_context) > 100 else prompt_context
        logger.info(f"{self._llm_type} API streaming[Async] 호출 - 프롬프트: {truncated}")
        self._should_stop = False
        logger.info(f"LANGCHAIN_TRACING_V2: {settings.LANGCHAIN_TRACING_V2}")
        #logger.info(f"LANGCHAIN_PROJECT: {settings.LANGCHAIN_PROJECT}")
        
        try:
            async with self._stream_lock:  # 스트림 세션 동기화
                
                content = prompt_context.replace('{', '{{').replace('}', '}}')
                # 개행 문자 정규화
                sanitized_prompt_context = content.replace('\r\n', '\n').replace('\r', '\n')

                system_message_prompt = SystemMessagePromptTemplate.from_template(sanitized_prompt_context)
                # User 메시지 템플릿
                user_message_prompt = HumanMessagePromptTemplate.from_template(f"{user_query}")

                # ChatPromptTemplate 구성
                prompt_template = ChatPromptTemplate.from_messages([system_message_prompt, user_message_prompt])

                # 메시지 생성
                formatted_messages = prompt_template.format_messages(context=sanitized_prompt_context, question=user_query)
                
                # 스트리밍 시작
                stream = self._llm_streaming.astream(formatted_messages)
                
                try:
                    # 현재 태스크 저장
                    self._current_task = asyncio.current_task()
                    
                    async for chunk in stream:
                        if self._should_stop:
                            logger.info("LLM 메시지 생성이 중지되었습니다.")
                            break
                        if chunk and chunk.content:
                            yield chunk
                            
                except asyncio.CancelledError:
                    logger.info("스트리밍 태스크가 취소되었습니다.")
                    raise
                finally:
                    self._current_task = None
                    
        except Exception as e:
            logger.exception(f"스트리밍 응답 생성 중 오류 발생[Async]: {str(e)}")
            raise e
        finally:
            self._should_stop = False

            self._current_task = None

    def generate_content_only(self, user_query: str, prompt_context: str) -> Optional[str]:
        """동기 컨텐츠 생성"""
        response = self.generate(user_query, prompt_context)
        return response.content
        # logger.info(f"Gemini API[Sync] 호출 - 프롬프트: {prompt[:100]}...")
        # # 프롬프트 템플릿 설정
        # prompt_template = ChatPromptTemplate.from_template("{prompt}")

        # # 파이프라인 구성
        # chain = prompt_template | self._llm | StrOutputParser()

        # # 파이프라인 실행
        # response = chain.invoke({"prompt": prompt})
        # logger.info(f"Gemini API 호출 완료")
        # # 그냥 text, content만 리턴된다.
        # return response
    async def generate_content_only_async(self, prompt: str) -> Optional[str]:
        """비동기 컨텐츠 생성"""
        logger.info(f"{self._llm_type} API[Async] 호출 - 프롬프트: {prompt[:100]}...")
        response: AIMessage = await self.agenerate(prompt=prompt)
        return response.content
    
    async def stop_generation(self):
        """메시지 생성 중지"""
        self._should_stop = True
        if self._current_task and not self._current_task.done():
            try:
                # 현재 실행 중인 태스크 취소
                self._current_task.cancel()
                await asyncio.shield(self._current_task)  # 태스크가 정리될 때까지 대기
            except asyncio.CancelledError:
                logger.info("스트리밍 태스크가 성공적으로 취소되었습니다.")
            except Exception as e:
                logger.error(f"태스크 취소 중 오류 발생: {str(e)}")
            finally:
                self._current_task = None

    
