from typing import List, Dict, Optional, Tuple
from langchain_community.vectorstores import Pinecone as PineconeLangchain
from langchain_core.documents import Document as LangchainDocument
from pinecone import Pinecone as PineconeClient, PodSpec, ServerlessSpec
import pinecone
from common.core.config import settings
from common.services.embedding_models import EmbeddingModelType
import logging
from threading import Lock
import asyncio
from functools import wraps
from common.services.embedding import EmbeddingService
from numpy.linalg import norm
import numpy as np
from datetime import datetime
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
    """벡터 스토어 관리 클래스"""
    _initialized = False
    _initialization_error = None

    def __init__(self, embedding_model_type: EmbeddingModelType = None, namespace: str = None, project_name:str = None):
        """
        VectorStoreManager 초기화
        Args:
            embedding_model_type: 임베딩 모델 타입
            namespace: Pinecone 네임스페이스. 기본값은 None
        """
        if embedding_model_type is None:
            raise ValueError("초기화 시에는 embedding_model_type이 필요합니다.")
            
        self.project_name = project_name
        self.embedding_model_type = embedding_model_type
        self.namespace = namespace
        
        self.embedding_model_config = None
        self.pinecone_client = None
        self.index = None
        self._lock = Lock()
        self._initialized = False
        self._initialized_future = None
        
        # 동기적으로 초기화 실행
        self._sync_initialize()

    def _sync_initialize(self):
        """동기 초기화 메서드"""
        try:
            embedding_service = EmbeddingService(self.embedding_model_type)
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
                
                try:
                    # 인덱스 생성 - 메트릭을 dotproduct로 변경
                    # api key로 이미 인덱스, 프로젝트가 고정되었음

                    # stockeasy는 pod spec으로.
                    # stockeasy는 개발모드에서도 prod 인덱스를 검색해야할수도 있는데.
                    # env따라 접근을 달리하는 방법은 잠깐 고민을 해보자.
                    # env.dev, env.prod의 stockeasy 인덱스 값을 prod껄로 고정해놔야겠다
                    # 자료 수집은 서버에서 prod로..
                    # 개발 환경에서는 stockeasy db에 writing하지 않도록 해야겠네.

                    if self.project_name == "stockeasy":
                        logger.error(f"Pinecone 인덱스 {self.embedding_model_config.name} 없음. 생성 중...(PodSpec)")
                        self.pinecone_client.create_index(
                            name=self.embedding_model_config.name,
                            dimension=self.embedding_model_config.dimension,
                            metric="dotproduct",  # cosine에서 dotproduct로 변경
                            spec=PodSpec(
                                environment=settings.PINECONE_ENVIRONMENT,
                                pod_type="p1"
                            )
                        )
                    else:
                        logger.error(f"Pinecone 인덱스 {self.embedding_model_config.name} 없음. 생성 중...(ServerlessSpec)")
                        self.pinecone_client.create_index(
                            name=self.embedding_model_config.name,
                            dimension=self.embedding_model_config.dimension,
                            metric="dotproduct",  # cosine에서 dotproduct로 변경
                            spec=ServerlessSpec(
                                cloud="aws",
                                region="us-west-2"
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

    async def _async_initialize(self, *args, **kwargs):
        """비동기 초기화 메서드"""
        try:
            # 동기 초기화 메서드를 비동기적으로 실행
            await asyncio.to_thread(self._sync_initialize)
            self._initialized_future.set_result(True)
        except Exception as e:
            self._initialization_error = e
            self._initialized_future.set_exception(e)

    async def ensure_initialized(self):
        """비동기 초기화가 완료되었는지 확인"""
        if not self._initialized:
            if not self._initialized_future:
                self._initialized_future = asyncio.Future()
                await self._async_initialize()
            await self._initialized_future
        return True

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
        # if filters and 'document_ids' in filters:
        #     filters = {"document_id": {"$in": filters['document_ids']}}

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
        # if filters and 'document_ids' in filters:
        #     filters = {"document_id": {"$in": filters['document_ids']}}
      
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

        # if filters and 'document_ids' in filters:
        #     filters = {"document_id": {"$in": filters['document_ids']}}

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
            
            if self.project_name == "stockeasy" and settings.ENV == "dev":
                logger.warning("Stockeasy 프로젝트는 개발 환경에서는 데이터 저장을 하지 않습니다.")
                return False

            # 벡터 정규화 수행
            normalized_vectors = []
            for vector in _vectors:
                values = vector.get("values", [])
                if values:
                    # L2 정규화 수행
                    values_array = np.array(values)
                    normalized_values = values_array / norm(values_array)
                    vector["values"] = normalized_values.tolist()
                    _meta = vector.get("metadata", {})
                    if _meta:
                        for key, value in _meta.items():
                            # null 값 처리
                            if value is None:
                                _meta[key] = ""  # 빈 문자열로 변환
                    vector["metadata"] = _meta
                normalized_vectors.append(vector)
            
            # 정규화된 벡터 저장
            logger.info(f"[{self.namespace}] 벡터 {len(normalized_vectors)}개 저장 중")
            self.index.upsert(vectors=normalized_vectors, namespace=self.namespace)
            logger.info(f"[{self.namespace}] 벡터 {len(normalized_vectors)}개 저장 완료")
            return True

        except Exception as e:
            try:
                import json
                import copy
                
                # 로깅용 복사본 생성
                vectors_for_logging = []
                
                # 리스트인 경우 각 항목 처리
                if isinstance(normalized_vectors, list):
                    for vector in normalized_vectors:
                        vector_copy = copy.deepcopy(vector)
                        # values 필드 제거
                        if 'values' in vector_copy:
                            del vector_copy['values']
                        vectors_for_logging.append(vector_copy)
                # 딕셔너리인 경우 직접 처리
                elif isinstance(normalized_vectors, dict):
                    vectors_for_logging = copy.deepcopy(normalized_vectors)
                    if 'values' in vectors_for_logging:
                        del vectors_for_logging['values']
                
                # 가독성 좋게 JSON 형식으로 출력
                formatted_vectors = json.dumps(vectors_for_logging, ensure_ascii=False, indent=2)
                logger.error(f"[{self.namespace}] normalized_vectors (values 제외): {formatted_vectors}")
            except Exception as logging_error:
                # 로깅 과정에서 오류 발생 시
                logger.error(f"[{self.namespace}] 벡터 로깅 중 오류 발생: {str(logging_error)}")
            
            raise

    async def store_vectors_async(self, _vectors: List[Dict]) -> bool:
        """벡터를 Pinecone에 저장"""
        await self.ensure_initialized()
        #return await asyncio.to_thread(self.store_vectors, _vectors)
        return self.store_vectors(_vectors)

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