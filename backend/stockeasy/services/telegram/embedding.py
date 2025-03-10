from typing import List, Dict, Any, Optional
import numpy as np
from datetime import datetime
from dataclasses import dataclass, asdict

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
    text: str                    # 메시지 텍스트
    sender_id: Optional[str]     # 발신자 ID (있는 경우)
    sender_name: Optional[str]   # 발신자 이름 (있는 경우)
    message_created_at: datetime         # 메시지 생성 시간
    has_media: bool             # 미디어 첨부 여부
    has_document: bool          # 문서 첨부 여부
    document_name: Optional[str] # 문서 이름 (있는 경우)
    document_gcs_path: Optional[str] # GCS 경로 (있는 경우)

    @classmethod
    def from_telegram_message(cls, message: TelegramMessage) -> 'TelegramMessageMetadata':
        """TelegramMessage로부터 메타데이터 객체를 생성합니다."""
        return cls(
            message_id=message.message_id,
            channel_id=message.channel_id,
            channel_title=message.channel_title,
            message_type=message.message_type,
            text=message.message_text,
            sender_id=message.sender_id,
            sender_name=message.sender_name,
            message_created_at=message.message_created_at,
            has_media=message.has_media,
            has_document=message.has_document,
            document_name=message.document_name if message.has_document else None,
            document_gcs_path=message.document_gcs_path if message.has_document else None,
        )

