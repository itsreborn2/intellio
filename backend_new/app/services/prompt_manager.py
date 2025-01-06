"""프롬프트 관리 및 실행을 담당하는 매니저"""

from typing import Dict, Any, List
from enum import Enum
import logging
import aiohttp
from openai import AsyncOpenAI

from app.core.config import settings
from app.services.prompt_chains import (
    DocumentType,
    PromptChainManager,
    PromptChainResponse
)

class PromptMode(Enum):
    CHAT = "chat"
    TABLE_HEADER = "table_header"
    TABLE = "table"

class PromptManager:
    """프롬프트 관리 및 실행을 담당하는 매니저 클래스"""

    # 테이블 헤더용 시스템 메시지는 유지
    TABLE_HEADER_SYSTEM_MSG = """
    사용자의 자연어 명령을 2-3단어로 된 간단한 헤더로 변환하세요.

    규칙:
    1. 반드시 2-3단어로 구성된 헤더만 생성
    2. 헤더는 명사형으로 끝나야 함
    3. 명령의 핵심 의미를 포함해야 함
    4. 불필요한 조사나 어미 제거
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # AI 모델 클라이언트 초기화
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.gemini_api_key = settings.GEMINI_API_KEY
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        
        # 프롬프트 체인 매니저 초기화
        self.chain_manager = PromptChainManager()

    async def process_prompt(self, mode: PromptMode, context: Dict[str, Any]) -> str:
        """프롬프트 처리 및 응답 생성"""
        try:
            if mode == PromptMode.CHAT:
                return await self._process_chat(context)
            elif mode == PromptMode.TABLE_HEADER:
                return await self._process_table_header(context)
            elif mode == PromptMode.TABLE:
                return await self._process_table(context)
            else:
                raise ValueError(f"지원하지 않는 프롬프트 모드: {mode}")
                
        except Exception as e:
            self.logger.error(f"프롬프트 처리 실패: {str(e)}")
            raise

    async def _process_chat(self, context: Dict[str, Any]) -> str:
        """채팅 모드 프롬프트 처리"""
        try:
            # Gemini API 호출
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.gemini_api_key
                }
                
                # 프롬프트 구성
                prompt = f"""
다음 문서를 분석하여 질문에 답변하세요.

분석 규칙:
1. 숫자는 <np>+값</np> 또는 <nn>-값</nn> 형식으로 표시

질문: {context['query']}

문서 내용:
{context['content']}
"""
                
                payload = {
                    "contents": [{
                        "parts": [{
                            "text": prompt
                        }]
                    }],
                    "generationConfig": {
                        "temperature": 0.2,
                        "topK": 40,
                        "topP": 0.8,
                        "maxOutputTokens": 2048,
                    }
                }
                
                async with session.post(
                    self.gemini_url,
                    headers=headers,
                    json=payload
                ) as response:
                    result = await response.json()
                    
                    if "error" in result:
                        raise Exception(f"Gemini API 오류: {result['error']}")
                        
                    return result["candidates"][0]["content"]["parts"][0]["text"]
                    
        except Exception as e:
            self.logger.error(f"채팅 프롬프트 처리 실패: {str(e)}")
            raise

    async def _process_table_header(self, context: Dict[str, Any]) -> str:
        """테이블 헤더 처리"""
        try:
            messages = [
                {"role": "system", "content": self.TABLE_HEADER_SYSTEM_MSG},
                {"role": "user", "content": context.get('query', '')}
            ]
            
            completion = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.0
            )
            
            return completion.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(f"테이블 헤더 처리 실패: {str(e)}")
            raise

    async def _process_table(self, context: Dict[str, Any]) -> str:
        """테이블 내용 프롬프트 처리"""
        try:
            # 채팅 모드와 동일한 프롬프트 체인 사용
            prompt = f"""
다음 문서를 분석하여 테이블 형식으로 정리하세요.

분석 규칙:
1. 숫자는 <np>+값</np> 또는 <nn>-값</nn> 형식으로 표시

