from typing import Dict, Optional, Union, Any
from loguru import logger
from app.core.config import settings
import json
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

class LLMService:
    """
    LLM(Large Language Model) 서비스 클래스
    
    이 클래스는 Google의 Gemini Pro 모델을 사용하여 텍스트 분석과 생성을 수행합니다.
    주요 기능:
    - 문서 구조 분석
    - 텍스트 청크 최적화
    - JSON 형식의 응답 생성
    """
    
    def __init__(self):
        """
        LLM 서비스 초기화
        - Gemini API 설정
        - 모델 인스턴스 생성
        - 재시도 설정 초기화
        """
        try:
            # Gemini API 설정
            genai.configure(api_key=settings.GEMINI_API_KEY)
            
            # 생성 설정
            generation_config = {
                "temperature": 0.3,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
            
            # 모델 초기화
            self.model = genai.GenerativeModel(
                model_name="models/gemini-2.0-flash-exp",
                generation_config=genai.GenerationConfig(**generation_config),
                safety_settings=[
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ]
            )
            
            logger.info("LLM 서비스가 성공적으로 초기화되었습니다.")
            
        except Exception as e:
            logger.error(f"LLM 서비스 초기화 중 오류 발생: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),  # 최대 3번 재시도
        wait=wait_exponential(multiplier=1, min=4, max=10)  # 지수 백오프
    )
    async def analyze(self, prompt: str) -> Dict[str, Any]:
        """
        프롬프트를 분석하여 결과를 반환합니다.
        
        Args:
            prompt (str): 분석할 프롬프트 텍스트
            
        Returns:
            Dict[str, Any]: 분석 결과를 담은 딕셔너리
            
        Raises:
            Exception: API 호출 실패나 응답 파싱 실패시 발생
        """
        if not prompt:
            logger.warning("빈 프롬프트가 전달되었습니다.")
            return {"error": "프롬프트가 비어있습니다."}
            
        try:
            # 프롬프트에 JSON 형식 강조 추가
            enhanced_prompt = f"""
            {prompt}
            
            중요: 응답은 반드시 올바른 JSON 형식이어야 합니다.
            잘못된 예: 일반 텍스트 응답
            올바른 예: {{"key": "value", "list": [1, 2, 3]}}
            """
            
            # Gemini API 호출
            response = await self.model.generate_content_async(
                enhanced_prompt,
                safety_settings=[
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ]
            )
            
            # 응답 텍스트 추출 및 정제
            response_text = response.text.strip()
            
            # JSON 형식 확인 및 파싱
            try:
                # 응답에서 JSON 부분만 추출
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    return json.loads(json_str)
                else:
                    # JSON이 없으면 에러로 처리
                    logger.error("응답에서 JSON을 찾을 수 없습니다")
                    return {
                        "error": "JSON 형식이 아닌 응답",
                        "raw_response": response_text
                    }
                    
            except json.JSONDecodeError as e:
                logger.error(f"JSON 파싱 실패: {e}")
                return {
                    "error": "JSON 파싱 실패",
                    "raw_response": response_text
                }
                
        except Exception as e:
            logger.error(f"LLM 분석 중 오류 발생: {e}")
            raise

    async def optimize_text(self, text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        주어진 텍스트를 최적화합니다.
        
        Args:
            text (str): 최적화할 텍스트
            context (Dict[str, Any], optional): 컨텍스트 정보
            
        Returns:
            Dict[str, Any]: 최적화된 텍스트와 메타데이터
        """
        prompt = f"""
        다음 텍스트를 RAG 시스템에 최적화하세요.
        
        컨텍스트:
        {json.dumps(context, ensure_ascii=False) if context else "컨텍스트 없음"}
        
        텍스트:
        {text}
        
        다음 형식으로 JSON 응답을 제공하세요:
        {{
            "optimized_text": "최적화된 텍스트",
            "key_terms": ["주요 키워드"],
            "info_density": 1-10,
            "requires_context": true/false
        }}
        """
        
        return await self.analyze(prompt)
