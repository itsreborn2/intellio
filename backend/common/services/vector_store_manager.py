from typing import List, Dict, Optional, Tuple
from langchain_community.vectorstores import Pinecone as PineconeLangchain
from langchain_core.documents import Document as LangchainDocument
from pinecone import Pinecone as PineconeClient, PodSpec
import pinecone
from common.core.config import settings
from common.services.embedding_models import EmbeddingModelType
import logging
from threading import Lock
import asyncio
from functools import wraps
from common.services.embedding import EmbeddingService
#from langchain_teddynote.community.pinecone import upsert_documents, upsert_documents_parallel

logger = logging.getLogger(__name__)

def async_init(func):
    """비동기 초기화를 위한 데코레이터"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, '_initialized_future'):
            self._initialized_future = asyncio.Future()
            asyncio.create_task(self._async_initialize(*args, **kwargs))
        return self._initialized_future
    return wrapper

class VectorStoreManager:
    """벡터 스토어 관리 클래스 (싱글턴)"""
    _instance = None
    _lock = Lock()
    _initialized = False
    _initialization_error = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(VectorStoreManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, embedding_model_type: EmbeddingModelType = None, namespace: str = None, project_name:str = None):
        """
        VectorStoreManager 초기화
        Args:
            embedding_model_type: 임베딩 모델 타입
            namespace: Pinecone 네임스페이스. 기본값은 None
        """
        if self._initialized:
            return
        
        with self._lock:
            if self._initialized:
                return
            
            if not self._initialized and embedding_model_type is None:
                raise ValueError("첫 초기화 시에는 embedding_model_type이 필요합니다.")
            self.project_name = project_name
            self.embedding_model_type = embedding_model_type
            self.namespace = namespace
            
            self.embedding_model_config = None
            self.pinecone_client = None
            self.index = None
            
            # 동기적으로 초기화 실행
            self._sync_initialize()

    def _sync_initialize(self):
        """동기 초기화 메서드"""
        try:
            embedding_service = EmbeddingService()
            self.embedding_model_provider = embedding_service.provider
            self.embedding_obj, self.embedding_obj_async = self.embedding_model_provider.get_embeddings_obj()
            self.embedding_model_config = embedding_service.current_model_config

            _api_key = settings.PINECONE_API_KEY_DOCEASY
            if self.project_name == "stockeasy":
                _api_key = settings.PINECONE_API_KEY_STOCKEASY
            # Pinecone 초기화 (새로운 방식)
            self.pinecone_client = PineconeClient(
                api_key=_api_key,
                environment=settings.PINECONE_ENVIRONMENT
            )

            # 인덱스 존재 여부 확인
            if self.embedding_model_config.name not in self.pinecone_client.list_indexes().names():
                logger.error(f"Pinecone 인덱스 {self.embedding_model_config.name} 없음. 생성 중...")
                try:
                    # 인덱스 생성
                    self.pinecone_client.create_index(
                        name=self.embedding_model_config.name,
                        dimension=self.embedding_model_config.dimension,
                        #metric="euclidean" 이미지, 오디오등에 적합.
                        #metric="dotproduct", 계산이 빠름, 크기가 중요한 경유.
                        metric="cosine",
                        spec=PodSpec(
                            environment=settings.PINECONE_ENVIRONMENT,
                            pod_type="p1"
                        )
                    )
                except Exception as e:
                    logger.error(f"Pinecone 인덱스 생성 실패: {str(e)}")
                    raise

            # 인덱스 가져오기
            self.index = self.pinecone_client.Index(self.embedding_model_config.name)
            self.vector_store = PineconeLangchain(
                index=self.index, 
                namespace=self.namespace,
                embedding=self.embedding_obj,
                text_key="text"  # 문서 내용을 저장할 메타데이터 필드 키
            )
            # AI 주석삭제금지.
            # pinecone에 저장할때 vectors.metadata.text 사용. 따라서 위에서 text_key는 "text"가 들어가야함.
            # vectors.append({
            # 	"id": chunk_id,
            # 	"values": embedding,
            # 	"metadata": {
            # 		"document_id": document_id,
            # 		"chunk_index": batch_start_idx + i,
            # 		"text": chunk
            # 	}
            # })
            self._initialized = True
        except Exception as e:
            self._initialization_error = e
            raise e

    def search(self, query: str, top_k: int, filters: Optional[Dict] = None) -> List[Tuple[LangchainDocument, float]]:
        """벡터 스토어에서 검색 수행"""
        logger.info(f"[{self.namespace}] 벡터 스토어 검색 시작 : {query}")

        ####################################
        # 1. 사용자 쿼리를 임베딩
        # 2. 임베딩 결과를 벡터 스토어에 검색
        # 3. 검색 결과를 반환
        ####################################
        # 사용자 쿼리 임베딩

        embedding = self.create_embeddings_single_query(query)

        # results = self.vector_store.similarity_search_by_vector_with_score(embedding=embedding, k=top_k, filter=filters)
        # #[(Document, score), (Document, score), ...]
        # filters 형식 변환
        if filters and 'document_ids' in filters:
            filters = {"document_id": {"$in": filters['document_ids']}}

        logger.info(f"[{self.namespace}] {filters}")

        # k: Number of Documents to return. Defaults to 4.
        # filter: Dictionary of argument(s) to filter on metadata
        results = self.vector_store.similarity_search_by_vector_with_score(
            namespace=self.namespace,
            embedding=embedding,
            k=top_k,
            filter=filters
        )
        return results

    async def search_async(self, query: str, top_k: int, filters: Optional[Dict] = None) -> List[Tuple[LangchainDocument, float]]:
        """벡터 스토어에서 검색 수행"""
        await self.ensure_initialized()
        logger.info(f"[{self.namespace}] 벡터 스토어 검색 시작 : {query}")

        ####################################
        # 1. 사용자 쿼리를 임베딩
        # 2. 임베딩 결과를 벡터 스토어에 검색
        # 3. 검색 결과를 반환
        ####################################
        # 사용자 쿼리 임베딩
        embedding = await self.create_embeddings_single_query_async(query)

        # filters 형식 변환
        if filters and 'document_ids' in filters:
            filters = {"document_id": {"$in": filters['document_ids']}}
      
        results = self.vector_store.similarity_search_by_vector_with_score(
            namespace=self.namespace,
            embedding=embedding,
            k=top_k,
            filter=filters,
        )
        return results

    def search_mmr(self, query: str, top_k: int, fetch_k:int, lambda_mult:float, filters: Optional[Dict] = None) -> List[Tuple[LangchainDocument, float]]:
        """벡터 스토어에서 검색 수행"""
        logger.info(f"[{self.namespace}] 벡터 스토어 검색 시작[MMR] : {query}")

        ####################################
        # 1. 사용자 쿼리를 임베딩
        # 2. 임베딩 결과를 벡터 스토어에 검색
        # 3. 검색 결과를 반환
        ####################################
        # 사용자 쿼리 임베딩
        embedding = self.create_embeddings_single_query(query)

        if filters and 'document_ids' in filters:
            filters = {"document_id": {"$in": filters['document_ids']}}

        doc_list: List[LangchainDocument] = self.vector_store.max_marginal_relevance_search_by_vector(
                namespace=self.namespace,
                embedding=embedding, 
                k=top_k,  # 문서 수 
                fetch_k=fetch_k,  # 초기 청크 
                lambda_mult=lambda_mult,  # 다양성 조절
                filter=filters
            )
        results = [(doc, 0.0) for doc in doc_list]
        return results
    

    def create_embeddings_single_query(self, query: str) -> List[float]:
        """문자열을 임베딩"""
        embeddings = self.embedding_model_provider.create_embeddings([query])
            
        # 임베딩 결과 검증
        if not embeddings or len(embeddings) == 0:
            logger.error("임베딩 생성 결과가 비어있음")
            raise ValueError("임베딩 생성 실패")
            
        embedding = embeddings[0]
        
        # 임베딩 벡터 검증
        if not isinstance(embedding, list) or len(embedding) != self.embedding_model_config.dimension:
            logger.error(f"잘못된 임베딩 형식 또는 차원: {len(embedding) if isinstance(embedding, list) else type(embedding)}")
            raise ValueError("잘못된 임베딩 형식")
        
        return embedding
    
    async def create_embeddings_single_query_async(self, query: str) -> List[float]:
        """문자열을 임베딩"""
        embeddings = await self.embedding_model_provider.create_embeddings_async([query])
            
        # 임베딩 결과 검증
        if not embeddings or len(embeddings) == 0:
            logger.error("임베딩 생성 결과가 비어있음")
            raise ValueError("임베딩 생성 실패")
            
        embedding = embeddings[0]
        
        # 임베딩 벡터 검증
        if not isinstance(embedding, list) or len(embedding) != self.embedding_model_config.dimension:
            logger.error(f"잘못된 임베딩 형식 또는 차원: {len(embedding) if isinstance(embedding, list) else type(embedding)}")
            raise ValueError("잘못된 임베딩 형식")
        
        return embedding

    def store_vectors(self, _vectors: List[Dict]) -> bool:
        """벡터를 Pinecone에 저장"""

        try:
            if not _vectors:
                logger.warning("저장할 벡터가 없습니다")
                return False
            
            # 벡터 저장
            logger.info(f"[{self.namespace}] 벡터 {len(_vectors)}개 저장 중")
            self.index.upsert(vectors=_vectors, namespace=self.namespace)
            logger.info(f"[{self.namespace}] 벡터 {len(_vectors)}개 저장 완료")
            return True

        except Exception as e:
            logger.error(f"[{self.namespace}] 벡터 저장 실패: {str(e)}", exc_info=True)
            return False

    async def store_vectors_async(self, _vectors: List[Dict]) -> bool:
        """벡터를 Pinecone에 저장"""
        await self.ensure_initialized()
        try:
            if not _vectors:
                logger.warning("저장할 벡터가 없습니다")
                return False
            
            # 벡터 저장
            logger.info(f"[{self.namespace}] 벡터 {len(_vectors)}개 저장 중")
            await self.index.upsert(vectors=_vectors, namespace=self.namespace)
            logger.info(f"[{self.namespace}] 벡터 {len(_vectors)}개 저장 완료")
            return True

        except Exception as e:
            logger.error(f"[{self.namespace}] 벡터 저장 실패: {str(e)}", exc_info=True)
            return False

    async def add_documents(self, documents: List[Dict]) -> bool:
        """문서를 벡터 스토어에 추가"""
        #await self.ensure_initialized()
        try:
            await self.index.upsert(vectors=documents, namespace=self.namespace)
            return True
        except Exception as e:
            logger.error(f"문서 추가 중 오류 발생: {str(e)}")
            return False
    def delete_documents_by_embedding_id(self, embed_ids: List[str]) -> bool:
        """벡터 스토어에서 문서 삭제"""
        # >>> index.delete(ids=['id1', 'id2'], namespace='my_namespace')
        # >>> index.delete(delete_all=True, namespace='my_namespace')
        # >>> index.delete(filter={'key': 'value'}, namespace='my_namespace') # 메타데이터 기준으로 삭제
        try:
            #result = self.index.delete(filter={"$or": [{"document_id": doc_id} for doc_id in document_ids]})
            result = self.index.delete(ids=embed_ids, namespace=self.namespace)
            # 반환값이 빈 딕셔너리인지 확인하여 삭제 성공 여부를 판단
            if isinstance(result, dict) and result == {}:
                logger.info(f"{self.namespace} - 문서 삭제 성공 (Sync)")
                return True
            else:
                logger.error(f"{self.namespace} - 삭제 결과 값이 유효하지 않음 (Sync): {result}")

                return False
        except Exception as e:
            logger.error(f"문서 삭제 중 오류 발생[Sync]: {str(e)}")

            return False
        
    async def delete_documents_by_embedding_id_async(self, embed_ids: List[str]) -> bool:
        """벡터 스토어에서 문서 삭제"""
        try:
            result = await asyncio.to_thread(self.index.delete, ids=embed_ids, namespace=self.namespace)
            # 반환값이 빈 딕셔너리인지 확인하여 삭제 성공 여부를 판단
            if isinstance(result, dict) and result == {}:
                logger.info(f"{self.namespace} - 문서 삭제 성공 (Async)")
                return True
            else:
                logger.error(f"{self.namespace} - 삭제 결과 값이 유효하지 않음 (Async): {result}")

                return False
        except Exception as e:
            logger.error(f"{self.namespace} - 문서 삭제 중 오류 발생[Async]: {str(e)}")
            return False

    async def update_documents(self, documents: List[Dict]) -> bool:
        """벡터 스토어의 문서 업데이트"""
        #await self.ensure_initialized()
        try:
            await self.index.upsert(vectors=documents, namespace=self.namespace)
            return True
        except Exception as e:
            logger.error(f"문서 업데이트 중 오류 발생: {str(e)}")
            return False 

    def delete_namespace(self) -> bool:
        """현재 네임스페이스의 모든 데이터를 삭제합니다."""
        try:
            if not self.namespace:
                logger.warning("네임스페이스가 지정되지 않았습니다.")
                return False
            
            logger.info(f"[{self.namespace}] 네임스페이스 전체 삭제 시작")
            result = self.index.delete(delete_all=True, namespace=self.namespace)
            
            # 반환값이 빈 딕셔너리인지 확인하여 삭제 성공 여부를 판단
            if isinstance(result, dict) and result == {}:
                logger.info(f"[{self.namespace}] 네임스페이스 전체 삭제 완료")
                return True
            else:
                logger.error(f"[{self.namespace}] 삭제 결과 값이 유효하지 않음: {result}")
                return False
                
        except Exception as e:
            logger.error(f"[{self.namespace}] 네임스페이스 삭제 중 오류 발생: {str(e)}")
            return False
            
    async def delete_namespace_async(self) -> bool:
        """현재 네임스페이스의 모든 데이터를 비동기적으로 삭제합니다."""
        try:
            if not self.namespace:
                logger.warning("네임스페이스가 지정되지 않았습니다.")
                return False
            
            logger.info(f"[{self.namespace}] 네임스페이스 전체 삭제 시작 (Async)")
            result = await asyncio.to_thread(self.index.delete, delete_all=True, namespace=self.namespace)
            
            # 반환값이 빈 딕셔너리인지 확인하여 삭제 성공 여부를 판단
            if isinstance(result, dict) and result == {}:
                logger.info(f"[{self.namespace}] 네임스페이스 전체 삭제 완료 (Async)")
                return True
            else:
                logger.error(f"[{self.namespace}] 삭제 결과 값이 유효하지 않음 (Async): {result}")
                return False
                
        except Exception as e:
            logger.error(f"[{self.namespace}] 네임스페이스 삭제 중 오류 발생 (Async): {str(e)}")
            return False 