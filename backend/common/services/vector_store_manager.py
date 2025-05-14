from typing import List, Dict, Optional, Tuple
# from langchain_community.vectorstores import Pinecone as PineconeLangchain
from langchain_pinecone import Pinecone as PineconeLangchain
from langchain_core.documents import Document as LangchainDocument
from pinecone import Pinecone as PineconeClient, PodSpec, ServerlessSpec
from pinecone import PineconeAsyncio  # 비동기 지원을 위해 추가
import pinecone
import time

from common.utils.util import measure_time_async  # 성능 측정을 위해 추가

from .embedding_models import EmbeddingModelType
import logging
from threading import Lock
import asyncio
from functools import wraps
from .embedding import EmbeddingService
from numpy.linalg import norm
import numpy as np
from datetime import datetime
#from langchain_teddynote.community.pinecone import upsert_documents, upsert_documents_parallel
import os
import aiohttp  # 명시적으로 aiohttp 임포트 추가

logger = logging.getLogger(__name__)
#from loguru import logger

# aiohttp 세션을 정리하기 위한 유틸리티 함수
async def cleanup_aiohttp_sessions():
    """활성 aiohttp 세션을 명시적으로 정리하는 유틸리티 함수"""
    try:
        # ClientSession.detach() 메서드를 호출하여 연결 유지하지 않도록 설정
        for attr_name in dir(aiohttp):
            if 'session' in attr_name.lower():
                attr = getattr(aiohttp, attr_name)
                # 클래스에 close_all 메서드가 있는 경우
                if hasattr(attr, 'close_all'):
                    await asyncio.to_thread(attr.close_all)
                    logger.info(f"aiohttp {attr_name} 세션 풀 정리됨")
        
        # ClientSession._connector_owner가 False로 설정되었을 수 있으므로
        # Connector도 직접 닫기 시도
        for attr_name in dir(aiohttp):
            if 'connector' in attr_name.lower():
                attr = getattr(aiohttp, attr_name)
                if hasattr(attr, 'close_all'):
                    await asyncio.to_thread(attr.close_all)
                    logger.info(f"aiohttp {attr_name} 커넥터 풀 정리됨")
        
        logger.info("모든 aiohttp 세션 정리 완료")
    except Exception as e:
        logger.warning(f"aiohttp 세션 정리 중 오류 발생: {str(e)}")


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
    """벡터 스토어 관리 클래스 (동기 및 비동기 작업 모두 지원)"""
    _initialized = False
    _initialization_error = None
    _initialization_lock = None  # 비동기 초기화를 위한 락

    def __init__(self, embedding_model_type: EmbeddingModelType = None, namespace: str = None, project_name:str = None):
        """VectorStoreManager 초기화
        Args:
            embedding_model_type: 임베딩 모델 타입
            namespace: Pinecone 네임스페이스. 기본값은 None
            project_name: 프로젝트 이름
        """
        if embedding_model_type is None:
            raise ValueError("초기화 시에는 embedding_model_type이 필요합니다.")
            
        self.project_name = project_name
        self.embedding_model_type = embedding_model_type
        self.namespace = namespace
        
        self.embedding_model_config = None
        self.pinecone_client = None
        self.index = None
        self.async_index = None  # 비동기 작업을 위한 인덱스
        self._lock = Lock()
        self._initialization_lock = asyncio.Lock()  # 비동기 초기화를 위한 락
        self._initialized = False
        self._async_initialized = False  # 비동기 초기화 상태 추적
        self._initialized_future = None
        self._closed = False  # 리소스 정리 상태 추적
        
        # 동기적으로 초기화 실행
        self._sync_initialize()
        
        # 비동기 초기화는 비동기 컨텍스트에서만 실행 (동기 컨텍스트에서는 오류 방지)
        try:
            # 현재 이벤트 루프가 실행 중인지 확인
            loop = asyncio.get_running_loop()
            self._initialized_future = asyncio.Future()
            logger.info(f"[{self.namespace}] 이벤트 루프 감지됨, 비동기 초기화 태스크 생성 시작")
            asyncio.create_task(self._async_initialize())
        except RuntimeError:
            # 이벤트 루프가 실행 중이 아님 (동기 컨텍스트)
            logger.info(f"[{self.namespace}] 이벤트 루프가 없음, 비동기 초기화는 필요시 나중에 수행")
            self._initialized_future = None  # 초기화되지 않은 상태로 유지

    def _sync_initialize(self):
        """동기 초기화 메서드"""
        try:
            self.embedding_service = EmbeddingService()
            self.embedding_model_provider = self.embedding_service.provider
            self.embedding_obj, self.embedding_obj_async = self.embedding_model_provider.get_embeddings_obj()
            self.embedding_model_config = self.embedding_service.current_model_config

            _api_key = os.getenv("PINECONE_API_KEY_DOCEASY")
            if self.project_name == "stockeasy":
                _api_key = os.getenv("PINECONE_API_KEY_STOCKEASY")
            
            # Pinecone 6.0 스타일 초기화
            self.pinecone_client = PineconeClient(api_key=_api_key)
            #logger.info("Pinecone 6.0+ 스타일로 초기화 성공")

            # 인덱스 존재 여부 확인
            if self.embedding_model_config.name not in self.pinecone_client.list_indexes().names():
                logger.error(f"Pinecone 인덱스 {self.embedding_model_config.name} 없음. 생성 중...")
                try:
                    # 인덱스 생성 - 메트릭을 dotproduct로 변경
                    dimension = self.embedding_model_config.dimension
                    metric = "dotproduct"  # cosine에서 dotproduct로 변경
                    
                    self.pinecone_client.create_index(
                        name=self.embedding_model_config.name,
                        dimension=dimension,
                        metric=metric,
                        spec=PodSpec(
                            environment=os.getenv("PINECONE_ENVIRONMENT"),
                            pod_type="p1"
                        )
                    )
                except Exception as e:
                    logger.error(f"Pinecone 인덱스 생성 실패: {str(e)}")
                    raise

            # 동기 인덱스 가져오기
            self.index = self.pinecone_client.Index(self.embedding_model_config.name)
            
            # 비동기 인덱스를 위한 호스트 URL 생성
            index_details = self.pinecone_client.describe_index(self.embedding_model_config.name)
            host_url = index_details.host
            logger.info(f"실제 사용되는 Pinecone 호스트 URL: {host_url}")
            
            # 비동기 인덱스 객체 준비 (실제 초기화는 비동기 메서드에서 수행)
            self.async_index = None
            
            # LangChain과 통합을 위한 벡터 스토어 설정
            self.vector_store = PineconeLangchain(
                index_name=self.embedding_model_config.name,
                namespace=self.namespace,
                embedding=self.embedding_obj,
                text_key="text",  # 문서 내용을 저장할 메타데이터 필드 키
                pinecone_api_key=_api_key
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
        logger.info(f"[{self.namespace}] 비동기 초기화 시작")
        
        if self._async_initialized:
            logger.info(f"[{self.namespace}] 이미 비동기 초기화 완료됨")
            if self._initialized_future and not self._initialized_future.done():
                self._initialized_future.set_result(True)
            return
            
        async with self._initialization_lock:
            if self._async_initialized:
                logger.info(f"[{self.namespace}] 락 획득 후 이미 비동기 초기화 완료됨")
                if self._initialized_future and not self._initialized_future.done():
                    self._initialized_future.set_result(True)
                return
                
            if not self._initialized_future:
                logger.info(f"[{self.namespace}] 초기화 Future 객체 생성")
                self._initialized_future = asyncio.Future()
                
            try:
                # 동기 초기화가 되어 있지 않다면 먼저 실행
                if not hasattr(self, 'embedding_model_config') or self.embedding_model_config is None:
                    logger.info(f"[{self.namespace}] 동기 초기화가 필요하여 수행")
                    await asyncio.to_thread(self._sync_initialize)
                
                # 비동기 인덱스 객체 생성 (호스트 URL이 필요)
                if hasattr(self, 'pinecone_client') and self.pinecone_client is not None:
                    logger.info(f"[{self.namespace}] 비동기 인덱스 객체 생성 시작")
                    index_details = self.pinecone_client.describe_index(self.embedding_model_config.name)
                    host_url = index_details.host
                    #logger.info(f"[{self.namespace}] 비동기 인덱스 호스트 URL: {host_url}")
                    
                    # 비동기 인덱스 객체 생성
                    self.async_index = self.pinecone_client.IndexAsyncio(host=host_url)
                    logger.info(f"[{self.namespace}] 비동기 Pinecone 인덱스 초기화 완료")
                else:
                    logger.error(f"[{self.namespace}] Pinecone 클라이언트가 초기화되지 않아 비동기 인덱스를 생성할 수 없습니다.")
                    raise RuntimeError("Pinecone 클라이언트 초기화 실패")
                
                self._initialized = True
                self._async_initialized = True  # 비동기 초기화 완료 표시
                logger.info(f"[{self.namespace}] 비동기 초기화 완전히 완료")
                
                if not self._initialized_future.done():
                    self._initialized_future.set_result(True)
            except Exception as e:
                self._initialization_error = e
                logger.error(f"[{self.namespace}] 비동기 초기화 중 오류 발생: {str(e)}")
                if not self._initialized_future.done():
                    self._initialized_future.set_exception(e)
                raise e

    async def ensure_initialized(self):
        """비동기 초기화가 완료되었는지 확인하고, 필요하다면 기다림"""
        
        # 이미 비동기 초기화가 완료된 경우
        if self._async_initialized:
            return self._initialized
        
        # 비동기 초기화가 아직 시작되지 않은 경우
        if not self._initialized_future:
            logger.info(f"[{self.namespace}] 비동기 초기화가 시작되지 않아 시작")
            try:
                # 이벤트 루프 확인
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    # 이벤트 루프가 없는 경우 (동기 컨텍스트에서 호출됨)
                    logger.warning(f"[{self.namespace}] 비동기 초기화 중 이벤트 루프가 없습니다. "
                                 f"동기적 초기화만 사용합니다.")
                    return self._initialized
                
                # 이벤트 루프가 있는 경우 비동기 초기화 시작
                self._initialized_future = asyncio.Future()
                await self._async_initialize()
            except Exception as e:
                logger.error(f"[{self.namespace}] 비동기 초기화 시작 실패: {str(e)}")
                if self._initialized_future and not self._initialized_future.done():
                    self._initialized_future.set_exception(e)
                raise
        elif not self._initialized_future.done():
            # 비동기 초기화가 진행 중인 경우, 완료될 때까지 대기
            logger.info(f"[{self.namespace}] 비동기 초기화 완료 대기 중...")
            await self._initialized_future
            logger.info(f"[{self.namespace}] 비동기 초기화 대기 완료")
        
        # 초기화 중 에러가 발생했는지 확인
        if hasattr(self, '_initialization_error') and self._initialization_error is not None:
            logger.error(f"[{self.namespace}] 비동기 초기화 중 오류 발생: {str(self._initialization_error)}")
            raise self._initialization_error
                
        # # 비동기 인덱스가 생성되었는지 확인
        # if not hasattr(self, 'async_index') or self.async_index is None:
        #     logger.warning(f"[{self.namespace}] 비동기 인덱스가 아직 설정되지 않았습니다. 다시 초기화를 시도합니다.")
        #     # 마지막 시도로 직접 비동기 인덱스 설정
        #     try:
        #         index_details = self.pinecone_client.describe_index(self.embedding_model_config.name)
        #         host_url = index_details.host
        #         self.async_index = self.pinecone_client.IndexAsyncio(host=host_url)
        #         logger.info(f"[{self.namespace}] 비동기 Pinecone 인덱스 생성 성공 (재시도)")
        #         self._async_initialized = True
        #     except Exception as e:
        #         logger.error(f"[{self.namespace}] 비동기 인덱스 생성 실패 (재시도): {str(e)}")
        #         # 비동기 인덱스가 없어도 동기 인덱스는 사용 가능하므로 계속 진행
        #         logger.warning(f"[{self.namespace}] 비동기 인덱스 없이 동기 인덱스만 사용합니다.")
                
        return self._initialized
        
    async def initialize(self):
        """외부에서 비동기 초기화를 명시적으로 실행하기 위한 메서드
        
        Returns:
            self: 초기화된 VectorStoreManager 인스턴스
        """
        await self.ensure_initialized()
        return self

    def search(self, query: str, top_k: int, filters: Optional[Dict] = None) -> List[Tuple[LangchainDocument, float]]:
        """벡터 스토어에서 검색 수행"""
        logger.info(f"[{self.namespace}] 벡터 스토어 검색 시작 : {query}")

        # 사용자 쿼리 임베딩
        embedding = self.create_embeddings_single_query(query)

        logger.info(f"[{self.namespace}] 필터: {filters}")

        # k: Number of Documents to return. Defaults to 4.
        # filter: Dictionary of argument(s) to filter on metadata
        results = self.vector_store.similarity_search_by_vector_with_score(
            namespace=self.namespace,
            embedding=embedding,
            k=top_k,
            filter=filters
        )
        return results

    @measure_time_async
    async def search_async(self, query: str, top_k: int, filters: Optional[Dict] = None) -> List[Tuple[LangchainDocument, float]]:
        """벡터 스토어에서 검색 수행 (비동기)"""
        # 비동기 초기화 확실히 기다리기
        try:
            await self.ensure_initialized()
            await self.get_async_index()
        except RuntimeError as e:
            # 런타임 에러가 발생하면 이벤트 루프가 없는 상황일 수 있음
            if "no running event loop" in str(e):
                logger.warning(f"[{self.namespace}] 이벤트 루프가 없어 동기 메서드로 폴백")
                return self.search(query, top_k, filters)
            logger.error(f"[{self.namespace}] 비동기 초기화 실패: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[{self.namespace}] 비동기 초기화 실패: {str(e)}")
        
        print(f"[{self.namespace}] 벡터 스토어 비동기 검색 시작 : {query}")

        # 사용자 쿼리 임베딩
        try:
            start_time = time.time()
            embedding = await self.create_embeddings_single_query_async(query)
            end_time = time.time()
            print(f"[{self.namespace}] 임베딩 생성 시간: {(end_time - start_time):.3f}초, 쿼리: {query}")
        except RuntimeError as e:
            # 런타임 에러가 발생하면 동기 메서드로 폴백
            if "no running event loop" in str(e):
                logger.warning(f"[{self.namespace}] 임베딩 생성 중 이벤트 루프 없음, 동기 메서드로 폴백")
                embedding = self.create_embeddings_single_query(query)
            else:
                raise
        
        #print(f"[{self.namespace}] 필터: {filters}")
        
        try:
            # 비동기 인덱스가 초기화되었는지 확인 (다시 한 번 명시적으로 확인)
            
            if hasattr(self, 'async_index') and self.async_index is not None:
                # Pinecone 비동기 클라이언트 직접 사용
                print(f"[{self.namespace}] Pinecone 비동기 클라이언트(async_index) 직접 사용")
                
                start_time = time.time()
                # Pinecone 6.0+ 비동기 API 사용
                try:
                    query_response = await self.async_index.query(
                        vector=embedding,
                        top_k=top_k,
                        include_metadata=True,
                        include_values=False,
                        namespace=self.namespace,
                        filter=filters
                    )
                except RuntimeError as e:
                    # 이벤트 루프 오류가 발생하면 동기 메서드로 폴백
                    if "no running event loop" in str(e):
                        logger.warning(f"[{self.namespace}] 쿼리 중 이벤트 루프 없음, 동기 메서드로 폴백")
                        return self.search(query, top_k, filters)
                    else:
                        logger.warning(f"[{self.namespace}] 비동기 클라이언트 중 오류 발생: {str(e)}")
                        raise
                finally:
                    end_time = time.time()
                    print(f"[{self.namespace}] Pinecone 비동기 쿼리 시간: {end_time - start_time}초")
                    logger.info(f"[{self.namespace}] Pinecone 비동기 쿼리 시간: {end_time - start_time}초")
                    # 비동기 클라이언트는 vector_store_manager 에서 관리하면 안됨
                    # retirver에서 search 함수를 여러번 호출할 수 있음.
                    #await self.async_index.close()
                    pass
                
                #end_time = time.time()
                #print(f"[{self.namespace}] Pinecone 비동기 쿼리 시간: {end_time - start_time}초")

                # LangChain Document 형식으로 결과 변환
                docs = []
                for match in query_response.matches:
                    metadata = match.metadata if hasattr(match, 'metadata') else {}
                    
                    # 텍스트 컨텐츠 추출
                    text = ""
                    if 'text' in metadata and metadata['text']:
                        text = metadata['text']
                    elif 'content' in metadata and metadata['content']:
                        text = metadata['content']
                    elif 'page_content' in metadata and metadata['page_content']:
                        text = metadata['page_content']
                    
                    # 점수 추출
                    score = match.score if hasattr(match, 'score') else 0.0
                    
                    # Document 객체 생성 (LangChain과 호환)
                    doc = LangchainDocument(page_content=text, metadata=metadata)
                    
                    # 튜플로 추가 (Document, score)
                    docs.append((doc, score))
                
                return docs
            
            else:
                # 폴백: 기존 동기 메서드를 비동기 스레드로 실행
                logger.info(f"[{self.namespace}] 폴백: 동기 메서드를 비동기 스레드로 실행")
                try:
                    results = await asyncio.to_thread(
                        self.vector_store.similarity_search_by_vector_with_score,
                        namespace=self.namespace,
                        embedding=embedding,
                        k=top_k,
                        filter=filters
                    )
                    return results
                except RuntimeError as e:
                    # 이벤트 루프 오류가 발생하면 동기 메서드로 폴백
                    if "no running event loop" in str(e):
                        logger.warning(f"[{self.namespace}] to_thread 중 이벤트 루프 없음, 동기 메서드로 폴백")
                        return self.search(query, top_k, filters)
                    raise
        except Exception as e:
            logger.error(f"[{self.namespace}] 비동기 검색 중 오류 발생: {str(e)}")
            # 마지막 폴백: 표준 동기 메서드 사용
            logger.info(f"[{self.namespace}] 오류 발생, 표준 동기 메서드로 폴백")
            results = self.vector_store.similarity_search_by_vector_with_score(
                namespace=self.namespace,
                embedding=embedding,
                k=top_k,
                filter=filters
            )
            return results

    def search_mmr(self, query: str, top_k: int, fetch_k:int, lambda_mult:float, filters: Optional[Dict] = None) -> List[Tuple[LangchainDocument, float]]:
        """벡터 스토어에서 MMR 검색 수행 (다양성 고려)"""
        logger.info(f"[{self.namespace}] 벡터 스토어 검색 시작[MMR] : {query}")

        # 사용자 쿼리 임베딩
        embedding = self.create_embeddings_single_query(query)

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
    
    async def search_mmr_async(self, query: str, top_k: int, fetch_k:int, lambda_mult:float, filters: Optional[Dict] = None) -> List[Tuple[LangchainDocument, float]]:
        """MMR 알고리즘을 사용하여 다양성이 높은 검색 결과 반환 (비동기)"""
        await self.ensure_initialized()
        logger.info(f"[{self.namespace}] 벡터 스토어 검색 시작[MMR] : {query}")

        # 사용자 쿼리 임베딩
        embedding = await self.create_embeddings_single_query_async(query)

        # 검색 수행 - LangChain의 네이티브 비동기 인터페이스 사용
        try:
            # 네이티브 비동기 메서드 사용 확인
            if hasattr(self.vector_store, 'amax_marginal_relevance_search_by_vector'):
                # 네이티브 비동기 MMR 검색 메서드 사용
                doc_list = await self.vector_store.amax_marginal_relevance_search_by_vector(
                    namespace=self.namespace,
                    embedding=embedding, 
                    k=top_k,  # 문서 수 
                    fetch_k=fetch_k,  # 초기 청크 
                    lambda_mult=lambda_mult,  # 다양성 조절
                    filter=filters
                )
                logger.info(f"[{self.namespace}] 네이티브 비동기 MMR 메서드 사용하여 검색 완료")
            else:
                # 폴백: 네이티브 비동기 메서드가 없는 경우 to_thread 사용
                logger.info(f"[{self.namespace}] 네이티브 비동기 MMR 메서드 없음. to_thread 사용")
                doc_list = await asyncio.to_thread(
                    self.vector_store.max_marginal_relevance_search_by_vector,
                    namespace=self.namespace,
                    embedding=embedding, 
                    k=top_k,  # 문서 수 
                    fetch_k=fetch_k,  # 초기 청크 
                    lambda_mult=lambda_mult,  # 다양성 조절
                    filter=filters
                )
            
            # MMR은 점수를 반환하지 않으므로 0.0으로 채움
            results = [(doc, 0.0) for doc in doc_list]
            return results
            
        except Exception as e:
            logger.error(f"[{self.namespace}] MMR 검색 중 오류 발생: {str(e)}")
            raise

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
        """문자열을 임베딩 (비동기)"""
        try:
            embeddings = await self.embedding_model_provider.create_embeddings_async([query])
        except RuntimeError as e:
            # 이벤트 루프가 없는 경우 동기 메서드로 폴백
            if "no running event loop" in str(e):
                logger.warning(f"[{self.namespace}] 임베딩 생성 중 이벤트 루프 없음, 동기 메서드로 폴백")
                return self.create_embeddings_single_query(query)
            raise
        finally:
            # embedding_model_provider는 EmbeddingService 에 속해있기 때문에 개별적으로 해제하면 안됨
            #await self.embedding_model_provider.aclose()
            pass
            
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
        normalized_vectors = []
        try:
            if not _vectors:
                logger.warning("저장할 벡터가 없습니다")
                return False
            
            # 벡터 정규화 수행
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
            
            # 배치 크기 계산 (Pinecone 제한: 2MB)
            BATCH_SIZE = 50  # 시작 배치 크기
            
            # 전체 벡터를 배치 단위로 나누어 처리
            total_vectors = len(normalized_vectors)
            for i in range(0, total_vectors, BATCH_SIZE):
                batch = normalized_vectors[i:i + BATCH_SIZE]
                try:
                    logger.info(f"[{self.namespace}] 벡터 배치 {i//BATCH_SIZE + 1}/{(total_vectors+BATCH_SIZE-1)//BATCH_SIZE} (크기: {len(batch)}) 저장 중")
                    self.index.upsert(vectors=batch, namespace=self.namespace)
                    logger.info(f"[{self.namespace}] 벡터 배치 {i//BATCH_SIZE + 1} 저장 완료")
                except Exception as batch_error:
                    if "larger than the maximum supported size" in str(batch_error):
                        # 배치 크기가 너무 크면 더 작은 배치로 나누어 다시 시도
                        logger.warning(f"배치가 너무 큽니다. 더 작은 배치로 재시도합니다. 오류: {str(batch_error)}")
                        half_batch_size = len(batch) // 2
                        if half_batch_size == 0:
                            # 더 이상 나눌 수 없으면 개별 처리
                            for single_vector in batch:
                                try:
                                    self.index.upsert(vectors=[single_vector], namespace=self.namespace)
                                    logger.info(f"[{self.namespace}] 단일 벡터 저장 완료")
                                except Exception as single_error:
                                    logger.error(f"[{self.namespace}] 단일 벡터 저장 실패: {str(single_error)}")
                        else:
                            # 반으로 나누어 처리
                            first_half = batch[:half_batch_size]
                            second_half = batch[half_batch_size:]
                            try:
                                self.index.upsert(vectors=first_half, namespace=self.namespace)
                                logger.info(f"[{self.namespace}] 첫 번째 절반 배치 저장 완료")
                            except Exception as e:
                                logger.error(f"[{self.namespace}] 첫 번째 절반 배치 저장 실패: {str(e)}")
                            
                            try:
                                self.index.upsert(vectors=second_half, namespace=self.namespace)
                                logger.info(f"[{self.namespace}] 두 번째 절반 배치 저장 완료")
                            except Exception as e:
                                logger.error(f"[{self.namespace}] 두 번째 절반 배치 저장 실패: {str(e)}")
                    else:
                        # 크기 외 다른 오류는 기록하고 계속 진행
                        logger.error(f"[{self.namespace}] 배치 저장 실패: {str(batch_error)}")
            
            logger.info(f"[{self.namespace}] 전체 벡터 {total_vectors}개 저장 완료")
            return True

        except Exception as e:
            logger.error(f"[{self.namespace}] 벡터 저장 실패: {str(e)}", exc_info=True)
            # 로깅 관련 코드는 그대로 유지
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
        """벡터를 Pinecone에 비동기적으로 저장"""
        try:
            await self.ensure_initialized()
        except RuntimeError as e:
            # 이벤트 루프가 없는 경우 동기 메서드로 폴백
            if "no running event loop" in str(e):
                logger.warning(f"[{self.namespace}] 이벤트 루프가 없어 동기 메서드로 폴백하여 벡터 저장")
                return self.store_vectors(_vectors)
            # 다른 런타임 에러는 그대로 발생시킴
            logger.error(f"[{self.namespace}] 비동기 초기화 실패: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[{self.namespace}] 비동기 초기화 실패: {str(e)}")
        
        try:
            if not _vectors:
                logger.warning("저장할 벡터가 없습니다")
                return False
            
            logger.info(f"[{self.namespace}] 저장할 벡터 개수: {len(_vectors)}")
            # 벡터 정규화 수행
            normalized_vectors = []
            for vector in _vectors:
                values = vector.get("values", [])
                if values:
                    # L2 정규화 수행
                    values_array = np.array(values)
                    normalized_values = values_array / norm(values_array)
                    
                    # Pinecone 6.0+ 벡터 형식
                    vector["values"] = normalized_values.tolist()
                    _meta = vector.get("metadata", {})
                    if _meta:
                        for key, value in _meta.items():
                            # null 값 처리
                            if value is None:
                                _meta[key] = ""  # 빈 문자열로 변환
                    vector["metadata"] = _meta
                normalized_vectors.append(vector)
            
            # 배치 크기 계산 (Pinecone 제한: 2MB)
            BATCH_SIZE = 50  # 시작 배치 크기
            
            # 전체 벡터를 배치 단위로 나누어 비동기 처리
            total_vectors = len(normalized_vectors)
            
            # 비동기 인덱스가 사용 가능한지 확인
            await self.get_async_index()
            if hasattr(self, 'async_index') and self.async_index is not None:
                try:
                    # 네이티브 비동기 API 사용
                    for i in range(0, total_vectors, BATCH_SIZE):
                        batch = normalized_vectors[i:i + BATCH_SIZE]
                        try:
                            logger.info(f"[{self.namespace}] 벡터 배치 {i//BATCH_SIZE + 1}/{(total_vectors+BATCH_SIZE-1)//BATCH_SIZE} (크기: {len(batch)}) 저장 중")
                            try:
                                await self.async_index.upsert(
                                    namespace=self.namespace,
                                    vectors=batch
                                )
                            except RuntimeError as e:
                                # 이벤트 루프가 없는 경우
                                if "no running event loop" in str(e):
                                    logger.warning(f"[{self.namespace}] 벡터 배치 업서트 중 이벤트 루프 없음, 동기 메서드로 폴백")
                                    # 동기 메서드로 폴백
                                    self.index.upsert(vectors=batch, namespace=self.namespace)
                                else:
                                    raise
                            logger.info(f"[{self.namespace}] 벡터 배치 {i//BATCH_SIZE + 1} 저장 완료")
                        except Exception as batch_error:
                            if "larger than the maximum supported size" in str(batch_error):
                                # 배치 크기가 너무 크면 더 작은 배치로 나누어 다시 시도
                                logger.warning(f"배치가 너무 큽니다. 더 작은 배치로 재시도합니다. 오류: {str(batch_error)}")
                                half_batch_size = len(batch) // 2
                                if half_batch_size == 0:
                                    # 더 이상 나눌 수 없으면 개별 처리
                                    for single_vector in batch:
                                        try:
                                            try:
                                                await self.async_index.upsert(
                                                    namespace=self.namespace,
                                                    vectors=[single_vector]
                                                )
                                            except RuntimeError as e:
                                                # 이벤트 루프가 없는 경우
                                                if "no running event loop" in str(e):
                                                    logger.warning(f"[{self.namespace}] 단일 벡터 업서트 중 이벤트 루프 없음, 동기 메서드로 폴백")
                                                    self.index.upsert(vectors=[single_vector], namespace=self.namespace)
                                                else:
                                                    raise
                                            logger.info(f"[{self.namespace}] 단일 벡터 저장 완료")
                                        except Exception as single_error:
                                            logger.error(f"[{self.namespace}] 단일 벡터 저장 실패: {str(single_error)}")
                                else:
                                    # 반으로 나누어 처리
                                    first_half = batch[:half_batch_size]
                                    second_half = batch[half_batch_size:]
                                    try:
                                        try:
                                            await self.async_index.upsert(
                                                namespace=self.namespace,
                                                vectors=first_half
                                            )
                                        except RuntimeError as e:
                                            # 이벤트 루프가 없는 경우
                                            if "no running event loop" in str(e):
                                                logger.warning(f"[{self.namespace}] 첫 번째 절반 배치 업서트 중 이벤트 루프 없음, 동기 메서드로 폴백")
                                                self.index.upsert(vectors=first_half, namespace=self.namespace)
                                            else:
                                                raise
                                        logger.info(f"[{self.namespace}] 첫 번째 절반 배치 저장 완료")
                                    except Exception as e:
                                        logger.error(f"[{self.namespace}] 첫 번째 절반 배치 저장 실패: {str(e)}")
                                    
                                    try:
                                        try:
                                            await self.async_index.upsert(
                                                namespace=self.namespace,
                                                vectors=second_half
                                            )
                                        except RuntimeError as e:
                                            # 이벤트 루프가 없는 경우
                                            if "no running event loop" in str(e):
                                                logger.warning(f"[{self.namespace}] 두 번째 절반 배치 업서트 중 이벤트 루프 없음, 동기 메서드로 폴백")
                                                self.index.upsert(vectors=second_half, namespace=self.namespace)
                                            else:
                                                raise
                                        logger.info(f"[{self.namespace}] 두 번째 절반 배치 저장 완료")
                                    except Exception as e:
                                        logger.error(f"[{self.namespace}] 두 번째 절반 배치 저장 실패: {str(e)}")
                            else:
                                # 크기 외 다른 오류는 기록하고 계속 진행
                                logger.error(f"[{self.namespace}] 배치 저장 실패: {str(batch_error)}")
                except Exception as e:
                    logger.error(f"[{self.namespace}] 벡터 저장 중 오류 발생: {str(e)}")
                finally:
                    await self.async_index.close()
            else:
                # 비동기 인덱스가 없는 경우, 동기 메서드를 비동기적으로 실행
                for i in range(0, total_vectors, BATCH_SIZE):
                    batch = normalized_vectors[i:i + BATCH_SIZE]
                    try:
                        logger.info(f"[{self.namespace}] 벡터 배치 {i//BATCH_SIZE + 1}/{(total_vectors+BATCH_SIZE-1)//BATCH_SIZE} (크기: {len(batch)}) 저장 중")
                        # 동기 메서드를 비동기 스레드로 래핑
                        try:
                            await asyncio.to_thread(
                                self.index.upsert,
                                vectors=batch, 
                                namespace=self.namespace
                            )
                        except RuntimeError as e:
                            # 이벤트 루프가 없는 경우
                            if "no running event loop" in str(e):
                                logger.warning(f"[{self.namespace}] to_thread 중 이벤트 루프 없음, 동기 메서드로 폴백")
                                self.index.upsert(vectors=batch, namespace=self.namespace)
                            else:
                                raise
                        logger.info(f"[{self.namespace}] 벡터 배치 {i//BATCH_SIZE + 1} 저장 완료")
                    except Exception as batch_error:
                        # 오류 처리 코드는 변경 없이 유지
                        if "larger than the maximum supported size" in str(batch_error):
                            logger.warning(f"배치가 너무 큽니다. 더 작은 배치로 재시도합니다. 오류: {str(batch_error)}")
                            half_batch_size = len(batch) // 2
                            if half_batch_size == 0:
                                # 더 이상 나눌 수 없으면 개별 처리
                                for single_vector in batch:
                                    try:
                                        try:
                                            await asyncio.to_thread(
                                                self.index.upsert,
                                                vectors=[single_vector], 
                                                namespace=self.namespace
                                            )
                                        except RuntimeError as e:
                                            # 이벤트 루프가 없는 경우
                                            if "no running event loop" in str(e):
                                                logger.warning(f"[{self.namespace}] 단일 벡터 to_thread 중 이벤트 루프 없음, 동기 메서드로 폴백")
                                                self.index.upsert(vectors=[single_vector], namespace=self.namespace)
                                            else:
                                                raise
                                        logger.info(f"[{self.namespace}] 단일 벡터 저장 완료")
                                    except Exception as single_error:
                                        logger.error(f"[{self.namespace}] 단일 벡터 저장 실패: {str(single_error)}")
                            else:
                                # 반으로 나누어 처리
                                first_half = batch[:half_batch_size]
                                second_half = batch[half_batch_size:]
                                try:
                                    try:
                                        await asyncio.to_thread(
                                            self.index.upsert,
                                            vectors=first_half, 
                                            namespace=self.namespace
                                        )
                                    except RuntimeError as e:
                                        # 이벤트 루프가 없는 경우
                                        if "no running event loop" in str(e):
                                            logger.warning(f"[{self.namespace}] 첫 번째 절반 배치 to_thread 중 이벤트 루프 없음, 동기 메서드로 폴백")
                                            self.index.upsert(vectors=first_half, namespace=self.namespace)
                                        else:
                                            raise
                                    logger.info(f"[{self.namespace}] 첫 번째 절반 배치 저장 완료")
                                except Exception as e:
                                    logger.error(f"[{self.namespace}] 첫 번째 절반 배치 저장 실패: {str(e)}")
                                
                                try:
                                    try:
                                        await asyncio.to_thread(
                                            self.index.upsert,
                                            vectors=second_half, 
                                            namespace=self.namespace
                                        )
                                    except RuntimeError as e:
                                        # 이벤트 루프가 없는 경우
                                        if "no running event loop" in str(e):
                                            logger.warning(f"[{self.namespace}] 두 번째 절반 배치 to_thread 중 이벤트 루프 없음, 동기 메서드로 폴백")
                                            self.index.upsert(vectors=second_half, namespace=self.namespace)
                                        else:
                                            raise
                                    logger.info(f"[{self.namespace}] 두 번째 절반 배치 저장 완료")
                                except Exception as e:
                                    logger.error(f"[{self.namespace}] 두 번째 절반 배치 저장 실패: {str(e)}")
                        else:
                            # 크기 외 다른 오류는 기록하고 계속 진행
                            logger.error(f"[{self.namespace}] 배치 저장 실패: {str(batch_error)}")
            
            logger.info(f"[{self.namespace}] 전체 벡터 {total_vectors}개 저장 완료")
            return True

        except Exception as e:
            logger.error(f"[{self.namespace}] 벡터 저장 실패: {str(e)}")
            return False

    async def add_documents(self, documents: List[Dict]) -> bool:
        """문서를 벡터 스토어에 추가 (비동기)"""
        await self.ensure_initialized()
        try:
            # 비동기 인덱스가 사용 가능한지 확인
            if hasattr(self, 'async_index') and self.async_index is not None:
                # 네이티브 비동기 API 사용
                await self.async_index.upsert(
                    namespace=self.namespace,
                    vectors=documents
                )
                logger.info(f"[{self.namespace}] 문서 {len(documents)}개 추가 완료")
                return True
            else:
                # 폴백: 동기 메서드를 비동기적으로 실행
                await asyncio.to_thread(self.index.upsert, vectors=documents, namespace=self.namespace)
                logger.info(f"[{self.namespace}] 문서 {len(documents)}개 추가 완료 (동기 메서드 사용)")
                return True
        except Exception as e:
            logger.error(f"문서 추가 중 오류 발생: {str(e)}")
            return False
        
    def delete_documents_by_embedding_id(self, embed_ids: List[str]) -> bool:
        """벡터 스토어에서 문서 삭제"""
        try:
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
        """벡터 스토어에서 문서 삭제 (비동기)"""
        await self.ensure_initialized()
        await self.get_async_index()
        try:
            
            # 비동기 인덱스가 사용 가능한지 확인
            if hasattr(self, 'async_index') and self.async_index is not None:
                # 네이티브 비동기 API 사용
                await self.async_index.delete(
                    ids=embed_ids, 
                    namespace=self.namespace
                )
                logger.info(f"[{self.namespace}] ID별 문서 삭제 성공 (IDs: {embed_ids})")
                return True
            else:
                # 폴백: 동기 메서드를 비동기적으로 실행
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
        finally:
            await self.async_index.close()

    async def update_documents(self, documents: List[Dict]) -> bool:
        """벡터 스토어의 문서 업데이트 (비동기)"""
        await self.ensure_initialized()
        try:
            # 비동기 인덱스가 사용 가능한지 확인
            if hasattr(self, 'async_index') and self.async_index is not None:
                # 네이티브 비동기 API 사용
                await self.async_index.upsert(
                    vectors=documents, 
                    namespace=self.namespace
                )
                return True
            else:
                # 폴백: 동기 메서드를 비동기적으로 실행
                await asyncio.to_thread(self.index.upsert, vectors=documents, namespace=self.namespace)
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
        await self.ensure_initialized()
        await self.get_async_index()
        try:
            if not self.namespace:
                logger.warning("네임스페이스가 지정되지 않았습니다.")
                return False
            
            logger.info(f"[{self.namespace}] 네임스페이스 전체 삭제 시작 (Async)")
            
            # 비동기 인덱스가 사용 가능한지 확인
            if hasattr(self, 'async_index') and self.async_index is not None:
                # 네이티브 비동기 API 사용
                await self.async_index.delete(
                    delete_all=True, 
                    namespace=self.namespace
                )
                logger.info(f"[{self.namespace}] 네임스페이스 전체 삭제 완료 (Async)")
                return True
            else:
                # 폴백: 동기 메서드를 비동기적으로 실행
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
        finally:
            await self.async_index.close()
            
    def delete_documents_by_metadata(self, metadata_key: str, metadata_value: any) -> bool:
        """
        특정 메타데이터 키와 값을 기준으로 문서를 삭제합니다.
        
        Args:
            metadata_key (str): 삭제 기준이 될 메타데이터 키
            metadata_value (any): 삭제 기준이 될 메타데이터 값
            
        Returns:
            bool: 삭제 성공 여부
        """
        try:
            if not self.namespace:
                logger.warning("네임스페이스가 지정되지 않았습니다.")
                return False
                
            # 메타데이터 필터 생성
            metadata_filter = {metadata_key: metadata_value}
            
            logger.info(f"[{self.namespace}] 메타데이터 기준 삭제 시작: {metadata_key}={metadata_value}")
            result = self.index.delete(filter=metadata_filter, namespace=self.namespace)
            
            # 반환값이 빈 딕셔너리인지 확인하여 삭제 성공 여부를 판단
            if isinstance(result, dict) and result == {}:
                logger.info(f"[{self.namespace}] 메타데이터 기준 삭제 완료: {metadata_key}={metadata_value}")
                return True
            else:
                logger.error(f"[{self.namespace}] 메타데이터 기준 삭제 결과 값이 유효하지 않음: {result}")
                return False
                
        except Exception as e:
            logger.error(f"[{self.namespace}] 메타데이터 기준 삭제 중 오류 발생: {str(e)}", exc_info=True)
            return False
            
    async def delete_documents_by_metadata_async(self, metadata_key: str, metadata_value: any) -> bool:
        """
        특정 메타데이터 키와 값을 기준으로 문서를 비동기적으로 삭제합니다.
        
        Args:
            metadata_key (str): 삭제 기준이 될 메타데이터 키
            metadata_value (any): 삭제 기준이 될 메타데이터 값
            
        Returns:
            bool: 삭제 성공 여부
        """
        await self.ensure_initialized()
        await self.get_async_index()

        try:
            if not self.namespace:
                logger.warning("네임스페이스가 지정되지 않았습니다.")
                return False
                
            # 메타데이터 필터 생성
            metadata_filter = {metadata_key: metadata_value}
            
            logger.info(f"[{self.namespace}] 메타데이터 기준 삭제 시작 (Async): {metadata_key}={metadata_value}")
            
            # 비동기 인덱스가 사용 가능한지 확인
            if hasattr(self, 'async_index') and self.async_index is not None:
                # 네이티브 비동기 API 사용
                await self.async_index.delete(
                    filter=metadata_filter, 
                    namespace=self.namespace
                )
                
                logger.info(f"[{self.namespace}] 메타데이터 기준 삭제 완료 (Async): {metadata_key}={metadata_value}")
                return True
            else:
                # 폴백: 동기 메서드를 비동기적으로 실행
                result = await asyncio.to_thread(self.index.delete, filter=metadata_filter, namespace=self.namespace)
                
                # 반환값이 빈 딕셔너리인지 확인하여 삭제 성공 여부를 판단
                if isinstance(result, dict) and result == {}:
                    logger.info(f"[{self.namespace}] 메타데이터 기준 삭제 완료 (Async): {metadata_key}={metadata_value}")
                    return True
                else:
                    logger.error(f"[{self.namespace}] 메타데이터 기준 삭제 결과 값이 유효하지 않음 (Async): {result}")
                    return False
                
        except Exception as e:
            logger.error(f"[{self.namespace}] 메타데이터 기준 삭제 중 오류 발생 (Async): {str(e)}", exc_info=True)
            return False
        finally:
            await self.async_index.close()
            
    def delete_documents_by_metadata_condition(self, metadata_conditions: Dict[str, any]) -> bool:
        """
        여러 메타데이터 조건을 기준으로 문서를 삭제합니다.
        
        Args:
            metadata_conditions (Dict[str, any]): 삭제 기준이 될 메타데이터 키-값 쌍의 딕셔너리
            
        Returns:
            bool: 삭제 성공 여부
        """
        try:
            if not self.namespace:
                logger.warning("네임스페이스가 지정되지 않았습니다.")
                return False
                
            if not metadata_conditions:
                logger.warning("메타데이터 조건이 지정되지 않았습니다.")
                return False
                
            logger.info(f"[{self.namespace}] 복합 메타데이터 기준 삭제 시작: {metadata_conditions}")
            result = self.index.delete(filter=metadata_conditions, namespace=self.namespace)
            
            # 반환값이 빈 딕셔너리인지 확인하여 삭제 성공 여부를 판단
            if isinstance(result, dict) and result == {}:
                logger.info(f"[{self.namespace}] 복합 메타데이터 기준 삭제 완료: {metadata_conditions}")
                return True
            else:
                logger.error(f"[{self.namespace}] 복합 메타데이터 기준 삭제 결과 값이 유효하지 않음: {result}")
                return False
                
        except Exception as e:
            logger.error(f"[{self.namespace}] 복합 메타데이터 기준 삭제 중 오류 발생: {str(e)}", exc_info=True)
            return False
            
    async def delete_documents_by_metadata_condition_async(self, metadata_conditions: Dict[str, any]) -> bool:
        """
        여러 메타데이터 조건을 기준으로 문서를 삭제 (비동기)
        
        Args:
            metadata_conditions (Dict[str, any]): 삭제 기준이 될 메타데이터 키-값 쌍의 딕셔너리
            
        Returns:
            bool: 삭제 성공 여부
        """
        await self.ensure_initialized()
        await self.get_async_index()
        try:
            if not self.namespace:
                logger.warning("네임스페이스가 지정되지 않았습니다.")
                return False
                
            if not metadata_conditions:
                logger.warning("메타데이터 조건이 지정되지 않았습니다.")
                return False
                
            logger.info(f"[{self.namespace}] 복합 메타데이터 기준 삭제 시작: {metadata_conditions}")
            
            # 비동기 인덱스가 사용 가능한지 확인
            if hasattr(self, 'async_index') and self.async_index is not None:
                # 네이티브 비동기 API 사용
                await self.async_index.delete(
                    filter=metadata_conditions, 
                    namespace=self.namespace
                )
                
                logger.info(f"[{self.namespace}] 복합 메타데이터 기준 삭제 완료: {metadata_conditions}")
                return True
            else:
                # 폴백: 동기 메서드를 비동기적으로 실행
                result = await asyncio.to_thread(
                    self.index.delete,
                    filter=metadata_conditions,
                    namespace=self.namespace
                )
                
                # 반환값이 빈 딕셔너리인지 확인하여 삭제 성공 여부를 판단
                if isinstance(result, dict) and result == {}:
                    logger.info(f"[{self.namespace}] 복합 메타데이터 기준 삭제 완료 (폴백): {metadata_conditions}")
                    return True
                else:
                    logger.error(f"[{self.namespace}] 복합 메타데이터 기준 삭제 결과 값이 유효하지 않음: {result}")
                    return False
                
        except Exception as e:
            logger.error(f"[{self.namespace}] 복합 메타데이터 기준 삭제 중 오류 발생: {str(e)}")
            return False
        finally:
            await self.async_index.close()

    async def close(self):
        """
        리소스를 정리하고 클라이언트 세션을 닫습니다.
        """
        if hasattr(self, '_closed') and self._closed:
            return
        
        # 비동기 인덱스 닫기
        if hasattr(self, 'async_index') and self.async_index is not None:
            try:
                # Pinecone 6.0+ 비동기 인덱스 세션 닫기
                await self.async_index.close()
                #logger.info(f"[{self.namespace}] Pinecone 비동기 인덱스 세션을 정상적으로 닫았습니다.")
            except Exception as e:
                logger.error(f"[{self.namespace}] Pinecone 비동기 인덱스 세션을 닫는 중 오류 발생: {str(e)}")
        
        # 동기 클라이언트 닫기
        if self.pinecone_client is not None:
            try:
                # Pinecone 클라이언트 세션 닫기
                if hasattr(self.pinecone_client, 'close'):
                    self.pinecone_client.close()
                    logger.info(f"[{self.namespace}] Pinecone 클라이언트 세션을 정상적으로 닫았습니다.")
            except Exception as e:
                logger.error(f"[{self.namespace}] Pinecone 클라이언트 세션을 닫는 중 오류 발생: {str(e)}")
        
        # 임베딩 모델 제공자의 리소스 정리
        # try:
        #     if hasattr(self, 'embedding_model_provider') and self.embedding_model_provider:
        #         # 비동기 리소스 정리 (다양한 메서드명 시도)
        #         if hasattr(self.embedding_model_provider, 'aclose') and callable(getattr(self.embedding_model_provider, 'aclose')):
        #             await self.embedding_model_provider.aclose()
        #             logger.info("임베딩 모델 제공자의 비동기 리소스를 정상적으로 닫았습니다.")
        #         elif hasattr(self.embedding_model_provider, 'close_async') and callable(getattr(self.embedding_model_provider, 'close_async')):
        #             await self.embedding_model_provider.close_async()
        #             logger.info("임베딩 모델 제공자의 비동기 리소스를 정상적으로 닫았습니다.")
        #         elif hasattr(self.embedding_model_provider, 'close') and callable(getattr(self.embedding_model_provider, 'close')):
        #             # 동기 close 메서드를 비동기적으로 실행
        #             await asyncio.to_thread(self.embedding_model_provider.close)
        #             logger.info("임베딩 모델 제공자의 리소스를 정상적으로 닫았습니다.")
        # except Exception as e:
        #     logger.error(f"임베딩 모델 제공자의 리소스 정리 중 오류 발생: {str(e)}")
            
        # 임베딩 객체의 리소스 정리 - embedding_obj_async
        try:
            # 비동기 임베딩 객체 정리
            if hasattr(self, 'embedding_obj_async') and self.embedding_obj_async:
                if hasattr(self.embedding_obj_async, 'aclose') and callable(getattr(self.embedding_obj_async, 'aclose')):
                    await self.embedding_obj_async.aclose()
                    #logger.info(f"[{self.namespace}] 비동기 임베딩 객체의 리소스를 정상적으로 닫았습니다.")
                elif hasattr(self.embedding_obj_async, 'client') and hasattr(self.embedding_obj_async.client, 'aclose'):
                    await self.embedding_obj_async.client.aclose()
                    #logger.info(f"[{self.namespace}] 비동기 임베딩 객체 클라이언트 리소스를 정상적으로 닫았습니다.")
                    
            # 동기 임베딩 객체 정리
            if hasattr(self, 'embedding_obj') and self.embedding_obj:
                if hasattr(self.embedding_obj, 'close') and callable(getattr(self.embedding_obj, 'close')):
                    self.embedding_obj.close()
                    #logger.info(f"[{self.namespace}] 동기 임베딩 객체의 리소스를 정상적으로 닫았습니다.")
                elif hasattr(self.embedding_obj, 'client') and hasattr(self.embedding_obj.client, 'close'):
                    self.embedding_obj.client.close()
                    #logger.info(f"[{self.namespace}] 동기 임베딩 객체 클라이언트 리소스를 정상적으로 닫았습니다.")
        except Exception as e:
            logger.error(f"[{self.namespace}] 임베딩 객체의 리소스 정리 중 오류 발생: {str(e)}")
        
        # aiohttp 세션 정리 시도 (주요 클라이언트 객체에 직접 접근)
        try:
            # OpenAI 임베딩 객체가 사용하는 세션 정리 시도
            for attr_name in ['embedding_obj_async', 'embedding_obj', 'embedding_model_provider']:
                if hasattr(self, attr_name):
                    obj = getattr(self, attr_name)
                    if obj is not None:
                        # client 속성 확인
                        if hasattr(obj, 'client'):
                            client_obj = obj.client
                            # 세션 닫기 시도
                            if hasattr(client_obj, 'session') and hasattr(client_obj.session, 'close'):
                                if asyncio.iscoroutinefunction(client_obj.session.close):
                                    await client_obj.session.close()
                                else:
                                    client_obj.session.close()
                                logger.info(f"[{self.namespace}] {attr_name}의 클라이언트 세션을 정상적으로 닫았습니다.")
        except Exception as e:
            logger.error(f"aiohttp 세션 정리 중 오류 발생: {str(e)}")
        
        # 모든 활성 aiohttp 세션 정리
        try:
            await cleanup_aiohttp_sessions()
        except Exception as e:
            logger.error(f"전역 aiohttp 세션 정리 중 오류 발생: {str(e)}")
        
        # 마지막으로 임베딩 서비스 정리
        if hasattr(self, 'embedding_service'):
            try:
                if hasattr(self.embedding_service, 'aclose'):
                    await self.embedding_service.aclose()
                    logger.info(f"[{self.namespace}] 임베딩 서비스 비동기 리소스 정리 완료")
                elif hasattr(self.embedding_service, 'close'):
                    self.embedding_service.close()
                    logger.info(f"[{self.namespace}] 임베딩 서비스 리소스 정리 완료")
            except Exception as e:
                logger.error(f"임베딩 서비스 정리 중 오류 발생: {str(e)}")
        
        self._closed = True
    
    def __del__(self):
        """
        객체가 소멸될 때 세션을 닫기 위한 시도
        (비동기 작업은 __del__에서 직접 실행할 수 없으므로 동기적으로 닫을 수 있는 리소스만 처리)
        """
        if not hasattr(self, '_closed') or not self._closed:
            # 개발 환경에서 제대로 close 호출을 추적하기 위한 경고
            #logger.warning("VectorStoreManager 객체가 제대로 close()되지 않고 소멸되었습니다. 리소스 누수가 발생할 수 있습니다.")
            
            # 동기적으로 닫을 수 있는 리소스 정리
            try:
                # Pinecone 클라이언트 세션 닫기
                if hasattr(self, 'pinecone_client') and self.pinecone_client is not None:
                    if hasattr(self.pinecone_client, 'close'):
                        self.pinecone_client.close()
                        #logger.info("Pinecone 클라이언트 세션을 __del__에서 정상적으로 닫았습니다.")
            except Exception as e:
                logger.error(f"__del__에서 Pinecone 세션 닫기 실패: {str(e)}")
            
            # # 동기 임베딩 객체 정리 시도
            # try:
            #     if hasattr(self, 'embedding_obj') and self.embedding_obj is not None:
            #         if hasattr(self.embedding_obj, 'close') and callable(getattr(self.embedding_obj, 'close')):
            #             self.embedding_obj.close()
            #             #logger.info("동기 임베딩 객체를 __del__에서 정상적으로 닫았습니다.")
            #         elif hasattr(self.embedding_obj, 'client') and hasattr(self.embedding_obj.client, 'close'):
            #             self.embedding_obj.client.close()
            #             #logger.info("동기 임베딩 객체 클라이언트를 __del__에서 정상적으로 닫았습니다.")
            # except Exception as e:
            #     logger.error(f"__del__에서 임베딩 객체 닫기 실패: {str(e)}")
            
            # 임베딩 모델 제공자 정리 시도
            try:
                if hasattr(self, 'embedding_model_provider') and self.embedding_model_provider is not None:
                    if hasattr(self.embedding_model_provider, 'close') and callable(getattr(self.embedding_model_provider, 'close')):
                        self.embedding_model_provider.close()
                        #logger.info("임베딩 모델 제공자를 __del__에서 정상적으로 닫았습니다.")
            except Exception as e:
                logger.error(f"__del__에서 임베딩 모델 제공자 닫기 실패: {str(e)}")
                
            # 비동기 리소스에 대한 경고 메시지
            if hasattr(self, 'async_index') and self.async_index is not None:
                logger.warning("VectorStoreManager 객체의 비동기 인덱스 세션이 닫히지 않았습니다. 리소스 누수가 발생할 수 있습니다.")
                
            if hasattr(self, 'embedding_obj_async') and self.embedding_obj_async is not None:
                logger.warning("VectorStoreManager 객체의 비동기 임베딩 객체 세션이 닫히지 않았습니다. 리소스 누수가 발생할 수 있습니다.") 

    async def get_async_index(self):
        """비동기 인덱스가 필요할 때만 생성하고 반환"""
        if not hasattr(self, 'async_index') or self.async_index is None:
            try:
                index_details = self.pinecone_client.describe_index(self.embedding_model_config.name)
                host_url = index_details.host
                self.async_index = self.pinecone_client.IndexAsyncio(host=host_url)
                logger.info(f"[{self.namespace}] 비동기 Pinecone 인덱스 생성 성공")
                print(f"[{self.namespace}] 비동기 Pinecone 인덱스 생성 성공.print")
            except Exception as e:
                logger.error(f"[{self.namespace}] 비동기 인덱스 생성 실패: {str(e)}")
                return None
        return self.async_index