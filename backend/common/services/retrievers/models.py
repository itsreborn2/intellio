from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from langchain_core.documents import Document as LangchainDocument

# LangchainDocument가 같은 구조를 가진다. 
class DocumentWithScore(LangchainDocument):
    """검색된 문서를 나타내는 기본 모델"""
    #content: str = Field(..., description="문서의 실제 내용")
#    metadata: Dict = Field(default_factory=dict, description="문서의 메타데이터 (ID, 제목, 페이지 번호 등)")
#     score: Optional[float] = Field(None, description="검색 결과의 관련성 점수")
    score: float = Field(..., description="검색 결과의 관련성 점수")

class RetrievalResult(BaseModel):
    """검색 결과를 나타내는 모델"""
    documents: List[DocumentWithScore] = Field(..., description="검색된 문서 목록")
    query_analysis: Optional[Dict] = Field(None, description="쿼리 분석 결과")
    metadata: Dict = Field(default_factory=dict, description="검색 결과에 대한 추가 메타데이터") 