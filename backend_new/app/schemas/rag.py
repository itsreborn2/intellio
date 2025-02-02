from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

class RAGQuery(BaseModel):
    """RAG 쿼리 스키마"""
    query: str
    mode: str = "chat"  # "chat" 또는 "table"
    document_ids: Optional[List[UUID]] = None
    user_id: Optional[str] = None
    project_id: Optional[str] = None

class RAGResponse(BaseModel):
    """RAG 응답 스키마"""
    answer: str
    context: List[dict] 