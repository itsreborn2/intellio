from typing import List, Dict, Optional
from uuid import UUID
from .base import BaseRetriever, RetrieverConfig
from .models import DocumentWithScore, RetrievalResult
from .semantic import SemanticRetriever, SemanticRetrieverConfig
from .contextual_bm25 import ContextualBM25Retriever, ContextualBM25Config
from pydantic import BaseModel, Field
import asyncio
from loguru import logger
from common.services.vector_store_manager import VectorStoreManager
from langchain_community.retrievers import BM25Retriever as LangchainBM25Retriever
from ..reranker import Reranker, RerankerConfig, RerankerType, PineconeRerankerConfig
from common.core.config import settings

class HybridRetrieverConfig(RetrieverConfig):
    """하이브리드 검색 설정"""
    semantic_config: SemanticRetrieverConfig = Field(..., description="시맨틱 검색 설정")
    contextual_bm25_config: ContextualBM25Config = Field(..., description="Contextual BM25 검색 설정")
    contextual_bm25_weight: float = Field(default=0.4, description="Contextual BM25 검색 결과의 가중치")
    semantic_weight: float = Field(default=0.6, description="벡터-BM25 순차 검색에서 벡터 검색 결과의 가중치")
    vector_multiplier: int = Field(default=10, description="벡터-BM25 순차 검색에서 벡터 검색 결과 수에 곱할 배수")
    project_type: Optional[str] = None
    user_id: Optional[UUID] = None

