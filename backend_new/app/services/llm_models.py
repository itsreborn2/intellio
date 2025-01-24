import asyncio
from typing import Any, List, Optional
from langchain_core.messages import BaseMessage
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import BaseMessage, ChatMessage, ai
from langchain_core.callbacks.manager import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
from langchain_core.outputs import ChatResult
from langchain_openai import ChatOpenAI
import logging
import torch
from transformers import AutoModel, AutoTokenizer
from loguru import logger
from app.core.config import settings

logger = logging.getLogger(__name__)

class KfDebertaAI(BaseChatModel):
    
    def _load_model_and_tokenizer(self):
        model = AutoModel.from_pretrained("app/kf-deberta")
        tokenizer = AutoTokenizer.from_pretrained("app/kf-deberta")
        return model, tokenizer
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # 모델과 토크나이저 로드
        model, tokenizer = self._load_model_and_tokenizer()
        
        # 메시지 내용 추출
        text = messages[-1].content
        
        # 토큰화 및 모델 입력 준비
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        
        # 모델 추론
        with torch.no_grad():
            model_output = model(**inputs)
        
        # 마지막 히든 스테이트 사용
        last_hidden_state = model_output.last_hidden_state
        
        # 간단한 예시: 마지막 토큰의 임베딩을 사용하여 응답 생성
        last_token_embedding = last_hidden_state[0, -1, :]
        
        # 임베딩을 문자열로 변환 (실제 사용 시에는 더 복잡한 디코딩 로직이 필요할 수 있음)
        response = f"Generated response based on embedding: {last_token_embedding[:5].tolist()}"
        
        # ChatResult 객체 생성 및 반환
        ai_message = ai.AIMessage(content=response)
        return ChatResult(generations=[ai_message])
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # 모델과 토크나이저 로드 (비동기 컨텍스트에서 실행)
        model, tokenizer = await asyncio.to_thread(self._load_model_and_tokenizer)
        
        # 메시지 내용 추출
        text = messages[-1].content
        
        # 토큰화 및 모델 입력 준비 (비동기 컨텍스트에서 실행)
        inputs = await asyncio.to_thread(lambda: tokenizer(text, return_tensors="pt", truncation=True, max_length=512))
        
        # 모델 추론 (비동기 컨텍스트에서 실행)
        with torch.no_grad():
            model_output = await asyncio.to_thread(lambda: model(**inputs))
        
        # 마지막 히든 스테이트 사용
        last_hidden_state = model_output.last_hidden_state
        
        # 간단한 예시: 마지막 토큰의 임베딩을 사용하여 응답 생성
        last_token_embedding = last_hidden_state[0, -1, :]
        
        # 임베딩을 문자열로 변환
        response = f"Generated response based on embedding: {last_token_embedding[:5].tolist()}"
        
        # ChatResult 객체 생성 및 반환
        ai_message = ai.AIMessage(content=response)
        return ChatResult(generations=[ai_message])
    
    @property
    def _llm_type(self) -> str:
        """이 챗 모델에서 사용하는 언어 모델의 유형을 반환합니다."""
        return "KfDeberta"
    
class LLMModels:
    """AI Model을 랭체인에 맞게 구현"""
    _instance = None
    _llm_chain = None
    _llm_type = "gemini"
    _llm = None
    _current_model_idx = 0
    
    def __new__(cls, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.initialize([  {"model":"gemini", "api_key":settings.GEMINI_API_KEY },
                                        {"model":"openai", "api_key":settings.OPENAI_API_KEY },
                                        {"model":"kf-deberta", "api_key":None }
                                     ], 
                                      **kwargs)
        return cls._instance

    def initialize(self, llm_list:list, **kwargs):
        """LangChain 초기화"""
        if self._llm_chain is None:

            self._llm_list = llm_list
            # 첫 번째 모델로 초기화
            model_info = llm_list[self._current_model_idx]
            self._llm = self.get_llm(model_info["model"], model_info["api_key"], **kwargs)

            logger.info(f"LLMModels : {model_info['model']} API 초기화")

    def get_llm(self, model_name: str, api_key: str, **kwargs) -> BaseChatModel:
        if model_name == "openai":
            return ChatOpenAI(
                        model="gpt-3.5-turbo",
                        openai_api_key=api_key,
                        temperature=kwargs.get("temperature", 0.3),
                        max_tokens=kwargs.get("max_output_tokens", 2048),
                        top_p=kwargs.get("top_p", 0.8),
                        top_k=kwargs.get("top_k", 40),
                    )
        elif model_name == "gemini":
            return ChatGoogleGenerativeAI(
                        model="models/gemini-2.0-flash-exp",
                        google_api_key=api_key,
                        temperature=kwargs.get("temperature", 0.3),
                        max_output_tokens=kwargs.get("max_output_tokens", 2048),
                        top_p=kwargs.get("top_p", 0.8),
                        top_k=kwargs.get("top_k", 40),
                    )
        elif model_name == "kf-deberta":
            return KfDebertaAI()
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
        

    def generate(self, prompt: str) -> Optional[ai.AIMessage]:
        """동기 컨텐츠 생성"""
        logger.info(f"Gemini API full[Sync] 호출 - 프롬프트: {prompt[:100]}...")
        # 프롬프트 템플릿 설정
        prompt_template = ChatPromptTemplate.from_template("{prompt}")
        # 프롬프트 생성
        messages = prompt_template.format_messages(prompt=prompt)
        
        # API 호출 및 전체 응답 받기
        # 응답 타입(Google) : 'langchain_core.messages.ai.AIMessage'
        full_response = self._llm.invoke(messages)
        logger.info(f"응답 타입: {type(full_response)}")
        # content='## 분석 결과 어쩌고 저쩌고..'
        # 응답 메세지 상세.
        #  additional_kwargs={}
        #  response_metadata={
        #    'prompt_feedback': {'block_reason': 0, 'safety_ratings': []}, 
        #    'finish_reason': 'STOP', 
        #    'safety_ratings': [
        # 			{'category': 'HARM_CATEGORY_HATE_SPEECH', 'probability': 'NEGLIGIBLE', 'blocked': False}, 
        # 			{'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'probability': 'NEGLIGIBLE', 'blocked': False}, 
        # 			{'category': 'HARM_CATEGORY_HARASSMENT', 'probability': 'NEGLIGIBLE', 'blocked': False}, 
        # 			{'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'probability': 'NEGLIGIBLE', 'blocked': False}]}
        #  id='run-cd10c37c-c733-4607-a9e4-b543bbecbb2c-0' 
        #  usage_metadata={'input_tokens': 1827, 'output_tokens': 818, 'total_tokens': 2645, 'input_token_details': {'cache_read': 0}}
        logger.info(f"Gemini API 호출 완료")# : {full_response}")

        # 여기서는 full_response를 리턴하자. 메세지를 재조립하는것은 위에서 알아서 할일.
        return full_response
    
    def agenerate(self, prompt: str) -> Optional[ai.AIMessage]:
        prompt_template = ChatPromptTemplate.from_template("{prompt}")
        # 프롬프트 생성
        messages = prompt_template.format_messages(prompt=prompt)
        
        # API 호출 및 전체 응답 받기
        full_response = self._llm.ainvoke(messages)
        return full_response

    
    def generate_content_only(self, prompt: str) -> Optional[str]:
        """동기 컨텐츠 생성"""
        response = self.generate(prompt=prompt)
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
        logger.info(f"Gemini API[Async] 호출 - 프롬프트: {prompt[:100]}...")
        response: ai.AIMessage = await self.agenerate(prompt=prompt)
        return response.content
