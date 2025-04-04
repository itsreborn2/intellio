"""
리랭킹(Reranking) 서비스

이 모듈은 검색 결과를 재정렬하는 리랭킹 기능을 제공합니다.
현재 지원하는 리랭킹 모델:
1. Pinecone 리랭킹 API (bge-reranker-v2-m3)
2. HuggingFace Cross-Encoder

사용 예:
```
# Pinecone 리랭커 사용
reranker = Reranker(
    RerankerConfig(
        reranker_type=RerankerType.PINECONE,
        pinecone_config=PineconeRerankerConfig(
            api_key="your_api_key",
            model_name="bge-reranker-v2-m3"
        )
    )
)

# 리랭킹 수행
results = await reranker.rerank(
    query="검색 쿼리",
    documents=search_results,
    top_k=5
)
```
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Dict, Optional, Any, Union, Tuple
from pydantic import BaseModel, Field, model_validator
import os
from loguru import logger

from common.services.retrievers.models import DocumentWithScore, RetrievalResult

# Pinecone 리랭킹 의존성
try:
    from pinecone import Pinecone
except ImportError:
    Pinecone = None

# Cross-Encoder 의존성
try:
    from sentence_transformers.cross_encoder import CrossEncoder
except ImportError:
    CrossEncoder = None


class RerankerType(str, Enum):
    """리랭커 타입 열거형"""
    PINECONE = "pinecone"
    CROSS_ENCODER = "cross_encoder"


class BaseRerankerConfig(BaseModel):
    """리랭커 기본 설정"""
    top_k: int = Field(default=10, description="반환할 최대 문서 수")
    min_score: float = Field(default=0.3, description="최소 점수 임계값")
    candidate_k: int = Field(default=100, description="리랭킹할 후보 문서 수")


class PineconeRerankerConfig(BaseRerankerConfig):
    """Pinecone 리랭커 설정"""
    model_name: str = Field(default="bge-reranker-v2-m3", description="Pinecone 리랭킹 모델 이름")
    api_key: Optional[str] = Field(default=None, description="Pinecone API 키")
    parameters: Dict[str, Any] = Field(default_factory=lambda: {"truncate": "END"}, description="추가 파라미터")
    # "END": 입력 시퀀스가 토큰 제한을 초과할 경우, 끝부분을 잘라냅니다
    # "NONE": 입력 시퀀스가 토큰 제한을 초과할 경우, 에러를 반환합니다
    # 기본값: bge-reranker-v2-m3의 경우 "NONE"
    # $2/1k requests

    # rank_fields : 리랭킹을 수행할 사용자 지정 필드를 지정하는 데 사용, 기본값 'text', 싱글 필드만 리랭킹 가능.

    @model_validator(mode='after')
    def set_api_key_from_env(self) -> 'PineconeRerankerConfig':
        """환경 변수에서 API 키 설정"""
        if not self.api_key:
            self.api_key = os.environ.get('PINECONE_API_KEY')
        return self


class CrossEncoderRerankerConfig(BaseRerankerConfig):
    """Cross-Encoder 리랭커 설정"""
    model_name: str = Field(default="cross-encoder/ms-marco-MiniLM-L-6-v2", description="Cross-Encoder 모델 이름")
    batch_size: int = Field(default=32, description="배치 크기")
    device: str = Field(default="cpu", description="실행 장치 (cpu 또는 cuda)")


class RerankerConfig(BaseModel):
    """리랭커 통합 설정"""
    reranker_type: RerankerType = Field(default=RerankerType.PINECONE, description="리랭커 타입")
    pinecone_config: Optional[PineconeRerankerConfig] = None
    cross_encoder_config: Optional[CrossEncoderRerankerConfig] = None

    def get_model_config(self):
        """선택된 리랭커 타입에 맞는 설정 반환"""
        if self.reranker_type == RerankerType.PINECONE:
            return self.pinecone_config or PineconeRerankerConfig()
        elif self.reranker_type == RerankerType.CROSS_ENCODER:
            return self.cross_encoder_config or CrossEncoderRerankerConfig()
        else:
            raise ValueError(f"지원하지 않는 리랭커 타입: {self.reranker_type}")


class BaseReranker(ABC):
    """리랭커 기본 인터페이스"""

    def __init__(self, config):
        self.config = config

    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: List[DocumentWithScore],
        top_k: Optional[int] = None
    ) -> RetrievalResult:
        """문서를 리랭킹하는 메서드"""
        pass


class PineconeReranker(BaseReranker):
    """Pinecone API를 사용한 리랭커 구현체"""

    def __init__(self, config: PineconeRerankerConfig):
        super().__init__(config)
        if Pinecone is None:
            raise ImportError("pinecone-client 패키지가 설치되지 않았습니다. pip install pinecone-client를 실행하세요.")
        
        self.client = Pinecone(api_key=config.api_key) if config.api_key else Pinecone()
        self.model_name = config.model_name

    async def rerank(
        self,
        query: str,
        documents: List[DocumentWithScore],
        top_k: Optional[int] = None
    ) -> RetrievalResult:
        """Pinecone API를 사용한 리랭킹"""
        _top_k = top_k or self.config.top_k

        try:
            # 문서 텍스트 추출
            doc_texts = [doc.page_content for doc in documents]

            # Pinecone 리랭킹 API 호출
            rerank_results = self.client.inference.rerank(
                model=self.model_name,
                query=query,
                documents=doc_texts,
                top_n=_top_k,
                return_documents=True,
                parameters=self.config.parameters
            )

            # 결과 변환
            result_documents = []
            for item in rerank_results.data:
                # 원본 문서 찾기
                original_doc = next(
                    (doc for doc in documents if doc.page_content == item.document.text),
                    None
                )

                if original_doc and item.score >= self.config.min_score:
                    # 원본 메타데이터 유지하면서 새 점수 설정
                    result_doc = DocumentWithScore(
                        page_content=item.document.text,
                        metadata={
                            **original_doc.metadata,
                            "rerank_score": item.score
                        },
                        score=item.score
                    )
                    result_documents.append(result_doc)

            logger.info(f"Pinecone 리랭킹 완료: {len(result_documents)}/{len(documents)} 문서")

            return RetrievalResult(
                documents=result_documents,
                query_analysis={
                    "type": "pinecone_rerank",
                    "model": self.model_name,
                    "total_candidates": len(documents),
                    "returned": len(result_documents)
                }
            )

        except Exception as e:
            logger.error(f"Pinecone 리랭킹 중 오류 발생: {str(e)}")
            # 오류 발생 시 원본 문서 그대로 반환
            return RetrievalResult(documents=documents[:_top_k])


class CrossEncoderReranker(BaseReranker):
    """HuggingFace Cross-Encoder를 사용한 리랭커 구현체"""

    def __init__(self, config: CrossEncoderRerankerConfig):
        super().__init__(config)

        if CrossEncoder is None:
            raise ImportError("sentence-transformers 패키지가 설치되지 않았습니다. pip install sentence-transformers를 실행하세요.")

        self.model = CrossEncoder(
            config.model_name,
            device=config.device
        )
        self.batch_size = config.batch_size

    async def rerank(
        self,
        query: str,
        documents: List[DocumentWithScore],
        top_k: Optional[int] = None
    ) -> RetrievalResult:
        """Cross-Encoder를 사용한 리랭킹"""
        _top_k = top_k or self.config.top_k

        try:
            # 쿼리-문서 쌍 생성
            pairs = [[query, doc.page_content] for doc in documents]

            # Cross-Encoder 점수 계산
            scores = self.model.predict(
                pairs,
                batch_size=self.batch_size
            )

            # 결과 정렬 및 변환
            scored_docs = list(zip(documents, scores))
            scored_docs.sort(key=lambda x: x[1], reverse=True)

            # 최소 점수 필터링 및 상위 K개 선택
            result_documents = []
            for doc, score in scored_docs:
                if score >= self.config.min_score and len(result_documents) < _top_k:
                    result_doc = DocumentWithScore(
                        page_content=doc.page_content,
                        metadata={
                            **doc.metadata,
                            "rerank_score": float(score)
                        },
                        score=float(score)
                    )
                    result_documents.append(result_doc)

            logger.info(f"Cross-Encoder 리랭킹 완료: {len(result_documents)}/{len(documents)} 문서")

            return RetrievalResult(
                documents=result_documents,
                query_analysis={
                    "type": "cross_encoder_rerank",
                    "model": self.config.model_name,
                    "total_candidates": len(documents),
                    "returned": len(result_documents)
                }
            )

        except Exception as e:
            logger.error(f"Cross-Encoder 리랭킹 중 오류 발생: {str(e)}")
            # 오류 발생 시 원본 문서 그대로 반환
            return RetrievalResult(documents=documents[:_top_k])


class Reranker:
    """리랭커 메인 클래스"""

    def __init__(self, config: RerankerConfig = None):
        self.config = config or RerankerConfig()
        self._reranker = self._create_reranker()

    def _create_reranker(self) -> BaseReranker:
        """설정에 따라 적절한 리랭커 구현체 생성"""
        if self.config.reranker_type == RerankerType.PINECONE:
            return PineconeReranker(self.config.get_model_config())
        elif self.config.reranker_type == RerankerType.CROSS_ENCODER:
            return CrossEncoderReranker(self.config.get_model_config())
        else:
            raise ValueError(f"지원하지 않는 리랭커 타입: {self.config.reranker_type}")

    async def rerank(
        self,
        query: str,
        documents: List[DocumentWithScore],
        top_k: Optional[int] = None
    ) -> RetrievalResult:
        """문서 리랭킹 수행"""
        if not documents:
            logger.warning("리랭킹할 문서가 없습니다.")
            return RetrievalResult(documents=[])

        logger.info(f"리랭킹 시작 - 쿼리: '{query}', 문서 수: {len(documents)}")
        return await self._reranker.rerank(query, documents, top_k)


# 사용 예제
async def example_usage():
    """사용 예제"""
    from common.services.retrievers.models import DocumentWithScore
    
    # 예제 문서
    documents = [
        DocumentWithScore(
            page_content="Apple은 인기 있는 과일로 단맛과 바삭한 식감으로 알려져 있습니다.",
            metadata={"id": "1"},
            score=0.8
        ),
        DocumentWithScore(
            page_content="Apple은 iPhone과 같은 혁신적인 제품으로 유명합니다.",
            metadata={"id": "2"},
            score=0.7
        ),
        DocumentWithScore(
            page_content="많은 사람들이 건강한 간식으로 사과를 즐깁니다.",
            metadata={"id": "3"},
            score=0.6
        ),
        DocumentWithScore(
            page_content="Apple Inc.는 세련된 디자인과 사용자 친화적인 인터페이스로 기술 산업에 혁명을 일으켰습니다.",
            metadata={"id": "4"},
            score=0.5
        ),
    ]
    
    # Pinecone 리랭커 설정
    config = RerankerConfig(
        reranker_type=RerankerType.PINECONE,
        pinecone_config=PineconeRerankerConfig(
            model_name="bge-reranker-v2-m3",
            min_score=0.1
        )
    )
    
    # 리랭커 초기화
    reranker = Reranker(config)
    
    # 리랭킹 수행
    results = await reranker.rerank(
        query="Apple 회사에 대해 알려주세요",
        documents=documents,
        top_k=2
    )
    
    # 결과 출력
    print(f"리랭킹 결과: {len(results.documents)} 문서")
    for i, doc in enumerate(results.documents):
        print(f"{i+1}. 점수: {doc.score:.3f}, 내용: {doc.page_content[:50]}...")
    
    return results


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage()) 