from typing import List, Dict, Optional
from uuid import UUID
import numpy as np
from rank_bm25 import BM25Okapi
from langchain_community.retrievers import BM25Retriever as LangchainBM25Retriever

from transformers import AutoTokenizer, AutoModel
from common.services.embedding_models import EmbeddingModelType
from common.core.config import settings
from sklearn.metrics.pairwise import cosine_similarity
from loguru import logger

from doceasy.services.document import AsyncDocumentDatabaseManager
from common.services.embedding import EmbeddingService
from .base import BaseRetriever, RetrieverConfig
from .models import DocumentWithScore, RetrievalResult
from pydantic import BaseModel, Field, model_validator, field_validator

class ContextualBM25Config(RetrieverConfig):
    """Contextual BM25 검색 설정"""
    min_score: float = Field(default=0.1, description="최소 점수")
    bm25_weight: float = Field(default=0.6, description="BM25 점수 가중치")
    context_weight: float = Field(default=0.4, description="문맥 점수 가중치")
    context_window_size: int = Field(default=3, description="문맥 윈도우 크기")
    model_name: str = Field(
        #default="jhgan/ko-sroberta-multitask",
        default=EmbeddingModelType.BGE_M3, # dragonkue/bge-m3-ko
        description="문맥 임베딩 모델"
    )
    project_type: Optional[str] = None
    user_id: Optional[UUID] = None


    @field_validator('bm25_weight', 'context_weight')
    @classmethod
    def validate_weights(cls, v: float, info) -> float:
        if not 0 <= v <= 1:
            raise ValueError(f"가중치는 0과 1 사이의 값이어야 합니다. 현재 값: {v}")
        return v

    @model_validator(mode='after')
    def validate_weight_sum(self) -> 'ContextualBM25Config':
        bm25_weight = self.bm25_weight
        context_weight = self.context_weight
        if abs(bm25_weight + context_weight - 1.0) > 1e-6:
            raise ValueError(f"가중치의 합은 1이어야 합니다. 현재 합: {bm25_weight + context_weight}")
        return self

