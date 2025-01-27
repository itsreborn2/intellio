from typing import List, Dict, Optional, Tuple
from .base import BaseRetriever, RetrieverConfig
from .models import Document, RetrievalResult
from pydantic import BaseModel
from app.services.embedding import EmbeddingService
import logging
from uuid import UUID

logger = logging.getLogger(__name__)

class SemanticRetrieverConfig(RetrieverConfig):
    """시맨틱 검색 설정"""
    embedding_model: str
    min_score: float = 0.6  # 최소 유사도 점수
    search_multiplier: int = 3  # top_k에 곱할 배수

class SemanticRetriever(BaseRetriever):
    """시맨틱 검색 구현체"""
    
    def __init__(self, config: SemanticRetrieverConfig):
        super().__init__(config)
        self.config = config
        self.embedding_service = EmbeddingService()
        
    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict] = None
    ) -> RetrievalResult:
        """시맨틱 검색 수행"""
        try:
            # 기본값 설정
            _top_k = top_k or self.config.top_k
            document_ids = filters.get("document_ids") if filters else None
            
            # AI 삭제금지.
            # 검색 수행. 검색 결과는 점수 순으로 정렬되어 있음.
            # search_similar() 리턴값
            #  result = {
            #     "id": match.id,
            #     "score": match.score,
            #     "metadata": match.metadata => 이건 pineonce의 metadata임.
            # }
            # pinecone의 metadata
            #   "metadata": {
            # 	    "document_id": document_id,
            # 	    "chunk_index": batch_start_idx + i,
            # 	    "text": chunk
            #   }
            search_results = await self.embedding_service.search_similar(
                query=query,
                top_k=_top_k * self.config.search_multiplier,  # 더 많은 결과를 가져와서 필터링
                min_score=self.config.min_score,
                document_ids=document_ids
            )
            
            if not search_results:
                logger.warning("검색 결과가 없습니다.")
                return RetrievalResult(documents=[])
            
            # Document 객체로 변환
            documents = []
            for result in search_results:
                metadata = result["metadata"]
                documents.append(
                    Document(
                        content=metadata.get("text", ""),
                        metadata={
                            "document_id": metadata.get("document_id"),
                            "page_number": metadata.get("page_number", 0), #없음
                            "chunk_index": metadata.get("chunk_index"),
                            "source": metadata.get("source") # 없음.
                        },
                        score=result["score"]
                    )
                )
            
            # 상위 K개만 선택
            documents = documents[:_top_k]
            
            # 쿼리 분석 정보 추가
            query_analysis = {
                "type": "semantic",
                "model": self.config.embedding_model,
                "min_score": self.config.min_score,
                "total_found": len(search_results),
                "returned": len(documents)
            }
            
            return RetrievalResult(
                documents=documents,
                query_analysis=query_analysis
            )
            
        except Exception as e:
            logger.error(f"시맨틱 검색 중 오류 발생: {str(e)}")
            raise
        
    async def add_documents(self, documents: List[Document]) -> bool:
        """문서를 벡터 스토어에 추가"""
        # TODO: 문서 임베딩 및 저장 구현
        return True
        
    async def delete_documents(self, document_ids: List[str]) -> bool:
        """벡터 스토어에서 문서 삭제"""
        # TODO: 문서 삭제 구현
        return True
        
    async def update_documents(self, documents: List[Document]) -> bool:
        """벡터 스토어의 문서 업데이트"""
        # TODO: 문서 업데이트 구현
        return True 