class HybridRetriever(BaseRetriever):
    """시맨틱 검색과 Contextual BM25를 결합한 하이브리드 검색 구현체"""
    
    def __init__(self, config: HybridRetrieverConfig, vs_manager: VectorStoreManager):
        super().__init__(config)
        self.config = config
        self.semantic_retriever = SemanticRetriever(
            config=self.config.semantic_config,
            vs_manager=vs_manager
        )
        self.contextual_bm25_retriever = ContextualBM25Retriever(
            config=self.config.contextual_bm25_config
        )
        
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
    
    async def retrieve_vector_then_bm25(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict] = None
    ) -> RetrievalResult:
        """벡터 검색 후 BM25 재랭킹 수행"""
        try:
            logger.info(f"벡터-BM25 순차 검색 시작 - 쿼리: {query}")
            _top_k = top_k or self.config.top_k
            
            # 1. 벡터 검색으로 후보군 확보 (더 많은 결과)
            vector_top_k = _top_k * self.config.vector_multiplier
            logger.info(f"벡터 검색 요청 - top_k: {_top_k}, vector_top_k: {vector_top_k}")
            vector_results = await self.semantic_retriever.retrieve(
                query=query, 
                top_k=vector_top_k, 
                filters=filters
            )
            
            if not vector_results.documents:
                logger.warning("벡터 검색 결과가 없습니다.")
                return RetrievalResult(documents=[])
            
            logger.info(f"벡터 검색 결과: {len(vector_results.documents)} 문서 (요청: {vector_top_k})")
            if len(vector_results.documents) < vector_top_k:
                logger.warning(f"벡터 검색 결과가 요청한 수({vector_top_k})보다 적습니다: {len(vector_results.documents)}")
            
            # 2. 벡터 검색 결과로 Contextual BM25 검색 수행
            # temp_bm25 = ContextualBM25Retriever(
            #     config=self.config.contextual_bm25_config
            # )
            await self.contextual_bm25_retriever.add_documents(vector_results.documents)
            #await self.contextual_bm25_retriever.add_documents_llama(vector_results.documents)
            bm25_results = await self.contextual_bm25_retriever.retrieve(query, top_k=_top_k)
            
            # 3. 결과 변환 및 점수 계산
            result_documents = []
            for doc in bm25_results.documents:
                # 원래 벡터 점수 찾기
                orig_idx = next(
                    (i for i, vdoc in enumerate(vector_results.documents)
                     if vdoc.page_content == doc.page_content),
                    None
                )
                
                if orig_idx is not None:
                    vector_score = vector_results.documents[orig_idx].score
                    bm25_score = doc.score
                    
                    # 결합 점수
                    combined_score = (
                        self.config.semantic_weight * vector_score +
                        self.config.contextual_bm25_weight * bm25_score
                    )
                    
                    # 메타데이터에 각 점수 추가
                    metadata = doc.metadata.copy()
                    metadata.update({
                        "vector_score": float(vector_score),
                        "bm25_score": float(bm25_score),
                        "contextual_score": float(doc.metadata.get("context_score", 0.0))
                    })
                    
                    result_documents.append(DocumentWithScore(
                        page_content=doc.page_content,
                        metadata=metadata,
                        score=float(combined_score)
                    ))
            
            # 쿼리 분석 정보 추가
            query_analysis = {
                "type": "vector_then_contextual_bm25",
                "vector_top_k": vector_top_k,
                "final_top_k": _top_k,
                "vector_weight": self.config.semantic_weight,
                "keyword_weight": self.config.contextual_bm25_weight,
                "total_vector_results": len(vector_results.documents),
                "total_bm25_results": len(bm25_results.documents),
                "returned": len(result_documents),
                "bm25_analysis": bm25_results.query_analysis
            }
            
            logger.info(f"벡터-Contextual BM25 순차 검색 완료 - 결과: {len(result_documents)} 문서")
            
            return RetrievalResult(
                documents=result_documents,
                query_analysis=query_analysis
            )
            
        except Exception as e:
            logger.error(f"벡터-Contextual BM25 순차 검색 중 오류 발생: {str(e)}")
            raise
    
    async def retrieve_vector_then_rerank(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict] = None
    ) -> RetrievalResult:
        """벡터 검색 후 리랭킹(Cross-Encoder) 수행"""
        _top_k = top_k or self.config.top_k
        
        # 1. 벡터 검색으로 후보군 확보 (더 많은 결과)
        vector_top_k = _top_k * self.config.vector_multiplier
        logger.info(f"벡터 검색 요청 - 쿼리: {query}, top_k: {_top_k}, vector_top_k: {vector_top_k}")
        vector_results = await self.semantic_retriever.retrieve(
            query=query, 
            top_k=vector_top_k, 
            filters=filters
        )
        
        if not vector_results.documents:
            logger.warning("벡터 검색 결과가 없습니다.")
            return RetrievalResult(documents=[])
        
        logger.info(f"벡터 검색 결과: {len(vector_results.documents)} 문서")
        
        # 2. 리랭킹 수행
        async with Reranker(
            RerankerConfig(
                reranker_type=RerankerType.PINECONE,
                pinecone_config=PineconeRerankerConfig(
                    api_key=settings.PINECONE_API_KEY_STOCKEASY,
                    min_score=0.1  # 낮은 임계값으로 더 많은 결과 포함
                )
            )
        ) as reranker:
            reranked_results = await reranker.rerank(
                query=query,
                documents=vector_results.documents,
                top_k=_top_k
            )
        
        logger.info(f"리랭킹 완료 - 결과: {len(reranked_results.documents)} 문서")
        
        # 결과에 리랭킹 정보 추가
        reranked_results.query_analysis.update({
            "type": "vector_then_rerank",
            "vector_search_count": len(vector_results.documents)
        })
        
        return reranked_results
    
    def _merge_results(
        self,
        semantic_docs: List[DocumentWithScore],
        contextual_docs: List[DocumentWithScore],
        top_k: int
    ) -> List[DocumentWithScore]:
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
            
            new_doc = DocumentWithScore(
                page_content=doc.page_content,
                metadata=metadata,
                score=item["score"]
            )
            result_docs.append(new_doc)
            
        return result_docs
        
    async def add_documents(self, documents: List[DocumentWithScore]) -> bool:
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
            
    async def update_documents(self, documents: List[DocumentWithScore]) -> bool:
        """문서를 양쪽 검색기에서 업데이트"""
        try:
            semantic_success = await self.semantic_retriever.update_documents(documents)
            contextual_success = await self.contextual_bm25_retriever.update_documents(documents)
            return semantic_success and contextual_success
        except Exception as e:
            logger.error(f"문서 업데이트 중 오류 발생: {str(e)}")
            return False 