import pytest
import numpy as np
from unittest.mock import Mock, patch
from common.services.retrievers.contextual_bm25 import ContextualBM25Retriever, ContextualBM25Config
from common.services.retrievers.models import Document, RetrievalResult
from llama_index.core.schema import NodeWithScore, TextNode, BaseNode
import torch

@pytest.fixture
def sample_documents():
    """테스트용 샘플 문서 생성"""
    return [
        Document(
            page_content="한국의 경제 성장률이 2023년에는 2.5% 증가할 것으로 전망됩니다.",
            metadata={"document_id": "doc1", "page_number": 1},
            score=0.0
        ),
        Document(
            page_content="인공지능 기술의 발전으로 자동화가 가속화되고 있습니다.",
            metadata={"document_id": "doc2", "page_number": 1},
            score=0.0
        ),
        Document(
            page_content="기후 변화로 인한 환경 문제가 심각해지고 있습니다.",
            metadata={"document_id": "doc3", "page_number": 1},
            score=0.0
        )
    ]

@pytest.fixture
def mock_bm25_results():
    """BM25 검색 결과 모의 데이터"""
    return [
        NodeWithScore(
            node=TextNode(text="한국의 경제 성장률", metadata={"document_id": "doc1"}),
            score=0.8
        ),
        NodeWithScore(
            node=TextNode(text="인공지능 기술", metadata={"document_id": "doc2"}),
            score=0.6
        )
    ]

@pytest.fixture
def retriever():
    """ContextualBM25Retriever 인스턴스 생성"""
    config = ContextualBM25Config(
        min_score=0.3,
        bm25_weight=0.6,
        context_weight=0.4,
        context_window_size=1
    )
    with patch('transformers.AutoTokenizer.from_pretrained'), \
         patch('transformers.AutoModel.from_pretrained'):
        return ContextualBM25Retriever(config)

@pytest.mark.asyncio
async def test_add_documents(retriever, sample_documents):
    """문서 추가 테스트"""
    with patch('llama_index.retrievers.bm25.BM25Retriever.from_defaults') as mock_bm25:
        mock_bm25.return_value = Mock()
        success = await retriever.add_documents(sample_documents)
        assert success == True
        assert len(retriever.documents) == 3
        assert retriever.bm25_retriever is not None

@pytest.mark.asyncio
async def test_retrieve_combines_bm25_and_context(retriever, sample_documents, mock_bm25_results):
    """문맥 점수와 BM25 점수가 올바르게 결합되는지 테스트"""
    with patch.object(retriever, '_get_embeddings') as mock_get_embeddings, \
         patch('llama_index.retrievers.bm25.BM25Retriever.from_defaults') as mock_bm25_cls, \
         patch.object(mock_bm25_cls.return_value, 'retrieve') as mock_retrieve:
        
        # BM25 검색 결과 설정
        mock_retrieve.return_value = mock_bm25_results
        mock_bm25_cls.return_value = Mock(retrieve=mock_retrieve)
        
        # 문맥 임베딩 설정 - 문서1이 쿼리와 가장 유사하도록
        doc_embeddings = np.array([
            [1.0] * 768,  # 문서1 - 쿼리와 가장 유사
            [0.5] * 768,  # 문서2 - 중간 유사도
            [0.1] * 768   # 문서3 - 낮은 유사도
        ])
        query_embedding = np.array([0.9] * 768).reshape(1, -1)  # 문서1과 유사한 쿼리
        
        mock_get_embeddings.side_effect = [
            doc_embeddings,  # 문서 임베딩
            query_embedding  # 쿼리 임베딩
        ]
        
        # 문서 추가
        await retriever.add_documents(sample_documents)
        
        # 검색 수행 - 경제 관련 쿼리
        result = await retriever.retrieve("한국 경제 성장률", top_k=2)
        
        # 기본 검증
        assert isinstance(result, RetrievalResult)
        assert len(result.documents) > 0
        
        # 문서 순서 검증 - 문서1(경제)이 가장 높은 점수를 받아야 함
        assert result.documents[0].metadata["document_id"] == "doc1"
        
        # 점수 결합 검증
        for doc in result.documents:
            # BM25와 문맥 점수가 모두 있어야 함
            assert "bm25_score" in doc.metadata
            assert "context_score" in doc.metadata
            
            # 점수가 올바른 범위에 있어야 함
            assert 0 <= doc.metadata["bm25_score"] <= 1
            assert 0 <= doc.metadata["context_score"] <= 1
            
            # 최종 점수가 가중치를 올바르게 반영해야 함
            expected_score = (
                retriever.config.bm25_weight * doc.metadata["bm25_score"] +
                retriever.config.context_weight * doc.metadata["context_score"]
            )
            assert abs(doc.score - expected_score) < 1e-6