헤더: {context.get('header', '')}
문서 내용:
{context.get('content', '')}
"""
            return await self._call_gemini_api(prompt)
            
        except Exception as e:
            self.logger.error(f"테이블 내용 처리 실패: {str(e)}")
            raise

    async def _call_gemini_api(self, prompt: str) -> str:
        """Gemini API 호출"""
        try:
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": self.gemini_api_key,
            }
            
            data = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "topK": 32,
                    "topP": 1,
                    "maxOutputTokens": 2048,
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.gemini_url, headers=headers, json=data) as response:
                    result = await response.json()
                    
                    if "error" in result:
                        raise Exception(f"Gemini API 오류: {result['error']}")
                        
                    return result["candidates"][0]["content"]["parts"][0]["text"]
                    
        except Exception as e:
            self.logger.error(f"Gemini API 호출 실패: {str(e)}")
            raise

    async def _call_gpt_api(self, prompt: str) -> str:
        """GPT API 호출"""
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=150
            )
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"GPT API 호출 실패: {str(e)}")
            raise

    def generate_prompt(self, mode: PromptMode, context: Dict[str, Any]) -> str:
        """주어진 모드와 컨텍스트에 따라 프롬프트 생성"""
        try:
            if mode == PromptMode.CHAT:
                return self._generate_chat_prompt(context)
            elif mode == PromptMode.TABLE_HEADER:
                return self._generate_table_header_prompt(context)
            elif mode == PromptMode.TABLE:
                return self._generate_table_content_prompt(context)
            else:
                raise ValueError(f"지원하지 않는 프롬프트 모드: {mode}")
        except Exception as e:
            self.logger.error(f"프롬프트 생성 실패: {str(e)}")
            raise

    def validate_response(self, mode: PromptMode, response: str) -> bool:
        """응답의 유효성 검증"""
        try:
            if mode == PromptMode.CHAT:
                return self._validate_chat_response(response)
            elif mode == PromptMode.TABLE_HEADER:
                return self._validate_table_header_response(response)
            elif mode == PromptMode.TABLE:
                return self._validate_table_content_response(response)
            else:
                raise ValueError(f"지원하지 않는 검증 모드: {mode}")
        except Exception as e:
            self.logger.error(f"응답 검증 실패: {str(e)}")
            return False

    def _generate_chat_prompt(self, context: Dict[str, Any]) -> str:
        """채팅 모드 프롬프트 생성"""
        return f"문서 내용: {context.get('content', '')}\n질문: {context.get('query', '')}"

    def _generate_table_header_prompt(self, context: Dict[str, Any]) -> str:
        """테이블 헤더 프롬프트 생성"""
        return f"{self.TABLE_HEADER_SYSTEM_MSG}\n\n입력: {context.get('query', '')}"

    def _generate_table_content_prompt(self, context: Dict[str, Any]) -> str:
        """테이블 내용 프롬프트 생성"""
        return f"문서 내용: {context.get('content', '')}\n헤더: {context.get('header', '')}"

    def _validate_chat_response(self, response: str) -> bool:
        """채팅 응답 검증"""
        if not response:
            return False
            
        required_patterns = [
            r'#.*:',  # 제목 형식
            r'\d+\..*',  # 번호 매기기
            r'※.*'  # 결론/요약
        ]
        return all(re.search(pattern, response) for pattern in required_patterns)

    def _validate_table_header_response(self, response: str) -> bool:
        """테이블 헤더 응답 검증"""
        if not response:
            return False
            
        words = response.split()
        return (2 <= len(words) <= 3 and 
                not any(particle in response for particle in ['은', '는', '이', '가', '을', '를']))

    def _validate_table_content_response(self, response: str) -> bool:
        """테이블 내용 응답 검증"""
        if not response:
            return False
            
        lines = response.split('\n')
        return (len(lines) > 1 and 
                any(re.match(r'\d+\..*', line) for line in lines))

    async def enhance_response(self, mode: PromptMode, original_response: str, 
                             context: Dict[str, Any]) -> str:
        """응답 품질 향상을 위한 보완 프롬프트 생성"""
        enhancement_prompts = {
            PromptMode.CHAT: """
            다음 응답을 개선하세요:
            
            원래 질문: {query}
            현재 응답: {response}
            
            개선 필요 사항:
            1. 구체적인 예시 추가
            2. 수치 데이터 포함
            3. 결론 명확화
            """,
            PromptMode.TABLE: """
            다음 테이블 내용을 개선하세요:
            
            헤더: {header}
            현재 내용: {response}
            
            개선 필요 사항:
            1. 구조화된 정보 추가
            2. 관련 수치 데이터 포함
            3. 핵심 정보 강조
            """
        }
        
        if mode not in enhancement_prompts:
            return original_response
            
        prompt_template = enhancement_prompts[mode]
        context['response'] = original_response
        return prompt_template.format(**context)
