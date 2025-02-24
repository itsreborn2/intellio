from typing import List, Dict, Optional
from .base import BaseRetriever, RetrieverConfig
from .models import Document, RetrievalResult
from .semantic import SemanticRetriever, SemanticRetrieverConfig
from .contextual_bm25 import ContextualBM25Retriever, ContextualBM25Config
from pydantic import BaseModel, Field
import asyncio
from loguru import logger
from common.services.vector_store_manager import VectorStoreManager

class HybridRetrieverConfig(RetrieverConfig):
    """하이브리드 검색 설정"""
    semantic_config: SemanticRetrieverConfig = Field(..., description="시맨틱 검색 설정")
    contextual_bm25_config: ContextualBM25Config = Field(..., description="Contextual BM25 검색 설정")
    semantic_weight: float = Field(default=0.6, description="시맨틱 검색 결과의 가중치")
    contextual_bm25_weight: float = Field(default=0.4, description="Contextual BM25 검색 결과의 가중치")

class HybridRetriever(BaseRetriever):
    """시맨틱 검색과 Contextual BM25를 결합한 하이브리드 검색 구현체"""
    
    def __init__(self, config: HybridRetrieverConfig, vs_manager: VectorStoreManager):
        super().__init__(config)
        self.config = config
        self.semantic_retriever = SemanticRetriever(config.semantic_config, vs_manager=vs_manager)
        self.contextual_bm25_retriever = ContextualBM25Retriever(config.contextual_bm25_config)
        
    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict] = None
    ) -> RetrievalResult:
        """하이브리드 검색 수행"""
        try:
            logger.info(f"하이브리드 검색 시작 - 쿼리: {query}")
            
            # 병렬로 시맨틱 검색과 Contextual BM25 검색 실행
            semantic_result, contextual_result = await asyncio.gather(
                self.semantic_retriever.retrieve(query, top_k, filters),
                self.contextual_bm25_retriever.retrieve(query, top_k, filters)
            )
            
            # 결과 병합
            merged_documents = self._merge_results(
                semantic_result.documents,
                contextual_result.documents,
                top_k or self.config.top_k
            )
            
            # 쿼리 분석 결과 통합
            query_analysis = {
                "type": "hybrid_contextual",
                "semantic_analysis": semantic_result.query_analysis,
                "contextual_bm25_analysis": contextual_result.query_analysis,
                "semantic_weight": self.config.semantic_weight,
                "contextual_bm25_weight": self.config.contextual_bm25_weight
            }
            
            logger.info(f"하이브리드 검색 완료 - 결과: {len(merged_documents)} 문서")
            
            return RetrievalResult(
                documents=merged_documents,
                query_analysis=query_analysis
            )
            
        except Exception as e:
            logger.error(f"하이브리드 검색 중 오류 발생: {str(e)}")
            raise
    
    def _merge_results(
        self,
        semantic_docs: List[Document],
        contextual_docs: List[Document],
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
                    "score": (doc.score or 0) * self.config.semantic_weight,
                    "semantic_score": doc.score
                }
        
        # Contextual BM25 검색 결과 처리
        for doc in contextual_docs:
            doc_id = doc.metadata.get("document_id")
            if doc_id:
                if doc_id in merged_docs:
                    # 이미 존재하는 문서의 경우 점수 결합
                    merged_docs[doc_id]["score"] += (doc.score or 0) * self.config.contextual_bm25_weight
                    merged_docs[doc_id]["contextual_score"] = doc.score
                else:
                    merged_docs[doc_id] = {
                        "doc": doc,
                        "score": (doc.score or 0) * self.config.contextual_bm25_weight,
                        "contextual_score": doc.score
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
            # 원본 메타데이터 복사
            metadata = doc.metadata.copy()
            # 각 검색 방식의 점수 추가
            metadata.update({
                "semantic_score": item.get("semantic_score"),
                "contextual_score": item.get("contextual_score"),
                "combined_score": item["score"]
            })
            
            new_doc = Document(
                page_content=doc.page_content,
                metadata=metadata,
                score=item["score"]
            )
            result_docs.append(new_doc)
            
        return result_docs
        
    async def add_documents(self, documents: List[Document]) -> bool:
        """문서를 양쪽 검색기에 추가"""
        try:
            semantic_success = await self.semantic_retriever.add_documents(documents)
            contextual_success = await self.contextual_bm25_retriever.add_documents(documents)
            return semantic_success and contextual_success
        except Exception as e:
            logger.error(f"문서 추가 중 오류 발생: {str(e)}")
            return False
            
    async def delete_documents(self, document_ids: List[str]) -> bool:
        """문서를 양쪽 검색기에서 삭제"""
        try:
            semantic_success = await self.semantic_retriever.delete_documents(document_ids)
            contextual_success = await self.contextual_bm25_retriever.delete_documents(document_ids)
            return semantic_success and contextual_success
        except Exception as e:
            logger.error(f"문서 삭제 중 오류 발생: {str(e)}")
            return False
            
    async def update_documents(self, documents: List[Document]) -> bool:
        """문서를 양쪽 검색기에서 업데이트"""
        try:
            semantic_success = await self.semantic_retriever.update_documents(documents)
            contextual_success = await self.contextual_bm25_retriever.update_documents(documents)
            return semantic_success and contextual_success
        except Exception as e:
            logger.error(f"문서 업데이트 중 오류 발생: {str(e)}")
            return False 