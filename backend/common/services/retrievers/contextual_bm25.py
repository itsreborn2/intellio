from typing import List, Dict, Optional
import numpy as np
from llama_index.retrievers.bm25 import BM25Retriever as LlamaBM25Retriever
from langchain_community.retrievers import BM25Retriever as LangchainBM25Retriever
from llama_index.core.schema import Document as LlamaDocument, NodeWithScore, BaseNode, TextNode
from transformers import AutoTokenizer, AutoModel
from common.core.config import settings
from sklearn.metrics.pairwise import cosine_similarity
from loguru import logger

from doceasy.services.document import AsyncDocumentDatabaseManager
from common.services.embedding import EmbeddingService
from .base import BaseRetriever, RetrieverConfig
from .models import Document, RetrievalResult
from pydantic import BaseModel, Field, model_validator, field_validator

class ContextualBM25Config(RetrieverConfig):
    """Contextual BM25 검색 설정"""
    min_score: float = Field(default=0.3, description="최소 점수")
    bm25_weight: float = Field(default=0.6, description="BM25 점수 가중치")
    context_weight: float = Field(default=0.4, description="문맥 점수 가중치")
    context_window_size: int = Field(default=3, description="문맥 윈도우 크기")
    model_name: str = Field(
        #default="jhgan/ko-sroberta-multitask",
        default=settings.KAKAO_EMBEDDING_MODEL_PATH,
        description="문맥 임베딩 모델"
    )

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
        
        # 문맥 임베딩을 위한 모델 초기화
        logger.info(f"문맥 임베딩 모델 초기화: {config.model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(config.model_name)
        self.model = AutoModel.from_pretrained(config.model_name)
        self.model.eval()
        
        # LlamaIndex BM25 초기화
        self.bm25_retriever = None
        
    def _tokenize_text(self, text: str) -> List[str]:
        """DeBERTa 토크나이저를 사용하여 텍스트 토큰화"""
        tokens = self.tokenizer.tokenize(text)
        return tokens

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """텍스트 리스트의 임베딩 생성"""

        embedding_service = EmbeddingService()
        embeddings = embedding_service.create_embeddings_batch_sync(texts)
        
        # for text in texts:
        #     cache_key = hash(text)
        #     if cache_key in self.embedding_cache:
        #         embeddings.append(self.embedding_cache[cache_key])
        #         continue
            
        #     with torch.no_grad():
        #         inputs = self.tokenizer(
        #             text,
        #             max_length=512,
        #             padding=True,
        #             truncation=True,
        #             return_tensors="pt"
        #         )
                
        #         outputs = self.model(**inputs)
        #         embedding = outputs.last_hidden_state[:, 0, :].numpy()
        #         embeddings.append(embedding[0])
        #         self.embedding_cache[cache_key] = embedding[0]
                
        #return np.array(embeddings)
        return embeddings
        
    async def add_documents_llama(self, documents: List[Document]) -> bool:
        """문서를 검색 인덱스에 추가"""
        try:
            logger.info(f"Contextual BM25 인덱스 생성 시작: {len(documents)} 청크")
            self.documents = documents
            
            llama_nodes = [
                TextNode(text=doc.page_content, metadata=doc.metadata)
                for doc in documents
            ]

            # BM25 인덱스 생성
            self.bm25_retriever = LlamaBM25Retriever.from_defaults(
                nodes=llama_nodes,
                language="kr",
                tokenizer_fn=lambda x: self.tokenizer.tokenize(x)  # DeBERTa 토크나이저 사용
            )
            # 문맥 임베딩 생성
            self.document_embeddings = self._get_embeddings([doc.page_content for doc in documents])
            
            return True
            
        except Exception as e:
            logger.error(f"Contextual BM25 인덱스 생성 중 오류: {str(e)}")
            return False
    async def add_documents(self, documents: List[Document]) -> bool:
        """문서를 검색 인덱스에 추가"""
        try:
            logger.info(f"Contextual BM25 인덱스 생성 시작: {len(documents)} 청크")
            self.documents = documents

            # BM25 인덱스 생성
            self.bm25_retriever = LangchainBM25Retriever.from_documents(documents)
                
            # 문맥 임베딩 생성
            self.document_embeddings = self._get_embeddings([doc.page_content for doc in documents])
            
            return True
            
        except Exception as e:
            logger.error(f"Contextual BM25 인덱스 생성 중 오류: {str(e)}")
            return False
        
    async def make_document_from_chunk_table(self, filters: Dict) -> List[Document]:
        """Documentchunk Table에서 문서를 읽어와서 추가"""
        try:
            if not self.db:
                raise ValueError("[ContextualBM25Retriever] Database session is not initialized")
            db_manager = AsyncDocumentDatabaseManager(self.db)
            document_ids = filters.get("document_ids", [])  # List[str]
            documents = []
            for doc_id in document_ids:
                chunks = await db_manager.get_document_chunks(doc_id)

                # id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
                # document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
                # chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
                # chunk_content: Mapped[str] = mapped_column(Text, nullable=False)
                # chunk_metadata: Mapped[str | None] = mapped_column(String)  # JSON string
                # embedding: Mapped[str | None] = mapped_column(String)

                # 각 청크를 Document 형식으로 변환
                converted_docs = [
                    Document(
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
            # 여기 Documentchunk Table을 읽어와서 Document 형식으로 변환
            # add_documents() 함수에 전달
            # 문서 추가
            documents = await self.make_document_from_chunk_table(filters)
            await self.add_documents(documents)

            if not self.bm25_retriever or not self.document_embeddings:
                logger.warning("검색 인덱스가 초기화되지 않았습니다.")
                return RetrievalResult(documents=[])
                
            _top_k = top_k or self.config.top_k
            logger.info(f"검색 시작 - 쿼리: {query}, top_k: {_top_k}")
            
            # BM25 검색 수행 (Langchain)
            bm25_results = self.bm25_retriever.invoke(query)
            
            logger.info(f"BM25 검색 결과 : {len(bm25_results)} 청크")
            # BM25 점수 계산 (Langchain은 기본적으로 점수를 제공하지 않으므로, 순서에 따른 정규화된 점수 부여)
            num_results = len(bm25_results)
            if num_results == 0:
                return RetrievalResult(documents=[])
                
            bm25_scores = np.linspace(1.0, 0.1, num_results)  # 선형적으로 감소하는 점수 부여
            
            # 문맥 유사도 계산
            query_embedding = self._get_embeddings([query])[0]
            context_scores = cosine_similarity([query_embedding], self.document_embeddings)[0]
            
            # 점수 결합 및 상위 K개 문서 선택
            final_scores = []
            result_documents = []
            
            for idx, (doc, bm25_score) in enumerate(zip(bm25_results, bm25_scores)):
                # 원본 문서에서 해당 문서의 인덱스 찾기
                doc_idx = next(
                    (i for i, orig_doc in enumerate(self.documents) 
                     if orig_doc.page_content == doc.page_content),
                    None
                )
                
                if doc_idx is not None:
                    context_score = context_scores[doc_idx]
                    final_score = (
                        self.config.bm25_weight * bm25_score +
                        self.config.context_weight * context_score
                    )
                    
                    if final_score >= self.config.min_score:
                        new_doc = Document(
                            page_content=doc.page_content,
                            metadata={
                                **doc.metadata,
                                "bm25_score": float(bm25_score),
                                "context_score": float(context_score)
                            },
                            score=float(final_score)
                        )
                        result_documents.append(new_doc)
                        final_scores.append(final_score)
            
            # top_k 적용
            if _top_k and len(result_documents) > _top_k:
                top_indices = np.argsort(final_scores)[-_top_k:][::-1]
                result_documents = [result_documents[i] for i in top_indices]
            
            logger.info(f"검색 완료 - 결과: {len(result_documents)} 문서")
            
            return RetrievalResult(
                documents=result_documents,
                query_analysis={
                    "type": "contextual_bm25",
                    "min_score": self.config.min_score,
                    "bm25_weight": self.config.bm25_weight,
                    "context_weight": self.config.context_weight,
                    "total_found": len(bm25_results),
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
            
    async def update_documents(self, documents: List[Document]) -> bool:
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