@pytest.mark.asyncio
async def test_retrieve_respects_context_window(retriever, sample_documents, mock_bm25_results):
    """문맥 윈도우 크기가 올바르게 적용되는지 테스트"""
    # 문맥 윈도우 크기를 1로 설정
    retriever.config.context_window_size = 1
    
    with patch.object(retriever, '_get_embeddings') as mock_get_embeddings, \
         patch('llama_index.retrievers.bm25.BM25Retriever.from_defaults') as mock_bm25_cls, \
         patch.object(mock_bm25_cls.return_value, 'retrieve') as mock_retrieve:
        
        # BM25 검색 결과 설정
        mock_retrieve.return_value = mock_bm25_results
        mock_bm25_cls.return_value = Mock(retrieve=mock_retrieve)
        
        # 문맥 임베딩 설정
        doc_embeddings = np.array([
            [1.0] * 768,  # 문서1
            [0.9] * 768,  # 문서2 - 문서1과 유사
            [0.1] * 768   # 문서3 - 매우 다름
        ])
        query_embedding = np.array([0.95] * 768).reshape(1, -1)
        
        mock_get_embeddings.side_effect = [
            doc_embeddings,
            query_embedding
        ]
        
        # 문서 추가
        await retriever.add_documents(sample_documents)
        
        # 검색 수행
        result = await retriever.retrieve("경제 성장", top_k=3)
        
        # 문맥 윈도우가 적용되었는지 확인
        assert len(result.documents) > 0
        scores = [doc.metadata["context_score"] for doc in result.documents]
        # 인접 문서들의 점수가 비슷해야 함
        for i in range(len(scores) - 1):
            assert abs(scores[i] - scores[i + 1]) <= 0.3

@pytest.mark.asyncio
async def test_retrieve_with_different_weights(retriever, sample_documents):
    """다양한 가중치 설정에서 검색이 올바르게 작동하는지 테스트"""
    # BM25 가중치를 높게 설정
    retriever.config.bm25_weight = 0.8
    retriever.config.context_weight = 0.2
    
    with patch.object(retriever, '_get_embeddings') as mock_get_embeddings:
        # 문맥 임베딩 설정
        doc_embeddings = np.array([
            [0.5] * 768,  # 문서1 - 중간 유사도
            [1.0] * 768,  # 문서2 - 높은 유사도
            [0.1] * 768   # 문서3 - 낮은 유사도
        ])
        query_embedding = np.array([0.9] * 768).reshape(1, -1)
        
        mock_get_embeddings.side_effect = [
            doc_embeddings,
            query_embedding
        ]
        
        # 문서 추가
        await retriever.add_documents(sample_documents)
        
        # 검색 수행
        result = await retriever.retrieve("경제 성장", top_k=2)
        
        # BM25 점수의 영향이 더 커야 함
        for doc in result.documents:
            bm25_contribution = doc.metadata["bm25_score"] * retriever.config.bm25_weight
            context_contribution = doc.metadata["context_score"] * retriever.config.context_weight
            assert bm25_contribution > context_contribution

@pytest.mark.asyncio
async def test_update_documents(retriever, sample_documents):
    """문서 업데이트 테스트"""
    with patch('llama_index.retrievers.bm25.BM25Retriever.from_defaults') as mock_bm25:
        mock_bm25.return_value = Mock()
        
        # 초기 문서 추가
        await retriever.add_documents(sample_documents)
        
        # 업데이트할 문서 준비
        updated_doc = Document(
            page_content="업데이트된 경제 전망 내용입니다.",
            metadata={"document_id": "doc1", "page_number": 1},
            score=0.0
        )
        
        # 문서 업데이트
        success = await retriever.update_documents([updated_doc])
        assert success == True

@pytest.mark.asyncio
async def test_delete_documents(retriever, sample_documents):
    """문서 삭제 테스트"""
    with patch('llama_index.retrievers.bm25.BM25Retriever.from_defaults') as mock_bm25:
        mock_bm25.return_value = Mock()
        
        # 초기 문서 추가
        await retriever.add_documents(sample_documents)
        
        # 문서 삭제
        success = await retriever.delete_documents(["doc1"])
        assert success == True
        assert len(retriever.documents) == 2

def test_config_validation():
    """설정 유효성 검사 테스트"""
    with pytest.raises(ValueError, match="가중치는 0과 1 사이의 값이어야 합니다"):
        ContextualBM25Config(
            min_score=0.3,
            bm25_weight=1.5,
            context_weight=0.4
        )
    
    with pytest.raises(ValueError, match="가중치의 합은 1이어야 합니다"):
        ContextualBM25Config(
            min_score=0.3,
            bm25_weight=0.3,
            context_weight=0.3
        )

@pytest.mark.asyncio
async def test_embedding_cache(retriever):
    """임베딩 캐시 테스트"""
    with patch('torch.no_grad') as mock_no_grad:
        # 토크나이저 설정
        mock_inputs = {
            'input_ids': torch.ones((1, 10), dtype=torch.long),
            'attention_mask': torch.ones((1, 10), dtype=torch.long)
        }
        retriever.tokenizer = Mock()
        retriever.tokenizer.return_value = mock_inputs
        
        # 모델 설정
        mock_output = Mock()
        mock_output.last_hidden_state = torch.ones((1, 1, 768))
        retriever.model = Mock()
        retriever.model.return_value = mock_output
        
        # 동일한 텍스트에 대한 임베딩 두 번 생성
        text = "테스트 텍스트"
        embedding1 = retriever._get_embeddings([text])
        embedding2 = retriever._get_embeddings([text])
        
        # 검증: 동일한 결과 반환 및 캐시 사용
        np.testing.assert_array_equal(embedding1, embedding2)
        assert retriever.model.call_count == 1  # 캐시로 인해 모델은 한 번만 호출됨
        assert retriever.tokenizer.call_count == 1  # 토크나이저도 한 번만 호출됨 