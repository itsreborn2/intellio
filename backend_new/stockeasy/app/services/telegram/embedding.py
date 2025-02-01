from typing import List, Dict, Any, Optional
import numpy as np
from openai import OpenAI, AsyncOpenAI
from pinecone import Pinecone, PodSpec, ServerlessSpec
from datetime import datetime
from dataclasses import dataclass

import logging
import re
from app.core.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.utils.common import measure_time_async
import openai
from openai import OpenAIError, Timeout
from app.services.embedding_models import EmbeddingModelManager, EmbeddingProviderFactory, EmbeddingModelConfig, EmbeddingModelType
from app.models.telegram_message import TelegramMessage

logger = logging.getLogger(__name__)

@dataclass
class TelegramMessageMetadata:
    """텔레그램 메시지 메타데이터"""
    channel_id: str              # 채널 ID
    channel_title: str           # 채널 이름
    message_id: int              # 메시지 ID
    message_type: str            # 메시지 타입 (text, photo, video 등)
    sender_id: Optional[str]     # 발신자 ID (있는 경우)
    sender_name: Optional[str]   # 발신자 이름 (있는 경우)
    created_at: datetime         # 메시지 생성 시간
    has_media: bool             # 미디어 첨부 여부

class EmbeddingService:
    def __init__(self, index_name: str = None):
        """
        임베딩 서비스 초기화
        
        Args:
            index_name (str, optional): 사용할 Pinecone 인덱스 이름. 
                                      지정하지 않으면 현재 모델 이름을 사용
        """
        self.batch_size = 5  # 임베딩 처리의 안정성을 위해 배치 크기 축소 (20 -> 5)
        self.model_manager = EmbeddingModelManager()
        self.current_model = self.model_manager.get_model(EmbeddingModelType.GOOGLE_MULTI_LANG) # 구글 다국어 모델

        # 현재 모델에 맞는 제공자 생성
        self.provider = EmbeddingProviderFactory.create_provider(
            self.current_model.provider,
            self.current_model.name
        )
        
        # 인덱스 이름 설정
        self.index_name = index_name if index_name else self.current_model.name
        self.create_pinecone_index(self.current_model)

    def create_pinecone_index(self, embedding_model: EmbeddingModelConfig):
        """Pinecone 인덱스 생성 또는 연결"""
        pinecone = Pinecone(api_key=settings.PINECONE_API_KEY)
        
        try:
            self.pinecone_index = pinecone.Index(self.index_name)
            logger.info(f"Pinecone 인덱스 {self.index_name} 설정 완료")
        except:
            logger.info(f"Pinecone 인덱스 {self.index_name} 없음. 생성 중...")
            try:
                # 새 인덱스 생성
                pinecone.create_index(
                    name=self.index_name,
                    dimension=embedding_model.dimension,  # 임베딩 차원수
                    metric="cosine",                     # 유사도 측정 방식
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-west-2"
                    )
                )
                self.pinecone_index = pinecone.Index(self.index_name)
                logger.info(f"Pinecone 인덱스 {self.index_name} 생성 완료")
            except Exception as e:
                logger.error(f"Pinecone 인덱스 생성 실패: {str(e)}")
                raise

    def _create_telegram_metadata(self, message: TelegramMessage) -> dict:
        """텔레그램 메시지의 메타데이터를 생성합니다.
        
        Args:
            message (TelegramMessage): 텔레그램 메시지
            
        Returns:
            dict: 메타데이터 딕셔너리
        """
        return {
            'message_id': message.message_id,
            'channel_id': message.channel_id,
            'channel_name': message.channel_name,
            'created_at': message.created_at.isoformat(),
            'has_document': message.has_document,
            'document_name': message.document_name if message.has_document else None
        }
        
    def _prepare_text_for_embedding(self, message: TelegramMessage) -> Optional[str]:
        """임베딩을 위한 텍스트를 준비합니다.
        
        메시지 텍스트에 문서 정보를 추가하고 유효성을 검사합니다.
        중복된 줄바꿈을 하나로 통일합니다.
        
        Args:
            message (TelegramMessage): 텔레그램 메시지
            
        Returns:
            Optional[str]: 임베딩할 텍스트. 유효하지 않은 경우 None 반환
        """
        if not message.message_text or len(message.message_text.strip()) < 10:
            logger.warning(f"텍스트가 너무 짧거나 비어있음 (message_id: {message.message_id}, 길이: {len(message.message_text) if message.message_text else 0})")
            return None
            
        # 연속된 줄바꿈을 하나로 통일
        text = re.sub(r'\n{2,}', '\n', message.message_text)
        
        # 문서가 있는 경우 문서 정보 추가
        if message.has_document and message.document_name:
            text = f"{text}\n[첨부파일: {message.document_name}]"
            
        return text.strip()
        
    def get_pinecone_index(self):
        return self.pinecone_index
    
    def set_model(self, model_name: str) -> None:
        """임베딩 모델 변경"""
        model = self.model_manager.get_model(model_name)
        if model:
            self.current_model = model
            # 새로운 모델에 맞는 제공자로 교체
            self.provider = EmbeddingProviderFactory.create_provider(
                model.provider,
                model.name
            )
            self.create_pinecone_index(model)
        else:
            raise ValueError(f"Unknown model: {model_name}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """텍스트 배치의 임베딩을 생성"""
        try:
            # texts는 사용자의 프롬프트 1개 일수도 있고, 문서의 청크 여러개 일수도 있음.
            if not texts:
                return []
                
            # 텍스트 유효성 검사
            validated_texts = []
            for text in texts:
                if not text or not text.strip():
                    logger.warning("빈 텍스트 건너뜀")
                    continue
                validated_texts.append(text.strip())
            
            if not validated_texts:
                return []
            
            # 제공자를 통해 임베딩 생성
            embeddings = await self.provider.create_embeddings_async(validated_texts)
            
            # 임베딩 품질 검사
            for i, emb in enumerate(embeddings):
                if not emb or len(emb) != self.current_model.dimension:
                    logger.error(f"잘못된 임베딩 차원 (인덱스 {i}): {len(emb) if emb else 0}")
                    continue
            
            return embeddings
            
        except Exception as e:
            logger.error(f"임베딩 생성 중 오류 발생: {str(e)}")
            raise

    @retry(
        stop=stop_after_attempt(3),  # 최대 3번 시도
        wait=wait_exponential(multiplier=1, min=4, max=10),  # 지수 백오프
        retry=retry_if_exception_type(Timeout)  # 타임아웃 예외 시 재시도
    )
    def create_embeddings_batch_sync(self, texts: List[str]) -> List[List[float]]:
        """텍스트 배치의 임베딩을 생성 (동기 버전)"""
        try:
            if not texts:
                return []
                
            # 텍스트 유효성 검사
            validated_texts = []
            for text in texts:
                if not text or not text.strip():
                    logger.warning("빈 텍스트 건너뜀")
                    continue
                validated_texts.append(text.strip())
            
            if not validated_texts:
                return []
            
            # 제공자를 통해 임베딩 생성
            embeddings = self.provider.create_embeddings(validated_texts)
            
            # 임베딩 품질 검사
            for i, emb in enumerate(embeddings):
                if not emb or len(emb) != self.current_model.dimension:
                    logger.error(f"잘못된 임베딩 차원 (인덱스 {i}): {len(emb) if emb else 0}")
                    continue
            
            return embeddings
            
        except Exception as e:
            logger.error(f"임베딩 생성 중 오류 발생: {str(e)}")
            raise
    
    def store_vectors(self, _vectors: List[Dict]) -> bool:
        """벡터를 Pinecone에 저장"""
        try:
            if not _vectors:
                logger.warning("저장할 벡터가 없습니다")
                return False

            # 벡터 저장
            logger.info(f"벡터 {len(_vectors)}개 저장 중")
            self.pinecone_index.upsert(vectors=_vectors)
            logger.info(f"벡터 {len(_vectors)}개 저장 완료")
            return True

        except Exception as e:
            logger.error(f"벡터 저장 실패: {str(e)}")
            return False
    
    async def get_single_embedding_async(self, query: str) -> List[float]:
        """단일 텍스트에 대한 임베딩을 생성하고 검증"""
        try:
            if not query or not query.strip():
                logger.error("빈 쿼리 문자열")
                raise ValueError("쿼리 문자열이 비어있습니다")

            embeddings = await self.provider.create_embeddings_async([query.strip()])
            
            # 임베딩 결과 검증
            if not embeddings or len(embeddings) == 0:
                logger.error("임베딩 생성 결과가 비어있음")
                raise ValueError("임베딩 생성 실패")
                
            embedding = embeddings[0]
            
            # 임베딩 벡터 검증
            if not isinstance(embedding, list) or len(embedding) != self.current_model.dimension:
                logger.error(f"잘못된 임베딩 형식 또는 차원: {len(embedding) if isinstance(embedding, list) else type(embedding)}")
                raise ValueError("잘못된 임베딩 형식")
            
            return embedding
        except Exception as e:
                logger.error(f"단일 임베딩 생성 실패: {str(e)}")
                raise
    def get_single_embedding(self, query: str) -> List[float]:
        """단일 텍스트에 대한 임베딩을 생성하고 검증 (동기 버전)"""
        try:
            if not query or not query.strip():
                logger.error("빈 쿼리 문자열")
                raise ValueError("쿼리 문자열이 비어있습니다")

            embeddings = self.provider.create_embeddings([query.strip()])
            
            # 임베딩 결과 검증
            if not embeddings or len(embeddings) == 0:
                logger.error("임베딩 생성 결과가 비어있음")
                raise ValueError("임베딩 생성 실패")
                
            embedding = embeddings[0]
            
            # 임베딩 벡터 검증
            if not isinstance(embedding, list) or len(embedding) != self.current_model.dimension:
                logger.error(f"잘못된 임베딩 형식 또는 차원: {len(embedding) if isinstance(embedding, list) else type(embedding)}")
                raise ValueError("잘못된 임베딩 형식")
                
            return embedding
            
        except Exception as e:
            logger.error(f"단일 임베딩 생성 실패: {str(e)}")
            raise
            
    async def create_embedding(self, text: str) -> List[float]:
        """OpenAI API를 사용하여 텍스트의 임베딩 생성"""
        try:
            if not text or not text.strip():
                logger.warning("Empty text provided for embedding")
                return []
                
            response = await self.async_client.embeddings.create(
                model="text-embedding-ada-002",  
                input=text.strip()
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Error creating embedding: {str(e)}")
            raise
    @measure_time_async
    async def search_similar(
        self, 
        query: str, 
        top_k: int = 7,
        min_score: float = 0.5,
        use_context: bool = True,
        context_window: int = 2,
        document_ids: List[str] = None
    ) -> List[Dict[str, Any]]:
        """질문과 유사한 문서 청크를 검색합니다."""
        try:
            logger.info(f"유사 문서 검색 시작 - 쿼리: {query}")
            
            # 쿼리 임베딩 생성
            query_embedding = await self.get_single_embedding_async(query)
            if not query_embedding:
                logger.error("쿼리 임베딩 생성 실패")
                return []
                
            # 필터 설정
            filter_dict = {}
            if document_ids:
                filter_dict["document_id"] = {"$in": document_ids}
                logger.debug(f"문서 필터 설정: {document_ids}")

            # Pinecone 검색 실행
            logger.info(f"Pinecone 검색 시작 (top_k: {top_k}, min_score: {min_score})")
            try:
                search_response = self.pinecone_index.query(
                    namespace="",
                    vector=query_embedding,
                    top_k=top_k * 5,  # 필터링을 위해 더 많은 결과 요청
                    filter=filter_dict if filter_dict else None,
                    include_metadata=True
                )
                
                if not search_response.matches:
                    logger.warning("검색 결과 없음")
                    return []
                    
                logger.info(f"검색된 총 매치 수: {len(search_response.matches)}")
                for match in search_response.matches[:3]:
                    logger.info(f"매치 - ID: {match.id}, 점수: {match.score:.4f}")
                
                # 유사도 점수로 필터링
                filtered_results = [
                    match for match in search_response.matches 
                    if match.score >= min_score
                ]
                
                if not filtered_results:
                    logger.warning(f"최소 유사도({min_score}) 이상의 결과 없음")
                    return []
                
                logger.debug(f"필터링된 결과: {len(filtered_results)}개")
                
                # 상위 K개만 선택
                top_results = filtered_results[:top_k]
                
                # 결과 포맷팅
                formatted_results = []
                for match in top_results:
                    result = {
                        "id": match.id,
                        "score": getattr(match, 'score', 0),  # score 속성이 없으면 0 반환
                        "metadata": match.metadata
                    }
                    formatted_results.append(result)
                    logger.debug(f"매치 정보 - ID: {match.id}, 점수: {match.score:.4f}")
                
                # score 기준으로 내림차순 정렬
                formatted_results.sort(key=lambda x: x["score"], reverse=True)
                return formatted_results
                
            except Exception as e:
                logger.error(f"Pinecone 검색 실패: {str(e)}")
                return []
            
        except Exception as e:
            logger.error(f"유사 문서 검색 실패: {str(e)}")
            return []

    async def _add_context_chunks(
        self,
        chunks: List[Dict[str, Any]],
        context_window: int
    ) -> List[Dict[str, Any]]:
        """주변 청크의 문맥을 추가"""
        context_chunks = []
        
        for chunk in chunks:
            doc_id = chunk["metadata"].get("document_id", "")
            chunk_idx = chunk["metadata"].get("chunk_index", 0)
            
            # 현재 청크 추가
            context_chunks.append(chunk)
            
            try:
                # 이전 청크들 가져오기
                start_idx = max(0, chunk_idx - context_window)
                prev_chunks = await self._get_document_chunks_by_range(
                    doc_id, start_idx, chunk_idx
                )
                context_chunks.extend(prev_chunks)
                
                # 다음 청크들 가져오기
                next_chunks = await self._get_document_chunks_by_range(
                    doc_id, chunk_idx + 1, chunk_idx + context_window + 1
                )
                context_chunks.extend(next_chunks)
                
            except Exception as e:
                logger.warning(f"문맥 청크 추가 실패: {str(e)}")
                continue
        
        # 중복 제거 및 정렬
        unique_chunks = {chunk["id"]: chunk for chunk in context_chunks}
        return list(unique_chunks.values())
        
    async def _get_document_chunks_by_range(
        self,
        doc_id: str,
        start_idx: int,
        end_idx: int
    ) -> List[Dict[str, Any]]:
        """문서의 특정 범위 청크 조회"""
        try:
            # 범위 검증
            if start_idx >= end_idx:
                return []
                
            # Pinecone 쿼리
            results = self.pinecone_index.query(
                vector=[0.0] * 1536,  # 더미 벡터
                top_k=max(1, end_idx - start_idx),  # 최소 1 보장
                include_metadata=True,
                filter={
                    "document_id": doc_id,
                    "chunk_index": {"$gte": start_idx, "$lt": end_idx}
                }
            )
            
            chunks = []
            for match in results.matches:
                chunks.append({
                    "id": match.id,
                    "score": 0.0,  # 문맥 청크는 점수 0으로 설정
                    "content": match.metadata.get("text", ""),
                    "metadata": match.metadata
                })
            
            # 청크 인덱스로 정렬
            chunks.sort(key=lambda x: x["metadata"].get("chunk_index", 0))
            return chunks
            
        except Exception as e:
            logger.error(f"청크 범위 조회 실패: {str(e)}")
            return []

    async def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """특정 문서의 모든 청크를 가져옵니다."""
        try:
            # 문서 ID로 필터링하여 모든 청크 검색
            results = self.pinecone_index.query(
                vector=[0] * 1536,  # 더미 벡터
                top_k=10000,  # 충분히 큰 값
                include_metadata=True,
                filter={"document_id": doc_id}
            )
            
            # 결과 형식화
            chunks = []
            for match in results.matches:
                chunk = {
                    "id": match.id,
                    "content": match.metadata.get("text", ""),
                    "metadata": match.metadata
                }
                chunks.append(chunk)
                
            return chunks
            
        except Exception as e:
            logger.error(f"문서 청크 조회 실패 (문서 ID: {doc_id}): {str(e)}")
            return []

    async def delete_embeddings(self, embedding_ids: List[str]) -> None:
        """임베딩 삭제"""
        try:
            if not embedding_ids:
                return
                
            # Pinecone에서 임베딩 삭제
            self.pinecone_index.delete(ids=embedding_ids)
            logger.info(f"임베딩 삭제 완료: {len(embedding_ids)}개")
            
        except Exception as e:
            logger.error(f"임베딩 삭제 실패: {str(e)}")

    async def clear_index(self) -> None:
        """인덱스의 모든 벡터 삭제"""
        try:
            self.pinecone_index.delete(delete_all=True)
            logger.info("Pinecone 인덱스 초기화 완료")
        except Exception as e:
            logger.error(f"인덱스 초기화 중 오류 발생: {str(e)}")

    async def embed_telegram_message(self, message: TelegramMessage) -> bool:
        """
        단일 텔레그램 메시지 임베딩 처리

        Args:
            message (TelegramMessage): 임베딩할 텔레그램 메시지

        Returns:
            bool: 성공 여부
        """
        try:
            # 메타데이터 생성
            metadata = self._create_telegram_metadata(message)
            
            # 임베딩할 텍스트 준비 (문서 정보 포함)
            text = self._prepare_text_for_embedding(message)
            
            # 임베딩 생성
            embeddings = await self.create_embeddings_batch([text])
            if not embeddings:
                logger.error(f"임베딩 생성 실패: message_id={message.message_id}")
                return False
                
            # Pinecone에 저장
            success = await self.store_vectors(
                [{"id": str(message.message_id), "vector": embeddings[0], "metadata": metadata}]
            )
            
            if success:
                logger.info(f"메시지 임베딩 완료: message_id={message.message_id}")
                return True
            else:
                logger.error(f"벡터 DB 저장 실패: message_id={message.message_id}")
                return False
                
        except Exception as e:
            logger.error(f"메시지 임베딩 중 오류 발생: {str(e)}")
            return False

    async def embed_telegram_messages_batch(self, messages: List[TelegramMessage]) -> bool:
        """
        텔레그램 메시지 배치 임베딩 처리

        Args:
            messages (List[TelegramMessage]): 임베딩할 메시지 리스트

        Returns:
            bool: 전체 성공 여부
        """
        try:
            # 메시지 전처리 및 유효성 검사
            valid_messages = []
            for msg in messages:
                text = self._prepare_text_for_embedding(msg)
                if text:  # None이 아닌 경우만 추가
                    valid_messages.append((msg, text))
                    
            if not valid_messages:
                logger.warning("유효한 메시지가 없습니다")
                return True  # 실패가 아닌 것으로 처리
                
            # 텍스트 길이에 따라 배치 구성
            batches = []
            current_batch = []
            current_batch_tokens = 0
            
            for msg, text in valid_messages:
                # 토큰 수 추정 (대략적으로 단어 수의 1.5배)
                estimated_tokens = len(text.split()) * 1.5
                
                # 현재 배치에 추가할 수 있는지 확인
                if current_batch_tokens + estimated_tokens > 2000 or len(current_batch) >= self.batch_size:
                    batches.append(current_batch)
                    current_batch = []
                    current_batch_tokens = 0
                
                current_batch.append((msg, text))
                current_batch_tokens += estimated_tokens
            
            if current_batch:
                batches.append(current_batch)
            
            # 배치 단위로 처리
            for batch_idx, batch in enumerate(batches):
                try:
                    logger.info(f"배치 처리 중 ({batch_idx + 1}/{len(batches)}): {len(batch)}개 메시지")
                    
                    # 메타데이터 생성
                    metadatas = [self._create_telegram_metadata(msg) for msg, _ in batch]
                    texts = [text for _, text in batch]
                    
                    # 임베딩 생성
                    embeddings = await self.create_embeddings_batch(texts)
                    
                    if not embeddings:
                        logger.error(f"배치 임베딩 생성 실패 (배치 {batch_idx + 1})")
                        continue
                    
                    if len(embeddings) != len(batch):
                        logger.error(f"임베딩 결과 수 불일치 - 예상: {len(batch)}, 실제: {len(embeddings)}")
                        continue
                    
                    # Pinecone에 저장
                    vectors = [
                        {
                            "id": str(msg.message_id), 
                            "vector": emb, 
                            "metadata": meta
                        } 
                        for (msg, _), emb, meta in zip(batch, embeddings, metadatas)
                    ]
                    
                    success = await self.store_vectors(vectors)
                    if not success:
                        logger.error(f"배치 벡터 DB 저장 실패 (배치 {batch_idx + 1})")
                        continue
                        
                    logger.info(f"배치 {batch_idx + 1} 임베딩 완료: {len(batch)}개 메시지")
                    
                except Exception as e:
                    logger.error(f"배치 {batch_idx + 1} 처리 중 오류: {str(e)}")
                    continue
            
            return True
            
        except Exception as e:
            logger.error(f"배치 임베딩 중 오류 발생: {str(e)}")
            return False
