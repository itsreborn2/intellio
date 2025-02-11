from typing import List, Dict, Optional, Tuple
import logging
from loguru import logger
from .base import BaseRetriever, RetrieverConfig
from .models import Document, RetrievalResult

from common.services.vector_store_manager import VectorStoreManager
from common.core.config import settings
from .semantic import SemanticRetriever, SemanticRetrieverConfig

import pinecone

#logger = logging.getLogger(__name__)

class TableModeSemanticRetriever(SemanticRetriever):
    """테이블 모드 시맨틱 검색 구현체
    
    부모 클래스인 SemanticRetriever의 검색 결과를 받아서 테이블 모드에 맞게 처리합니다.
    """
    
    def __init__(self, config: SemanticRetrieverConfig, vs_manager: VectorStoreManager):
        """초기화
        
        Args:
            config (SemanticRetrieverConfig): 시맨틱 검색 설정
        """
        super().__init__(config, vs_manager=vs_manager)
        self.config = config

        
    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict] = None
    ) -> RetrievalResult:
        """테이블 모드 시맨틱 검색 수행
        
        부모 클래스의 검색 결과를 받아서 테이블 모드에 맞게 처리합니다.
        
        Args:
            query (str): 검색 쿼리
            top_k (Optional[int], optional): 문서당 청크 검색 결과 개수. Defaults to None.
            filters (Optional[Dict], optional): 검색 필터. Defaults to None.
            
        Returns:
            RetrievalResult: 검색 결과
        """
        try:
            # 내일하자..
            # MMR로 하는게 맞나.
            # 재귀적으로 Similarity Search 하는게 맞나.

            #filter {'document_ids': ['08c0b3c7-4173-4834-a296-095ea6b594c8', 'bb591d2a-362e-4317-b834-e77e99ec03b3']}
            logger.info(f"table 시멘틱 검색 target : {filters}")
            #vs_manager = VectorStoreManager(embedding_model_type=self.embedding_service.get_model_type())
            doc_ids = filters.get("document_ids") if filters else None
            doc_count = len(doc_ids) if doc_ids else 0
            search_results = self.vs_manager.search_mmr(
                query=query,
                top_k=top_k,
                fetch_k=top_k*2,
                lambda_mult=0.2,
                filters=filters
            )


            #search_results = [(Document, score), (Document, score), ...]
            # Document.metadata는 저장할때 넣었던 metadata와 같은 구조다.
            
            if not search_results:
                logger.warning("검색 결과가 없습니다.")
                return RetrievalResult(documents=[])
            logger.info(f"입력문서 개수 : {doc_count}, 검색된 총 매치 수: {len(search_results)}")
            
            # 상위 K개만 선택하고 Document 객체만 추출
            actual_top_k = min(len(search_results), doc_count)
            filtered_results = search_results[:actual_top_k]
            
            # Document 객체에 score 정보를 포함시킴
            documents = []
            # missed dic
            found_doc_ids = set()
            for doc, score in filtered_results:
                doc_id = doc.metadata.get('document_id', None)
                if doc_id:
                    found_doc_ids.add(doc_id)
                # 기존 Document 객체의 속성을 복사하여 새로운 Document 생성
                new_doc = Document(
                    page_content=doc.page_content,
                    metadata=doc.metadata.copy(),  # metadata는 깊은 복사
                    score=score  # score 추가
                )
                
                documents.append(new_doc)

            ########################################
            # 누락된 문서에 대하여 재검색
            # 다양성을 최대치로 줘도 빠지는 문서가 생긴다.
            ########################################

            missed_doc_ids = set(doc_ids) - found_doc_ids
            if missed_doc_ids:
                # 누락된 문서들에 대해 추가 검색 수행
                doc_count = len(missed_doc_ids)
                missed_filters = {"document_ids": list(missed_doc_ids)}
                logger.warning(f"누락된 문서 재검색 필터 : {missed_filters}")
                additional_results = self.vs_manager.search_mmr(
                    query=query,
                    filters=missed_filters,
                    top_k=doc_count*2,
                    fetch_k=doc_count*4,
                    lambda_mult=0.3
                )
                
                # 추가 검색 결과를 documents에 추가
                for doc, score in additional_results:
                    new_doc = Document(
                        page_content=doc.page_content,
                        metadata=doc.metadata.copy(),
                        score=score
                    )
                    documents.append(new_doc)
            

            # 쿼리 분석 정보 추가
            query_analysis = {
                "type": "semantic_mmr",
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
            
            return result
            
        except Exception as e:
            logger.error(f"테이블 모드 시맨틱 검색 중 오류 발생: {str(e)}")
            raise
        
    async def add_documents(self, documents: List[Document]) -> bool:
        """문서를 벡터 스토어에 추가"""
        return await super().add_documents(documents)
        
    async def delete_documents(self, document_ids: List[str]) -> bool:
        """벡터 스토어에서 문서 삭제"""
        return await super().delete_documents(document_ids)
        
    async def update_documents(self, documents: List[Document]) -> bool:
        """벡터 스토어의 문서 업데이트"""
        return await super().update_documents(documents) 
    