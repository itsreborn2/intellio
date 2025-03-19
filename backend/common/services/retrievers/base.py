from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from .models import DocumentWithScore, RetrievalResult
from pydantic import BaseModel

class RetrieverConfig(BaseModel):
    """Retriever 설정을 위한 기본 모델"""
    top_k: int = 5
    score_threshold: Optional[float] = None
    filters: Dict[str, Any] = {}
    
class BaseRetriever(ABC):
    """Retriever의 기본 인터페이스"""
    
    def __init__(self, config: RetrieverConfig):
        self.config = config
    
    @abstractmethod
    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict] = None
    ) -> RetrievalResult:
        """주어진 쿼리에 대해 관련 문서를 검색

        Args:
            query: 검색 쿼리
            top_k: 반환할 최대 문서 수 (None이면 config의 값 사용)
            filters: 검색 필터 (None이면 config의 값 사용)

        Returns:
            RetrievalResult: 검색 결과
        """
        pass

    @abstractmethod
    async def add_documents(self, documents: List[DocumentWithScore]) -> bool:
        """문서를 검색 인덱스에 추가

        Args:
            documents: 추가할 문서 리스트

        Returns:
            bool: 성공 여부
        """
        pass

    @abstractmethod
    async def delete_documents(self, document_ids: List[str]) -> bool:
        """문서를 검색 인덱스에서 삭제

        Args:
            document_ids: 삭제할 문서 ID 리스트

        Returns:
            bool: 성공 여부
        """
        pass

    @abstractmethod
    async def update_documents(self, documents: List[DocumentWithScore]) -> bool:
        """문서를 검색 인덱스에서 업데이트

        Args:
            documents: 업데이트할 문서 리스트

        Returns:
            bool: 성공 여부
        """
        pass 