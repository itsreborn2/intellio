from typing import List, Dict, Optional
from .base import BaseRetriever, RetrieverConfig
from .models import Document, RetrievalResult
from .semantic import SemanticRetriever, SemanticRetrieverConfig
from .keyword import KeywordRetriever, KeywordRetrieverConfig
from pydantic import BaseModel
import asyncio

class HybridRetrieverConfig(RetrieverConfig):
    """하이브리드 검색 설정"""
    semantic_config: SemanticRetrieverConfig
    keyword_config: KeywordRetrieverConfig
    semantic_weight: float = 0.7  # 시맨틱 검색 결과의 가중치
    keyword_weight: float = 0.3   # 키워드 검색 결과의 가중치
    merge_strategy: str = "weighted_sum"  # 결과 병합 전략

class HybridRetriever(BaseRetriever):
    """시맨틱 검색과 키워드 검색을 결합한 하이브리드 검색 구현체"""
    
    def __init__(self, config: HybridRetrieverConfig):
        super().__init__(config)
        self.config = config
        self.semantic_retriever = SemanticRetriever(config.semantic_config)
        self.keyword_retriever = KeywordRetriever(config.keyword_config)
        
    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict] = None
    ) -> RetrievalResult:
        """하이브리드 검색 수행"""
        # 병렬로 시맨틱 검색과 키워드 검색 실행
        semantic_result, keyword_result = await asyncio.gather(
            self.semantic_retriever.retrieve(query, top_k, filters),
            self.keyword_retriever.retrieve(query, top_k, filters)
        )
        
        # 결과 병합
        merged_documents = self._merge_results(
            semantic_result.documents,
            keyword_result.documents,
            top_k or self.config.top_k
        )
        
        # 쿼리 분석 결과 통합
        query_analysis = {
            "type": "hybrid",
            "semantic_analysis": semantic_result.query_analysis,
            "keyword_analysis": keyword_result.query_analysis
        }
        
        return RetrievalResult(
            documents=merged_documents,
            query_analysis=query_analysis
        )
    
    def _merge_results(
        self,
        semantic_docs: List[Document],
        keyword_docs: List[Document],
        top_k: int
    ) -> List[Document]:
        """검색 결과 병합"""
        # 문서 ID를 키로 사용하여 결과 병합
        merged_docs = {}
        
        # 시맨틱 검색 결과 처리
        for doc in semantic_docs:
            doc_id = doc.metadata.get("document_id")
            if doc_id:
                merged_docs[doc_id] = {
                    "doc": doc,
                    "score": (doc.score or 0) * self.config.semantic_weight
                }
        
        # 키워드 검색 결과 처리
        for doc in keyword_docs:
            doc_id = doc.metadata.get("document_id")
            if doc_id:
                if doc_id in merged_docs:
                    # 이미 존재하는 문서의 경우 점수 결합
                    merged_docs[doc_id]["score"] += (doc.score or 0) * self.config.keyword_weight
                else:
                    merged_docs[doc_id] = {
                        "doc": doc,
                        "score": (doc.score or 0) * self.config.keyword_weight
                    }
        
        # 점수 기준으로 정렬하고 상위 K개 선택
        sorted_docs = sorted(
            merged_docs.values(),
            key=lambda x: x["score"],
            reverse=True
        )[:top_k]
        
        # 최종 문서 리스트 생성
        result_docs = []
        for item in sorted_docs:
            doc = item["doc"]
            doc.score = item["score"]  # 병합된 점수로 업데이트
            result_docs.append(doc)
            
        return result_docs
        
    async def add_documents(self, documents: List[Document]) -> bool:
        """두 검색 엔진에 모두 문서 추가"""
        results = await asyncio.gather(
            self.semantic_retriever.add_documents(documents),
            self.keyword_retriever.add_documents(documents)
        )
        return all(results)
        
    async def delete_documents(self, document_ids: List[str]) -> bool:
        """두 검색 엔진에서 모두 문서 삭제"""
        results = await asyncio.gather(
            self.semantic_retriever.delete_documents(document_ids),
            self.keyword_retriever.delete_documents(document_ids)
        )
        return all(results)
        
    async def update_documents(self, documents: List[Document]) -> bool:
        """두 검색 엔진에서 모두 문서 업데이트"""
        results = await asyncio.gather(
            self.semantic_retriever.update_documents(documents),
            self.keyword_retriever.update_documents(documents)
        )
        return all(results) 