class TelegramEmbeddingService(CommonEmbeddingService):
    """텔레그램 메시지 전용 임베딩 서비스"""

    def __init__(self):
        """
        Args:
            namespace (str): Pinecone 네임스페이스. 기본값은 "telegram"
        """
        super().__init__()
        self.namespace = settings.PINECONE_NAMESPACE_STOCKEASY_TELEGRAM
        self.vector_store = VectorStoreManager(
            EmbeddingModelType.GOOGLE_MULTI_LANG,   
            project_name="stockeasy",
            namespace=self.namespace,
        )

    def _create_telegram_metadata(self, message: TelegramMessage) -> dict:
        """텔레그램 메시지의 메타데이터를 생성합니다.
        
        Args:
            message (TelegramMessage): 텔레그램 메시지
            
        Returns:
            dict: 메타데이터 딕셔너리
        """
        metadata = TelegramMessageMetadata.from_telegram_message(message)
        metadata_dict = asdict(metadata)
        
        # 모든 값을 직렬화 가능한 형식으로 변환
        for key, value in metadata_dict.items():
            if value is None:
                metadata_dict[key] = ""  # None을 빈 문자열로 변환
            elif isinstance(value, bool):
                metadata_dict[key] = str(value).lower()  # bool을 문자열로 변환
            elif isinstance(value, (int, float)):
                metadata_dict[key] = str(value)  # 숫자를 문자열로 변환
            elif isinstance(value, datetime):
                metadata_dict[key] = value.isoformat()  # datetime을 ISO 형식 문자열로 변환
        
        return metadata_dict
        
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

    def _create_vector_id(self, message: TelegramMessage) -> str:
        """메시지의 고유 ID를 생성합니다.
        
        채널 ID와 메시지 ID를 조합하여 고유한 벡터 ID를 생성합니다.
        
        Args:
            message (TelegramMessage): 텔레그램 메시지
            
        Returns:
            str: 고유한 벡터 ID (format: {channel_id}_{message_id})
        """
        return f"{message.channel_id}_{message.message_id}"

    def _validate_vector(self, vector: Dict) -> bool:
        """벡터 데이터의 유효성을 검사합니다.
        
        Args:
            vector (Dict): 검사할 벡터 데이터
            
        Returns:
            bool: 유효성 검사 통과 여부
        """
        try:
            # 필수 필드 확인
            if not all(key in vector for key in ["id", "values", "metadata"]):
                logger.error("벡터 데이터에 필수 필드가 없습니다")
                return False
            
            # id 검사
            if not isinstance(vector["id"], str):
                logger.error(f"id가 문자열이 아닙니다: {type(vector['id'])}")
                return False
            
            # values 검사
            if not isinstance(vector["values"], list):
                logger.error(f"values가 리스트가 아닙니다: {type(vector['values'])}")
                return False
            
            if not vector["values"] or not all(isinstance(x, (int, float)) for x in vector["values"]):
                logger.error("values가 비어있거나 숫자가 아닌 값이 포함되어 있습니다")
                return False
            
            # metadata 검사
            if not isinstance(vector["metadata"], dict):
                logger.error(f"metadata가 딕셔너리가 아닙니다: {type(vector['metadata'])}")
                return False
            
            # metadata 값 검사
            for key, value in vector["metadata"].items():
                if not isinstance(value, str):
                    logger.error(f"metadata의 값이 문자열이 아닙니다: {key}={type(value)}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"벡터 데이터 검증 중 오류 발생: {str(e)}")
            return False

    def embed_telegram_message(self, message: TelegramMessage) -> bool:
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
            embeddings = self.create_single_embedding(text)
            if not embeddings:
                logger.error(f"임베딩 생성 실패: message_id={message.message_id}")
                return False
                
            # numpy 배열로 변환하고 float32로 타입 변환
            embedding_vector = np.array(embeddings, dtype=np.float32).tolist()
                
            # 벡터 저장
            vector = {
                "id": self._create_vector_id(message),
                "values": embedding_vector,
                "metadata": metadata
            }
            
            # 벡터 데이터 유효성 검사
            if not self._validate_vector(vector):
                logger.error("벡터 데이터가 유효하지 않습니다")
                return False
            
            # 벡터 데이터 형식 로깅
            logger.info(f"벡터 데이터 형식 확인:")
            logger.info(f"- id type: {type(vector['id'])}")
            logger.info(f"- values type: {type(vector['values'])}")
            logger.info(f"- values[0] type: {type(vector['values'][0])}")
            logger.info(f"- metadata type: {type(vector['metadata'])}")
            logger.info(f"- values length: {len(vector['values'])}")
            
            success = self.vector_store.store_vectors([vector])
            
            if success:
                logger.info(f"메시지 임베딩 완료: message_id={message.message_id}")
                return True
            else:
                logger.error(f"벡터 저장 실패: message_id={message.message_id}")
                return False
                
        except Exception as e:
            logger.error(f"메시지 임베딩 중 오류 발생: {str(e)}")
            return False

    def embed_telegram_messages_batch(self, messages: List[TelegramMessage]) -> bool:
        """텔레그램 메시지 배치를 임베딩 처리합니다.

        Args:
            messages (List[TelegramMessage]): 임베딩할 메시지 리스트

        Returns:
            bool: 전체 성공 여부
        """
        try:
            logger.info(f"배치 임베딩 시작: {len(messages)}개 메시지")
            # 메시지 전처리 및 유효성 검사
            valid_messages = []
            for msg in messages:
                text = self._prepare_text_for_embedding(msg)
                if text:  # None이 아닌 경우만 추가
                    valid_messages.append((msg, text))
                    
            if not valid_messages:
                logger.warning("유효한 메시지가 없습니다")
                return True  # 실패가 아닌 것으로 처리
            
            logger.info(f"유효한 메시지 수: {len(valid_messages)}개")
            # 텍스트 길이에 따라 배치 구성
            batches = []
            current_batch = []
            current_batch_tokens = 0
            
            for msg, text in valid_messages:
                # 토큰 수 추정 (대략적으로 단어 수의 1.5배)
                estimated_tokens = len(text.split()) * 1.5
                
                # 현재 배치에 추가할 수 있는지 확인
                if len(current_batch) >= self.batch_size:
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
                    embeddings = self.create_embeddings_batch_sync(texts)
                    
                    if not embeddings:
                        logger.error(f"배치 임베딩 생성 실패 (배치 {batch_idx + 1})")
                        continue
                    
                    if len(embeddings) != len(batch):
                        logger.error(f"임베딩 결과 수 불일치 - 예상: {len(batch)}, 실제: {len(embeddings)}")
                        continue
                    
                    # numpy 배열로 변환하고 float32로 타입 변환
                    embedding_vectors = [np.array(emb, dtype=np.float32).tolist() for emb in embeddings]
                    
                    # 벡터 저장
                    vectors = [
                        {
                            "id": self._create_vector_id(msg),
                            "values": emb,
                            "metadata": meta
                        }
                        for (msg, _), emb, meta in zip(batch, embedding_vectors, metadatas)
                    ]
                    
                    # 벡터 데이터 유효성 검사
                    valid_vectors = []
                    for vector in vectors:
                        if self._validate_vector(vector):
                            valid_vectors.append(vector)
                        else:
                            logger.error(f"유효하지 않은 벡터 데이터 발견: id={vector['id']}")
                    
                    if not valid_vectors:
                        logger.error("유효한 벡터가 없습니다")
                        continue
                    
                    # 첫 번째 벡터의 데이터 형식 로깅
                    if valid_vectors:
                        logger.info(f"배치의 첫 번째 벡터 데이터 형식 확인:")
                        logger.info(f"- id type: {type(valid_vectors[0]['id'])}")
                        logger.info(f"- values type: {type(valid_vectors[0]['values'])}")
                        logger.info(f"- values[0] type: {type(valid_vectors[0]['values'][0])}")
                        logger.info(f"- metadata type: {type(valid_vectors[0]['metadata'])}")
                        logger.info(f"- values length: {len(valid_vectors[0]['values'])}")
                    
                    success = self.vector_store.store_vectors(valid_vectors)
                    if not success:
                        logger.error(f"배치 벡터 저장 실패 (배치 {batch_idx + 1})")
                        continue
                        
                    logger.info(f"배치 {batch_idx + 1} 임베딩 완료: {len(valid_vectors)}개 메시지")
                    
                except Exception as e:
                    logger.error(f"배치 {batch_idx + 1} 처리 중 오류: {str(e)}")
                    continue
            
            return True
            
        except Exception as e:
            logger.error(f"배치 임베딩 중 오류 발생: {str(e)}")
            return False
