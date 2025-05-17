from loguru import logger # loguru import 추가
from typing import List, Dict, Optional, Tuple
from uuid import UUID
#from sqlalchemy import UUID
from .base import BaseRetriever, RetrieverConfig
from .models import DocumentWithScore, RetrievalResult

from common.services.vector_store_manager import VectorStoreManager
from common.core.config import settings

# logger = logging.getLogger(__name__) # 삭제

class SemanticRetrieverConfig(RetrieverConfig):
    """시맨틱 검색 설정"""
    model_config = {"arbitrary_types_allowed": True}
    min_score: float = 0.6  # 최소 유사도 점수
    search_multiplier: int = 1  # top_k에 곱할 배수
    project_type: Optional[str] = None
    user_id: Optional[UUID] = None
    

class SemanticRetriever(BaseRetriever):
    """시맨틱 검색 구현체"""
    
    def __init__(self, config: SemanticRetrieverConfig, vs_manager: VectorStoreManager):
        super().__init__(config)
        self.config = config
        self.vs_manager = vs_manager
        logger.info(f"[SemanticRetriever][init] user:{config.user_id}, project_type:{config.project_type}")
        self.vs_manager.user_id = config.user_id
        self.vs_manager.project_type = config.project_type
    
    async def aclose(self):
        await self.vs_manager.close()

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
            
            # VectorStoreManager 사용
            search_results = await self.vs_manager.search_async(
                query=query,
                #top_k=_top_k * self.config.search_multiplier,  # 더 많은 결과를 가져와서 필터링
                top_k = _top_k,
                filters=filters
            )

            #search_results = [(Document, score), (Document, score), ...]
            # Document.metadata는 저장할때 넣었던 metadata와 같은 구조다.
            
            if not search_results:
                logger.warning("검색 결과가 없습니다.")
                return RetrievalResult(documents=[])
            #logger.info(f"검색된 총 매치 수: {len(search_results)}")
            
            # 상위 K개만 선택하고 Document 객체만 추출
            actual_top_k = min(len(search_results), _top_k)
            filtered_results = search_results[:actual_top_k]
            
            # Document 객체에 score 정보를 포함시킴
            documents = []
            score_list = []
            for i, (doc, score) in enumerate(filtered_results):
                # 기존 Document 객체의 속성을 복사하여 새로운 Document 생성
                if i < 3:
                    if settings.ENV == "development":
                        logger.info(f"[{i}] score: {score}, min_score: {self.config.min_score}")
                        cont = doc.page_content[:100]
                        cont = cont.replace("\n\n", "\n")
                        #logger.info(f"doc: {doc.page_content[:100].strip()}")
                    score_list.append(score)
                if score >= self.config.min_score:
                    new_doc = DocumentWithScore(
                        page_content=doc.page_content,
                        metadata=doc.metadata.copy(),  # metadata는 깊은 복사
                        score=score  # score 추가
                        )
                    documents.append(new_doc)

            logger.info(f"검색된 총 매치 수: {len(search_results)}, 최소 점수: {self.config.min_score}, 검색된 수: {len(documents)}")
            logger.info(f"score_list: {score_list}")
            
            # 쿼리 분석 정보 추가
            query_analysis = {
                "type": "semantic",
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
        
    async def add_documents(self, documents: List[DocumentWithScore]) -> bool:
        """문서를 벡터 스토어에 추가"""
        # TODO: 문서 임베딩 및 저장 구현
        return True
        
    async def delete_documents(self, document_ids: List[str]) -> bool:
        """벡터 스토어에서 문서 삭제"""
        # TODO: 문서 삭제 구현
        return True
        
    async def update_documents(self, documents: List[DocumentWithScore]) -> bool:
        """벡터 스토어의 문서 업데이트"""
        # TODO: 문서 업데이트 구현
        return True 