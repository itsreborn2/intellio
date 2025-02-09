from typing import List, Dict, Any, Optional
import numpy as np
from datetime import datetime
from dataclasses import dataclass

import logging
import re
from common.core.config import settings
from common.utils.util import measure_time_async
from common.services.embedding_models import    EmbeddingModelType
from common.services.embedding import EmbeddingService as CommonEmbeddingService
from common.services.vector_store_manager import VectorStoreManager

from stockeasy.models.telegram_message import TelegramMessage

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
    has_document: bool          # 문서 첨부 여부
    document_name: Optional[str] # 문서 이름 (있는 경우)
    document_gcs_path: Optional[str] # GCS 경로 (있는 경우)

class TelegramEmbeddingService(CommonEmbeddingService):
    """텔레그램 메시지 전용 임베딩 서비스"""

    def __init__(self, namespace: str = "telegram"):
        """
        Args:
            namespace (str): Pinecone 네임스페이스. 기본값은 "telegram"
        """
        super().__init__()
        self.namespace = namespace
        self.vector_store = VectorStoreManager(
            EmbeddingModelType.GOOGLE_MULTI_LANG,
            namespace=namespace
        )

    def _create_telegram_metadata(self, message: TelegramMessage) -> dict:
        """텔레그램 메시지의 메타데이터를 생성합니다.
        
        Args:
            message (TelegramMessage): 텔레그램 메시지
            
        Returns:
            dict: 메타데이터 딕셔너리
        """
        return {
            'message_id': str(message.message_id),
            'channel_id': message.channel_id,
            'channel_title': message.channel_title,
            'created_at': message.created_at.isoformat(),
            'has_document': message.has_document,
            'document_name': message.document_name if message.has_document else None,
            'document_gcs_path': message.document_gcs_path if message.has_document else None,
            'namespace': self.namespace
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
            logger.warning(f"텍스트가 너무 짧거나 비어있음 (message_id: {message.message_id})")
            return None
            
        # 연속된 줄바꿈을 하나로 통일
        text = re.sub(r'\n{2,}', '\n', message.message_text)
        
        # 문서가 있는 경우 문서 정보 추가
        if message.has_document and message.document_name:
            text = f"{text}\n[첨부파일: {message.document_name}]"
            
        return text.strip()

    async def embed_telegram_message(self, message: TelegramMessage) -> bool:
        """단일 텔레그램 메시지를 임베딩 처리합니다.

        Args:
            message (TelegramMessage): 임베딩할 텔레그램 메시지

        Returns:
            bool: 성공 여부
        """
        try:
            # 메타데이터 생성
            metadata = self._create_telegram_metadata(message)
            
            # 임베딩할 텍스트 준비
            text = self._prepare_text_for_embedding(message)
            if not text:
                return False
            
            # 임베딩 생성
            embeddings = await self.create_embeddings_batch([text])
            if not embeddings:
                logger.error(f"임베딩 생성 실패: message_id={message.message_id}")
                return False
                
            # 벡터 저장
            vector = {
                "id": str(message.message_id),
                "values": embeddings[0],
                "metadata": metadata
            }
            
            success = await self.vector_store.store_vectors_async([vector])
            
            if success:
                logger.info(f"메시지 임베딩 완료: message_id={message.message_id}")
                return True
            else:
                logger.error(f"벡터 저장 실패: message_id={message.message_id}")
                return False
                
        except Exception as e:
            logger.error(f"메시지 임베딩 중 오류 발생: {str(e)}")
            return False

    async def embed_telegram_messages_batch(self, messages: List[TelegramMessage]) -> bool:
        """텔레그램 메시지 배치를 임베딩 처리합니다.

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
                    
                    # 벡터 저장
                    vectors = [
                        {
                            "id": str(msg.message_id),
                            "values": emb,
                            "metadata": meta
                        }
                        for (msg, _), emb, meta in zip(batch, embeddings, metadatas)
                    ]
                    
                    success = await self.vector_store.store_vectors_async(vectors)
                    if not success:
                        logger.error(f"배치 벡터 저장 실패 (배치 {batch_idx + 1})")
                        continue
                        
                    logger.info(f"배치 {batch_idx + 1} 임베딩 완료: {len(batch)}개 메시지")
                    
                except Exception as e:
                    logger.error(f"배치 {batch_idx + 1} 처리 중 오류: {str(e)}")
                    continue
            
            return True
            
        except Exception as e:
            logger.error(f"배치 임베딩 중 오류 발생: {str(e)}")
            return False

    async def search_messages(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.5,
        channel_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """쿼리와 관련된 텔레그램 메시지를 검색합니다.
        
        Args:
            query (str): 검색 쿼리
            top_k (int): 검색할 메시지 수
            min_score (float): 최소 유사도 점수
            channel_ids (Optional[List[str]]): 검색할 채널 ID 목록
            
        Returns:
            List[Dict[str, Any]]: 검색된 메시지 목록
        """
        try:
            # 필터 설정
            filters = {
                "namespace": self.namespace
            }
            if channel_ids:
                filters["channel_id"] = {"$in": channel_ids}

            # 검색 실행
            results = await self.vector_store.search_async(
                query=query,
                top_k=top_k,
                filters=filters
            )

            # 결과 형식화
            messages = []
            for doc, score in results:
                if score < min_score:
                    continue
                    
                message = {
                    "text": doc.page_content,
                    "score": score,
                    "metadata": doc.metadata
                }
                messages.append(message)

            return messages

        except Exception as e:
            logger.error(f"메시지 검색 중 오류 발생: {str(e)}")
            return []

    async def delete_channel_messages(
        self, 
        channel_id: str,
        before_date: Optional[datetime] = None
    ) -> bool:
        """특정 채널의 메시지를 삭제합니다.
        
        Args:
            channel_id (str): 삭제할 채널 ID
            before_date (Optional[datetime]): 이 날짜 이전의 메시지만 삭제. None이면 모든 메시지 삭제.
            
        Returns:
            bool: 성공 여부
        """
        try:
            # 채널 메시지 검색을 위한 필터 설정
            filters = {
                "namespace": self.namespace,
                "channel_id": channel_id
            }
            
            # 날짜 필터 추가
            if before_date:
                filters["created_at"] = {"$lt": before_date.isoformat()}
            
            # 검색 실행 (임시 쿼리와 큰 top_k 값 사용)
            results = await self.vector_store.search_async(
                query="",  # 임시 쿼리
                top_k=10000,  # 충분히 큰 값
                filters=filters
            )
            
            if not results:
                logger.info(f"삭제할 메시지가 없습니다 (channel_id: {channel_id})")
                return True
                
            # 메시지 ID 추출
            message_ids = [doc.metadata.get("message_id") for doc, _ in results if doc.metadata.get("message_id")]
            
            if not message_ids:
                logger.warning(f"유효한 메시지 ID가 없습니다 (channel_id: {channel_id})")
                return True
                
            # 벡터 삭제
            success = await self.vector_store.delete_documents_by_embedding_id_async(message_ids)
            
            if success:
                logger.info(f"채널 메시지 삭제 완료: {len(message_ids)}개 (channel_id: {channel_id})")
            else:
                logger.error(f"채널 메시지 삭제 실패 (channel_id: {channel_id})")
                
            return success
            
        except Exception as e:
            logger.error(f"채널 메시지 삭제 중 오류 발생: {str(e)}")
            return False
