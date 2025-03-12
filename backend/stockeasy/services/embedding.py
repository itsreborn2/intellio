import logging
from common.core.config import settings
from common.services.embedding_models import    EmbeddingModelType
from common.services.embedding import EmbeddingService as CommonEmbeddingService
from common.services.vector_store_manager import VectorStoreManager


logger = logging.getLogger(__name__)

class StockeasyEmbeddingService(CommonEmbeddingService):
    """텔레그램 메시지 전용 임베딩 서비스"""

    def __init__(self):
        """
        Args:
            namespace (str): Pinecone 네임스페이스. 기본값은 "telegram"
        """
        super().__init__()
        self.namespace = settings.PINECONE_NAMESPACE_STOCKEASY
        self.vector_store = VectorStoreManager(
            EmbeddingModelType.OPENAI_3_LARGE,   
            project_name="stockeasy",
            namespace=self.namespace,
        )

    def embed_message(self, text: str) -> bool:
        #잠깐.. 여기서 임베딩을 할 이유가? 검색할때는 쓰겠네
        # 이거 호출안하고 부모 클래스 create_single_embedding() 바로 호출해서 쓰면 되겠고..
        # 일단 보류
        try:
            
            # 임베딩 생성
            embeddings = self.create_single_embedding(text)
            if not embeddings:
                logger.error(f"임베딩 생성 실패: {text}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"메시지 임베딩 중 오류 발생: {str(e)}")
            return False

    