import pytest
import asyncio
import os
from typing import AsyncGenerator, Generator
from fastapi.testclient import TestClient
from httpx import AsyncClient
from main import app

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """테스트 케이스마다 새로운 이벤트 루프 생성"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """테스트에서 사용할 비동기 클라이언트"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture(autouse=True)
def setup_test_environment():
    """테스트 환경 설정"""
    # 환경 변수 설정
    os.environ["OPENAI_API_KEY"] = "test-openai-api-key"
    os.environ["PINECONE_API_KEY"] = "test-pinecone-api-key"
    os.environ["PINECONE_ENVIRONMENT"] = "test-env"
    os.environ["PINECONE_INDEX_NAME"] = "test-index"
    
    # 테스트 실행
    yield
    
    # 환경 변수 제거
    del os.environ["OPENAI_API_KEY"]
    del os.environ["PINECONE_API_KEY"]
    del os.environ["PINECONE_ENVIRONMENT"]
    del os.environ["PINECONE_INDEX_NAME"]

@pytest.fixture(autouse=True)
def mock_openai(monkeypatch):
    """OpenAI API 모킹"""
    class MockEmbeddings:
        def create(self, *args, **kwargs):
            class MockEmbedding:
                def __init__(self):
                    self.embedding = [0.1] * 1536  # OpenAI ada-002 모델의 임베딩 차원
            
            class MockResponse:
                def __init__(self):
                    self.data = [MockEmbedding()]
            
            return MockResponse()
    
    class MockOpenAI:
        def __init__(self, *args, **kwargs):
            self.embeddings = MockEmbeddings()
    
    # OpenAI 클라이언트 전체를 모킹
    monkeypatch.setattr("openai.OpenAI", MockOpenAI)

@pytest.fixture(autouse=True)
def mock_pinecone(monkeypatch):
    """Pinecone API 모킹"""
    class MockIndex:
        def __init__(self):
            self.vectors = {}
        
        def upsert(self, vectors):
            for id, embedding, metadata in vectors:
                self.vectors[id] = {
                    "embedding": embedding,
                    "metadata": metadata
                }
    
    class MockPinecone:
        def __init__(self, *args, **kwargs):
            self._index = MockIndex()
        
        def Index(self, *args, **kwargs):
            return self._index
        
        def list_indexes(self):
            class MockResponse:
                def __init__(self):
                    self.names = []
            return MockResponse()
    
    # Pinecone 클라이언트 모킹
    monkeypatch.setattr("pinecone.Pinecone", MockPinecone)

@pytest.fixture(autouse=True)
def mock_celery(monkeypatch):
    """Celery 태스크를 동기적으로 실행하도록 설정"""
    def mock_delay(self, *args, **kwargs):
        return self(*args, **kwargs)
    
    # Celery 태스크의 delay 메서드를 동기 실행으로 변경
    monkeypatch.setattr("celery.app.task.Task.delay", mock_delay)
