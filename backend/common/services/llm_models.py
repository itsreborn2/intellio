import asyncio
from typing import Any, List, Optional,  Callable

from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.callbacks import BaseCallbackHandler

from langchain_openai import ChatOpenAI
from langchain_google_vertexai import ChatVertexAI

from pydantic import BaseModel
from google.oauth2 import service_account
import json
from loguru import logger
from common.core.config import settings

from uuid import UUID
from common.services.token_usage_service import TokenUsageQueue, track_token_usage, track_token_usage_bg, track_token_usage_sync
from common.services.embedding_models import TokenCounter

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
            logger.warning(f"LLMModels : {model_info['model']} Streaming")
            logger.warning(f"LLMModels : {model_info['model']} API 초기화")
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
        logger.warning(f"LLMModels : {model_info['model']} Streaming")


    def get_llm(self, model_name: str, 
                    api_key: str | None, 
                    streaming: bool = False, 
                    callback_handler: Optional[BaseCallbackHandler] = None,
                    **kwargs) -> BaseChatModel:
        if model_name == "openai":
            callbacks = [callback_handler] if callback_handler else None
            return ChatOpenAI(
                        model="gpt-4o-mini",
                        openai_api_key=api_key,
                        temperature=kwargs.get("temperature", 0.2),
                        max_tokens=kwargs.get("max_output_tokens", 2048),
                        top_p=kwargs.get("top_p", 0.7),
                        streaming=streaming,
                        callbacks=callbacks,
                    )
        elif model_name == "gemini":
                # 모델 이름: models/gemini-2.5-pro-exp-03-25
                # 표시 이름: Gemini 2.5 Pro Experimental 03-25
                # ---
                # 모델 이름: models/gemini-2.0-flash-exp
                # 표시 이름: Gemini 2.0 Flash Experimental
                # ---
                # 모델 이름: models/gemini-2.0-flash
                # 표시 이름: Gemini 2.0 Flash
                # ---
                # 모델 이름: models/gemini-2.0-flash-001
                # 표시 이름: Gemini 2.0 Flash 001
                # ---
                # 모델 이름: models/gemini-2.0-flash-exp-image-generation
                # 표시 이름: Gemini 2.0 Flash (Image Generation) Experimental
                # ---
                # 모델 이름: models/gemini-2.0-flash-lite-001
                # 표시 이름: Gemini 2.0 Flash-Lite 001
                # ---
                # 모델 이름: models/gemini-2.0-flash-lite
                # 표시 이름: Gemini 2.0 Flash-Lite
                # ---
                # 모델 이름: models/gemini-2.0-flash-lite-preview-02-05
                # 표시 이름: Gemini 2.0 Flash-Lite Preview 02-05
                # ---
                # 모델 이름: models/gemini-2.0-flash-lite-preview
                # 표시 이름: Gemini 2.0 Flash-Lite Preview
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
                # ---
                # 모델 이름: models/learnlm-1.5-pro-experimental
                # 표시 이름: LearnLM 1.5 Pro Experimental
                # ---
                # 모델 이름: models/gemma-3-27b-it
                # 표시 이름: Gemma 3 27B
                # ---
                # 모델 이름: models/embedding-001
                # 표시 이름: Embedding 001
                # ---
                # 모델 이름: models/text-embedding-004
                # 표시 이름: Text Embedding 004
                # ---
                # 모델 이름: models/gemini-embedding-exp-03-07
                # 표시 이름: Gemini Embedding Experimental 03-07
                # ---
                # 모델 이름: models/gemini-embedding-exp
                # 표시 이름: Gemini Embedding Experimental
                # ---
                # 모델 이름: models/imagen-3.0-generate-002
                # 표시 이름: Imagen 3.0 002 model
            callbacks = [callback_handler] if callback_handler else None
            return ChatGoogleGenerativeAI(
                        #model="models/gemini-2.0-flash-001",
                        model="models/gemini-2.0-flash", # 실험모델은 분당 횟수 제한이 심함 분당 2~5회. 사용불가한 수준
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
        

    def generate(self, user_query: str, prompt_context: str, user_id: Optional[UUID] = None, project_type: Optional[str] = None) -> Optional[AIMessage]:
        """동기 컨텐츠 생성"""
        try:
            #logger.info(f"LANGCHAIN_TRACING_V2[Settings]: {settings.LANGCHAIN_TRACING_V2}")
            import os
            #logger.info(f"LANGCHAIN_TRACING_V2[OS]: {os.getenv('LANGCHAIN_TRACING_V2')}")
            truncated = prompt_context[:100] + "..." if len(prompt_context) > 100 else prompt_context
            logger.info(f" {self._llm_type} full[Sync] 호출 - 프롬프트: {truncated[:100]}...")
            # 프롬프트 템플릿 설정
            # {context}와 {question}은 템플릿 내의 변수 플레이스홀더
            # format_messages() 메서드를 호출할 때 context=prompt_context, question=user_query와 같이 실제 값을 전달
            system_message_prompt = SystemMessagePromptTemplate.from_template("{context}")
            user_message_prompt = HumanMessagePromptTemplate.from_template("{question}")
            prompt_template = ChatPromptTemplate.from_messages([system_message_prompt, user_message_prompt])
            formatted_messages = prompt_template.format_messages(context=prompt_context, question=user_query)

            # 토큰 사용량 추적이 필요한 경우
            if user_id and project_type:
                # 동기 DB 세션 팩토리
                from common.core.database import SessionLocal
                
                with track_token_usage_sync(
                    user_id=user_id,
                    project_type=project_type,
                    token_type="llm",
                    model_name=self._llm.model,
                    db_getter=SessionLocal
                ) as tracker:
                    # API 호출 및 전체 응답 받기
                    full_response = self._llm.invoke(formatted_messages)
                    
                    # 응답에서 토큰 사용량 추출
                    if hasattr(full_response, "usage_metadata"):
                        usage = full_response.usage_metadata
                        tracker.add_tokens(
                            prompt_tokens=usage.get("input_tokens", 0),
                            completion_tokens=usage.get("output_tokens", 0),
                            total_tokens=usage.get("total_tokens", None)
                        )
                    logger.info(f"{self._llm_type} API 호출 완료 (토큰 사용량 추적됨)")
            else:
                # 토큰 추적 없이 실행
                full_response = self._llm.invoke(formatted_messages)
                logger.info(f"{self._llm_type} API 호출 완료")
        except Exception as e:
            logger.error(f"{self._llm_type} 호출 실패: {str(e)}")
            raise
        return full_response
    def generate_with_structured_output(self, user_query: str, prompt_context: str, _struct: BaseModel) -> Any:
        """
        구조화된 출력을 생성하는 메서드
        
        Args:
            user_query: 사용자 질의
            prompt_context: 프롬프트 컨텍스트
            _struct: BaseModel을 상속받은 Pydantic 모델 클래스
            
        Returns:
            _struct 타입의 객체
        """
        try:
            truncated = prompt_context[:100] + "..." if len(prompt_context) > 100 else prompt_context
            logger.info(f" {self._llm_type} structured output[Sync] 호출 - 프롬프트: {truncated[:100]}...")
            
            # 모델 스키마 정보 추출
            schema_info = _struct.model_json_schema()
            schema_str = json.dumps(schema_info, ensure_ascii=False, indent=2)
            #logger.info(f"요청 스키마: {schema_str}")
            
            # 프롬프트에 스키마 정보 추가
            enhanced_context = f"{prompt_context}\n\n출력 형식 스키마:\n{schema_str}\n\n반드시 위 스키마에 맞는 형식으로 응답해주세요. 각 필드의 타입/Description을 정확히 지켜주세요. JSON 형식으로만 응답해주세요."
            
            # 프롬프트 템플릿 설정
            system_message_prompt = SystemMessagePromptTemplate.from_template("{context}")
            user_message_prompt = HumanMessagePromptTemplate.from_template("{question}")
            prompt_template = ChatPromptTemplate.from_messages([system_message_prompt, user_message_prompt])
            formatted_messages = prompt_template.format_messages(context=enhanced_context, question=user_query)
            
            
            
            # 방법 2: 직접 파싱 방식 (새로운 방식)
            try:
                # 일반 LLM 호출로 원본 응답 얻기
                raw_response = self._llm.invoke(formatted_messages)
                #logger.info(f"LLM 원본 응답: {raw_response.content}")
                
                # JSON 응답 추출 시도
                try:
                    # JSON 형식 응답 추출 (```json ... ``` 형식 처리)
                    import re
                    json_pattern = r'```(?:json)?\s*([\s\S]*?)```'
                    json_match = re.search(json_pattern, raw_response.content)
                    
                    if json_match:
                        json_str = json_match.group(1).strip()
                    else:
                        # 일반 텍스트에서 JSON 객체 찾기 시도
                        json_str = raw_response.content.strip()
                    
                    # JSON 파싱
                    parsed_data = json.loads(json_str)
                    #logger.info(f"파싱된 JSON 데이터: {json.dumps(parsed_data, ensure_ascii=False, indent=2)}")
                    
                    # Pydantic 모델로 변환
                    direct_structured_response = _struct(**parsed_data)
                    #logger.info(f"직접 파싱 방식 응답: {direct_structured_response.model_dump()}")
                    
                    # 직접 파싱 방식 사용
                    return direct_structured_response
                    
                except (json.JSONDecodeError, ValueError) as json_error:
                    logger.warning(f"직접 JSON 파싱 실패, LangChain 구조화 출력으로 대체: {str(json_error)}")
                    # 방법 1: LangChain의 구조화된 출력 사용 (기존 방식)
                    structured_llm = self._llm.with_structured_output(_struct)
                    # JSON 파싱 실패 시 LangChain 방식으로 폴백
                    structured_response = structured_llm.invoke(formatted_messages)
                    
                    # 구조화된 응답 내용 로깅
                    response_dict = structured_response.model_dump()
                    logger.info(f"LangChain 구조화 응답 내용: {json.dumps(response_dict, ensure_ascii=False, indent=2)}")
                    
                    logger.info(f"구조화된 응답 타입: {type(structured_response)}")
                    logger.info(f"{self._llm_type} 구조화된 API 호출 완료")
                    return structured_response
                    
            except Exception as parsing_error:
                # 파싱 오류 발생 시 재시도
                logger.warning(f"구조화된 출력 파싱 오류, 재시도 중: {str(parsing_error)}")
                
                # 오류 정보를 포함한 프롬프트로 재시도
                error_prompt = f"{enhanced_context}\n\n이전 응답에서 다음 오류가 발생했습니다: {str(parsing_error)}\n반드시 스키마에 맞는 형식으로 응답해주세요. JSON 형식으로만 응답해주세요."
                retry_messages = prompt_template.format_messages(context=error_prompt, question=user_query)
                
                # 일반 LLM 호출로 원본 응답 확인 (재시도)
                raw_retry_response = self._llm.invoke(retry_messages)
                logger.info(f"재시도 LLM 원본 응답: {raw_retry_response.content}")
                
                # JSON 응답 추출 재시도
                try:
                    # JSON 형식 응답 추출 (```json ... ``` 형식 처리)
                    import re
                    json_pattern = r'```(?:json)?\s*([\s\S]*?)```'
                    json_match = re.search(json_pattern, raw_retry_response.content)
                    
                    if json_match:
                        json_str = json_match.group(1).strip()
                    else:
                        # 일반 텍스트에서 JSON 객체 찾기 시도
                        json_str = raw_retry_response.content.strip()
                    
                    # JSON 파싱
                    parsed_data = json.loads(json_str)
                    logger.info(f"재시도 파싱된 JSON 데이터: {json.dumps(parsed_data, ensure_ascii=False, indent=2)}")
                    
                    # Pydantic 모델로 변환
                    direct_structured_response = _struct(**parsed_data)
                    logger.info(f"재시도 직접 파싱 방식 응답: {direct_structured_response.model_dump()}")
                    
                    # 직접 파싱 방식 사용
                    return direct_structured_response
                    
                except (json.JSONDecodeError, ValueError) as json_error:
                    logger.warning(f"재시도 직접 JSON 파싱 실패, LangChain 구조화 출력으로 대체: {str(json_error)}")
                    # JSON 파싱 실패 시 LangChain 방식으로 폴백
                    structured_response = structured_llm.invoke(retry_messages)
                    
                    # 재시도 후 구조화된 응답 내용 로깅
                    retry_response_dict = structured_response.model_dump()
                    logger.info(f"재시도 후 LangChain 구조화된 응답 내용: {json.dumps(retry_response_dict, ensure_ascii=False, indent=2)}")
                    
                    logger.info(f"재시도 후 구조화된 응답 타입: {type(structured_response)}")
                    return structured_response
                
        except Exception as e:
            logger.error(f"{self._llm_type} 구조화된 출력 생성 실패: {str(e)}")
            raise
    
    def generate_stream(self, user_query: str, prompt_context: str, user_id: Optional[UUID] = None, project_type: Optional[str] = None):
        """동기 스트리밍 컨텐츠 생성"""
        truncated = prompt_context[:100] + "..." if len(prompt_context) > 100 else prompt_context
        logger.info(f"{self._llm_type} API stream[Sync] 호출 - 프롬프트: {truncated}")
        system_message_prompt = SystemMessagePromptTemplate.from_template("{context}")
        user_message_prompt = HumanMessagePromptTemplate.from_template("{question}")
        prompt_template = ChatPromptTemplate.from_messages([system_message_prompt, user_message_prompt])
        formatted_messages = prompt_template.format_messages(context=prompt_context, question=user_query)
        
        # 토큰 사용량 추적 정보
        token_tracking = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        
        try:
            # 스트리밍 응답 생성
            for i, chunk in enumerate(self._llm_streaming.stream(formatted_messages)):
                if hasattr(chunk, "usage_metadata"):
                    usage_metadata = chunk.usage_metadata
                    token_tracking["prompt_tokens"] += usage_metadata['input_tokens']
                    token_tracking["completion_tokens"] += usage_metadata['output_tokens']
                    token_tracking["total_tokens"] += usage_metadata['total_tokens']

                
                # 응답의 각 청크를 반환
                yield chunk
        except Exception as e:
            logger.error(f"{self._llm_type} 스트리밍 응답 생성 중 오류 발생: {str(e)}")
            raise
        finally:
            # 스트리밍 완료 후 토큰 사용량 저장
            if user_id and project_type:
                # 비동기 코드이지만 동기 코드 내에서 호출해야 함
                import asyncio
                if asyncio.get_event_loop().is_running():
                    asyncio.create_task(self._save_token_usage_bg(
                        user_id=user_id,
                        project_type=project_type,
                        token_type="llm",
                        model_name=self._llm_streaming.model,
                        token_data={
                            "prompt_tokens": token_tracking["prompt_tokens"],
                            "completion_tokens": token_tracking["completion_tokens"],
                            "total_tokens": token_tracking["total_tokens"],
                            "total_cost": 0.0  # 실제 비용 계산 필요
                        }
                    ))
                else:
                    logger.warning("이벤트 루프가 실행 중이 아니어서 토큰 사용량을 저장할 수 없습니다.")
    
    async def _save_token_usage_bg(self, user_id: UUID, project_type: str, token_type: str, model_name: str, token_data: dict):
        """백그라운드에서 토큰 사용량 저장 (유틸리티 메서드)"""
        try:
            queue = TokenUsageQueue()
            await queue.add_usage(
                user_id=user_id,
                project_type=project_type,
                token_type=token_type,
                model_name=model_name,
                token_data=token_data
            )
            logger.info(f"토큰 사용량이 큐에 추가됨: {token_data}")
        except Exception as e:
            logger.error(f"토큰 사용량 저장 중 오류 발생: {str(e)}")
    
    @track_token_usage_bg(token_type="llm")
    async def agenerate(self, user_query: str, prompt_context: str, user_id: Optional[UUID] = None, project_type: Optional[str] = None) -> Optional[AIMessage]:
        try:
            truncated = prompt_context[:100] + "..." if len(prompt_context) > 100 else prompt_context
            logger.info(f"{self._llm_type} API [Async] 호출 - 프롬프트: {truncated}")

            system_message_prompt = SystemMessagePromptTemplate.from_template("{context}")
            user_message_prompt = HumanMessagePromptTemplate.from_template("{question}")
            prompt_template = ChatPromptTemplate.from_messages([system_message_prompt, user_message_prompt])
            formatted_messages = prompt_template.format_messages(context=prompt_context, question=user_query)

            # API 호출 및 전체 응답 받기 
            # track_token_usage_bg 데코레이터로 인해 자동으로 토큰 사용량 추적됨
            full_response = await self._llm.ainvoke(formatted_messages)
        except Exception as e:
            logger.error(f"{self._llm_type}[agenerate] 호출 실패: {str(e)}")
            raise
        
        return full_response
    
    async def agenerate_stream(self, user_query: str, prompt_context: str, user_id: Optional[UUID] = None, project_type: Optional[str] = None):
        """비동기 스트리밍 컨텐츠 생성"""
        truncated = prompt_context[:100] + "..." if len(prompt_context) > 100 else prompt_context
        logger.info(f"{self._llm_type} API streaming[Async] 호출 - 프롬프트: {truncated}")
        self._should_stop = False
        
        try:
            async with self._stream_lock:  # 스트림 세션 동기화
                
                content = prompt_context.replace('{', '{{').replace('}', '}}')
                # 개행 문자 정규화
                sanitized_prompt_context = content.replace('\r\n', '\n').replace('\r', '\n')

                system_message_prompt = SystemMessagePromptTemplate.from_template("{context}")
                user_message_prompt = HumanMessagePromptTemplate.from_template("{question}")

                # ChatPromptTemplate 구성
                prompt_template = ChatPromptTemplate.from_messages([system_message_prompt, user_message_prompt])

                # 메시지 생성
                formatted_messages = prompt_template.format_messages(context=sanitized_prompt_context, question=user_query)
                
                # 토큰 사용량 추적 정보
                token_tracking = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }
                
                # 스트리밍 시작
                stream = self._llm_streaming.astream(formatted_messages)
                
                try:
                    # 현재 태스크 저장
                    self._current_task = asyncio.current_task()
                    chunk_count = 0
                    
                    async for chunk in stream:
                        if self._should_stop:
                            logger.info("LLM 메시지 생성이 중지되었습니다.")
                            break

                        if hasattr(chunk, "usage_metadata"):
                            usage_metadata = chunk.usage_metadata
                            token_tracking["prompt_tokens"] += usage_metadata['input_tokens']
                            token_tracking["completion_tokens"] += usage_metadata['output_tokens']
                            token_tracking["total_tokens"] += usage_metadata['total_tokens']
                        
                        if chunk and chunk.content:
                            yield chunk
                            
                        chunk_count += 1
                            
                except asyncio.CancelledError:
                    logger.info("스트리밍 태스크가 취소되었습니다.")
                    raise
                finally:
                    self._current_task = None
                
                    logger.info(f"최종 토큰 사용량 정보: 입력={token_tracking['prompt_tokens']}, 출력={token_tracking['completion_tokens']}, 전체={token_tracking['total_tokens']}")
                    # 토큰 사용량 저장
                    await self._save_token_usage_bg(
                        user_id=user_id,
                        project_type=project_type,
                        token_type="llm",
                        model_name=self._llm_streaming.model,
                        token_data={
                            "prompt_tokens": token_tracking["prompt_tokens"],
                            "completion_tokens": token_tracking["completion_tokens"],
                            "total_tokens": token_tracking["total_tokens"],
                            "total_cost": 0.0  # 실제 비용 계산 필요
                        }
                    )
                
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

    