class ContextualBM25Retriever(BaseRetriever):
    """Contextual BM25 검색 구현체"""
    
    def __init__(self, config: ContextualBM25Config, db=None):
        super().__init__(config)
        self.config = config
        self.db = db
        self.documents = []
        self.document_embeddings = None
        self.embedding_cache = {}
        self.bm25 = None  # BM25Okapi 인스턴스
        
        # 문맥 임베딩을 위한 모델 초기화
        logger.info(f"문맥 임베딩 모델 초기화: {config.model_name}")
        model_name = config.model_name.value if hasattr(config.model_name, 'value') else config.model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        self.embedding_service = EmbeddingService(EmbeddingModelType.OPENAI_3_LARGE)
        
    def _tokenize_text(self, text: str) -> List[str]:
        """DeBERTa 토크나이저를 사용하여 텍스트 토큰화"""
        tokens = self.tokenizer.tokenize(text)
        return tokens

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """텍스트 리스트의 임베딩 생성"""

        
        embeddings = self.embedding_service.create_embeddings_batch_sync(texts, user_id=self.config.user_id, project_type=self.config.project_type)
        
        
        return embeddings
        
    async def add_documents(self, documents: List[DocumentWithScore]) -> bool:
        """문서를 검색 인덱스에 추가"""
        try:
            logger.info(f"Contextual BM25 인덱스 생성 시작: {len(documents)} 청크")
            self.documents = documents

            # 문서 텍스트 토큰화
            tokenized_corpus = [
                self.tokenizer.tokenize(doc.page_content)
                for doc in documents
            ]
            
            # BM25 인덱스 생성
            self.bm25 = BM25Okapi(tokenized_corpus)
                
            # 문맥 임베딩 생성
            self.document_embeddings = self._get_embeddings([doc.page_content for doc in documents])
            
            return True
            
        except Exception as e:
            logger.error(f"Contextual BM25 인덱스 생성 중 오류: {str(e)}")
            return False
        
    async def make_document_from_chunk_table(self, filters: Dict) -> List[DocumentWithScore]:
        """Documentchunk Table에서 문서를 읽어와서 추가"""
        try:
            if not self.db:
                raise ValueError("[ContextualBM25Retriever] Database session is not initialized")
            db_manager = AsyncDocumentDatabaseManager(self.db)
            document_ids = filters.get("document_ids", [])  # List[str]
            documents = []
            for doc_id in document_ids:
                chunks = await db_manager.get_document_chunks(doc_id)


                # 각 청크를 Document 형식으로 변환
                converted_docs = [
                    DocumentWithScore(
                        page_content=chunk.chunk_content,
                        metadata={
                            "document_id": str(chunk.document_id),
                            "chunk_index": chunk.chunk_index,
                            "metadata": chunk.chunk_metadata
                        },
                        score=0.0  # score 필드 추가
                    ) for chunk in chunks
                ]
                documents.extend(converted_docs)
            
            return documents
        except Exception as e:
            logger.error(f"Contextual BM25 - make_document_from_chunk_table 생성 중 오류: {str(e)}", exc_info=True)
            return []
            
    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict] = None
    ) -> RetrievalResult:
        """Contextual BM25 검색 수행"""
        try:
            if self.db:
                documents = await self.make_document_from_chunk_table(filters)
                await self.add_documents(documents)

            if not self.bm25 or not self.document_embeddings:
                logger.warning("검색 인덱스가 초기화되지 않았습니다.")
                return RetrievalResult(documents=[])
                
            _top_k = top_k or self.config.top_k
            logger.info(f"검색 시작 - 쿼리: {query}, top_k: {_top_k}")
            
            # BM25 검색 수행
            tokenized_query = self.tokenizer.tokenize(query)
            bm25_scores = self.bm25.get_scores(tokenized_query)
            
            # BM25 점수 정규화
            bm25_scores = (bm25_scores - bm25_scores.min()) / (bm25_scores.max() - bm25_scores.min() + 1e-6)
            
            # 문맥 유사도 계산 및 정규화
            query_embedding = self._get_embeddings([query])[0]
            context_scores = cosine_similarity([query_embedding], self.document_embeddings)[0]
            context_scores = (context_scores - context_scores.min()) / (context_scores.max() - context_scores.min() + 1e-6)
            
            # 점수 결합 및 상위 K개 문서 선택
            final_scores = []
            result_documents = []
            
            for idx, (doc, bm25_score, context_score) in enumerate(zip(self.documents, bm25_scores, context_scores)):
                # 정규화된 점수로 최종 점수 계산
                final_score = (
                    self.config.bm25_weight * bm25_score +
                    self.config.context_weight * context_score
                )
                
                logger.debug(f"문서 {idx} 점수 - BM25: {bm25_score:.3f}, 문맥: {context_score:.3f}, 최종: {final_score:.3f}")
                
                if final_score >= self.config.min_score:
                    new_doc = DocumentWithScore(
                        page_content=doc.page_content,
                        metadata={
                            **doc.metadata,
                            "bm25_score": float(bm25_score),
                            "context_score": float(context_score),
                            "normalized_score": float(final_score)
                        },
                        score=float(final_score)
                    )
                    result_documents.append(new_doc)
                    final_scores.append(final_score)
            
            # top_k 적용 (점수 기준 내림차순 정렬)
            if result_documents:
                sorted_indices = np.argsort(final_scores)[::-1]
                result_documents = [result_documents[i] for i in sorted_indices[:_top_k]]
            
            logger.info(f"검색 완료 - 결과: {len(result_documents)} 문서")
            
            return RetrievalResult(
                documents=result_documents,
                query_analysis={
                    "type": "contextual_bm25",
                    "min_score": self.config.min_score,
                    "bm25_weight": self.config.bm25_weight,
                    "context_weight": self.config.context_weight,
                    "total_found": len(self.documents),
                    "returned": len(result_documents)
                }
            )
            
        except Exception as e:
            logger.error(f"Contextual BM25 검색 중 오류 발생: {str(e)}")
            raise
            
    async def delete_documents(self, document_ids: List[str]) -> bool:
        """검색 인덱스에서 문서 삭제"""
        try:
            self.documents = [
                doc for doc in self.documents
                if doc.metadata.get("document_id") not in document_ids
            ]
            return await self.add_documents(self.documents)
        except Exception as e:
            logger.error(f"문서 삭제 중 오류 발생: {str(e)}")
            return False
            
    async def update_documents(self, documents: List[DocumentWithScore]) -> bool:
        """검색 인덱스의 문서 업데이트"""
        try:
            update_ids = [
                doc.metadata.get("document_id")
                for doc in documents
                if "document_id" in doc.metadata
            ]
            
            existing_docs = [
                doc for doc in self.documents
                if doc.metadata.get("document_id") not in update_ids
            ]
            
            all_documents = existing_docs + documents
            return await self.add_documents(all_documents)
            
        except Exception as e:
            logger.error(f"문서 업데이트 중 오류 발생: {str(e)}")
            return False 