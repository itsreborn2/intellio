from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class RAGEvaluationExample(BaseModel):
    """RAG 평가 예제 모델"""
    query: str
    ground_truth: str
    retrieved_documents: List[str]
    retrieved_documents_raw: Optional[List[Any]] = None  # 원본 문서 객체를 저장하기 위한 필드
    expected_sources: Optional[List[str]] = None
    generated_response: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None 