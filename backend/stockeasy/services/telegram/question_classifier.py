import json
from typing import Dict, Any, List, Tuple, Optional
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from pydantic import BaseModel, Field

from common.services.llm_models import LLMModels

TOPIC_LABELS = {
   0: "종목기본정보",
   1: "전망",
   2: "기타"
}

ANSWER_LEVEL_LABELS = {
   0: "간단한답변",
   1: "긴설명요구",
   2: "종합적판단",
   3: "웹검색"
}

class QuestionClassification(BaseModel):
   """질문 분류 결과를 나타내는 Pydantic 모델"""
   질문주제: int = Field(..., description="질문 주제 (0: 종목기본정보, 1: 전망 관련, 2: 기타)")
   답변수준: int = Field(..., description="답변 요구 수준 (0: 간단한 답변, 1: 긴 설명 요구, 2: 종합적 판단, 3: 웹검색)")
   종목코드: Optional[str] = Field(None, description="기업의 종목코드")
   종목명: Optional[str] = Field(None, description="종목명")
   추가옵션: Optional[str] = Field(None, description="추가 옵션 (리포트검색, 뉴스검색 등)")
   
   def get_topic_label(self) -> str:
      """주제 번호에 해당하는 레이블을 반환합니다."""
      return TOPIC_LABELS.get(self.질문주제, "알 수 없음")
   
   def get_answer_level_label(self) -> str:
      """답변 수준 번호에 해당하는 레이블을 반환합니다."""
      return ANSWER_LEVEL_LABELS.get(self.답변수준, "알 수 없음")
   
   def to_dict_with_labels(self) -> Dict[str, Any]:
      """레이블이 포함된 딕셔너리를 반환합니다."""
      result = self.model_dump()
      result["질문주제_label"] = self.get_topic_label()
      result["답변수준_label"] = self.get_answer_level_label()

      return result


class QuestionClassifierService:
   
   AI_ROLE = """너는 금융 및 주식 관련 질문 분류 전문가이자, LLM 기반 질문분류기 역할을 수행한다.
사용자가 입력한 질문을 아래의 기준에 따라 분석하고, 각 항목에 대해 분류 결과를 도출해줘.

1. 질문 주제:
   - [종목기본정보]: 기업의 재무, 배당, 주가, 시세 등 기초 정보와 관련된 질문.
   - [전망]: 미래 전망, 투자 의견, 시장 분석, 미래 예측 등 미래의 흐름이나 전략에 관한 질문.
   - [기타]: 위 두 항목에 포함되지 않는 금융/주식 관련 기타 질문.

2. 답변 수준:
   - [간단한답변]: 단순 정보, 숫자 혹은 짧은 단답형 답변이 적절한 경우.
   - [긴설명요구]: 배경 정보, 근거 및 상세 설명이 필요한 경우.
   - [종합적판단]: 다양한 변수와 복합적 요소를 고려해 판단해야 하는 경우.
   - [웹검색]: 웹 검색을 통해 정보를 찾아야 하는 경우.

3. 추가 옵션 (선택 사항):
   - 만약 분류 결과에 따라 특정 DB 조회나 임베딩 검색 옵션이 달라져야 한다면, 그에 맞는 제안도 함께 제공해줘.
   - 예를 들어, "종목 기본 정보"에 해당하면 재무 데이터베이스, "전망 관련"이라면 시장 분석 리포트를 참고하는 옵션 등을 제안할 수 있음.
4. 종목명, 종목코드
   - 사용자는 종목명을 축약해서 넣는다. 예를 들어, "삼성전자"는 "삼전"으로 넣는다.
   - 축약된 종목명은 krx의 full name을 찾아서 종목명으로 넣어줘
   - full name 기준으로 종목코드를 검색해서 넣어줘

5. 결과 출력 형식 : JSON 형식. 필수.

사용자 질문 예시: "A기업(018273)의 배당률이 어떻게 되나요?"
- 분석 결과 예시:
   { "질문주제": "종목기본정보",
   "답변수준": "간단한답변",
   "종목코드":"018273",
   "종목명":"A기업 종목명",
   "추가옵션": "리포트검색"
   }

사용자 질문 예시: "B기업의 향후 성장 가능성과 시장 전망은 어떻게 보시나요?"
- 분석 결과 예시:
   { "질문주제": "전망",
   "답변수준": "긴설명요구|종합적판단",
   "추가옵션": "뉴스검색",
   "종목코드":"B기업 종목코드",
   "종목명":"B기업 종목명"
   }

이와 같은 형식으로 사용자 질문에 대한 분류 결과를 도출해줘."""


   
   # 역방향 매핑 (레이블 -> 인덱스)
   TOPIC_INDICES = {v: k for k, v in TOPIC_LABELS.items()}
   ANSWER_LEVEL_INDICES = {v: k for k, v in ANSWER_LEVEL_LABELS.items()}

   def __init__(self):
      self.llm = LLMModels()

   def classify_question(self, question: str) -> QuestionClassification:
      result = self.llm.generate(question, self.AI_ROLE)
      
      # 아래와 같은 포맷으로 리턴되는데, 불필요한 문자 제거 후 json 파싱
      # ```json
      # 내용
      # ```
      try:
         # 마크다운 포맷 제거
         content = result.content.strip()
         if content.startswith("```json"):
            content = content[7:]  # "```json" 제거
         if content.endswith("```"):
            content = content[:-3]  # "```" 제거
         content = content.strip()
         
         # JSON 파싱
         json_data = json.loads(content)
         
         # 필드명 매핑 (LLM 응답의 한글 필드명을 영어 필드명으로 변환)
         field_mapping = {
            "질문주제": "주제",
            "답변수준": "answer_level",
            "종목코드": "종목코드",
            "종목명": "stock_name",
            "추가옵션": "additional_option"
         }
         
         # 매핑된 필드명으로 데이터 변환
         mapped_data = {}
         for k, v in json_data.items():
            if k in field_mapping:
               mapped_data[field_mapping[k]] = v
         
         # 문자열 레이블을 숫자 인덱스로 변환
         if "topic" in mapped_data and isinstance(mapped_data["topic"], str):
            # 유사한 문자열 처리 (공백, 대소문자 등 무시)
            topic_str = mapped_data["topic"].strip().lower()
            for label, idx in self.TOPIC_INDICES.items():
               if label.lower() in topic_str:
                  mapped_data["topic"] = idx
                  break
            else:
               # 일치하는 항목이 없으면 기본값 설정
               mapped_data["topic"] = 2  # 기타
         
         if "answer_level" in mapped_data and isinstance(mapped_data["answer_level"], str):
            # 여러 답변 수준이 포함된 경우 (예: "긴설명요구|종합판단")
            answer_level_str = mapped_data["answer_level"].strip().lower()
            
            # 가장 높은 수준의 답변 요구를 선택 (숫자가 클수록 복잡한 답변)
            max_level = 0
            for label, idx in self.ANSWER_LEVEL_INDICES.items():
               if label.lower() in answer_level_str:
                  max_level = max(max_level, idx)
            
            mapped_data["answer_level"] = max_level
         
         # Pydantic 모델로 변환하여 반환
         return QuestionClassification(**mapped_data)
      except json.JSONDecodeError as e:
         raise ValueError(f"LLM이 반환한 결과를 JSON으로 파싱할 수 없습니다: {str(e)}")
      except Exception as e:
         raise ValueError(f"질문 분류 중 오류가 발생했습니다: {str(e)}")
   
   def classify_question_with_structured_output(self, question: str) -> QuestionClassification:
      result = self.llm.generate_with_structured_output(question, self.AI_ROLE, QuestionClassification)
      return result

