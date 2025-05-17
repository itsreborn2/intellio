from typing import List, Dict, Optional, Tuple

from loguru import logger # loguru import 추가
from .models import DocumentWithScore, RetrievalResult

from common.services.vector_store_manager import VectorStoreManager
from common.core.config import settings
from .semantic import SemanticRetriever, SemanticRetrieverConfig

import pinecone

# logger = logging.getLogger(__name__) # 삭제

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
            async def _recursive_search(remaining_doc_ids: set, found_docs: List[DocumentWithScore], max_retries: int = 3) -> List[DocumentWithScore]:
                """재귀적으로 누락된 문서를 검색하는 내부 함수"""
                if not remaining_doc_ids or max_retries <= 0:
                    return found_docs
                
                doc_count = len(remaining_doc_ids)
                logger.warning(f"재검색 시도 - remaining_doc_ids: {remaining_doc_ids}")
                missed_filters = {
                    "document_id": {"$in": list(remaining_doc_ids)}
                }
                logger.warning(f"누락된 문서 재검색 필터 (남은 시도: {max_retries}): {missed_filters}")
                
                additional_results = self.vs_manager.search_mmr(
                    query=query,
                    filters=missed_filters,
                    top_k=doc_count*2,
                    fetch_k=doc_count*4,
                    lambda_mult=0.2
                )
                
                newly_found_doc_ids = set()
                for doc, score in additional_results:
                    doc_id = doc.metadata.get('document_id', None)
                    if doc_id:
                        newly_found_doc_ids.add(doc_id)
                    
                    new_doc = DocumentWithScore(
                        page_content=doc.page_content,
                        metadata=doc.metadata.copy(),
                        score=score
                    )
                    found_docs.append(new_doc)
                
                still_missing = remaining_doc_ids - newly_found_doc_ids
                if still_missing:
                    return await _recursive_search(still_missing, found_docs, max_retries - 1)
                return found_docs

            #doc easy의 테이블모드 한정 검색이네. 클래스 자체가 그런것.
            # 메타데이터도 문서 아이디만 참고 가능.
            logger.info(f"table 시멘틱 검색 target : {filters}")
            # document_id 리스트 추출
            doc_ids = filters.get("document_id", {}).get("$in", []) if filters else []
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
            
            # Document 객체에 score 정보를 포함시킴
            documents = []
            found_doc_ids = set()
            
            # 모든 검색 결과를 처리하여 document_id를 수집
            for doc, score in search_results:
                doc_id = doc.metadata.get('document_id', None)
                if doc_id:
                    found_doc_ids.add(doc_id)
                
                new_doc = DocumentWithScore(
                    page_content=doc.page_content,
                    metadata=doc.metadata.copy(),
                    score=score
                )
                documents.append(new_doc)

            # 누락된 문서 재귀적 검색 - 실제로 문서가 없는 경우에만 수행
            missed_doc_ids = set(doc_ids) - found_doc_ids
            if missed_doc_ids:
                logger.warning(f"누락된 문서 ID 목록: {missed_doc_ids}")
                logger.warning(f"원본 doc_ids: {doc_ids}")
                logger.warning(f"찾은 doc_ids: {found_doc_ids}")
                documents = await _recursive_search(missed_doc_ids, documents)

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
        
    async def add_documents(self, documents: List[DocumentWithScore]) -> bool:
        """문서를 벡터 스토어에 추가"""
        return await super().add_documents(documents)
        
    async def delete_documents(self, document_ids: List[str]) -> bool:
        """벡터 스토어에서 문서 삭제"""
        return await super().delete_documents(document_ids)
        
    async def update_documents(self, documents: List[DocumentWithScore]) -> bool:
        """벡터 스토어의 문서 업데이트"""
        return await super().update_documents(documents) 
    