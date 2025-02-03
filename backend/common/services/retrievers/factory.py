from enum import Enum
from typing import Dict, Type
from .base import BaseRetriever, RetrieverConfig

class RetrieverType(str, Enum):
    """지원하는 Retriever 타입"""
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"
    MULTIMODAL = "multimodal"

class RetrieverFactory:
    """Retriever 인스턴스를 생성하는 팩토리 클래스"""
    
    _retrievers: Dict[RetrieverType, Type[BaseRetriever]] = {}
    
    @classmethod
    def register(cls, retriever_type: RetrieverType, retriever_class: Type[BaseRetriever]):
        """새로운 Retriever 클래스 등록

        Args:
            retriever_type: Retriever 타입
            retriever_class: 등록할 Retriever 클래스
        """
        cls._retrievers[retriever_type] = retriever_class
    
    @classmethod
    def create(cls, retriever_type: RetrieverType, config: RetrieverConfig) -> BaseRetriever:
        """Retriever 인스턴스 생성

        Args:
            retriever_type: 생성할 Retriever 타입
            config: Retriever 설정

        Returns:
            BaseRetriever: 생성된 Retriever 인스턴스

        Raises:
            ValueError: 지원하지 않는 Retriever 타입
        """
        if retriever_type not in cls._retrievers:
            raise ValueError(f"지원하지 않는 Retriever 타입: {retriever_type}")
            
        retriever_class = cls._retrievers[retriever_type]
        return retriever_class(config) 