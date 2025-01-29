"""RAG 전체 프로세스 통합 테스트"""

import pytest
import asyncio
from pathlib import Path
import mimetypes
import logging
from app.services.extractor import DocumentExtractor
from app.services.chunker import RAGOptimizedChunker
from app.services.embedding import EmbeddingService
from app.services.llm import LLMService
from app.services.rag import RAGService
from app.services.prompts.chat_prompt import ChatPrompt
from app.services.prompts.table_prompt import TablePrompt

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@pytest.fixture
def test_docs_path():
    return [
        r"C:\Users\itsre\OneDrive\바탕 화면\새 폴더\새 폴더\NVIDIA 어닝콜 FY25.2Q.docx",
        r"C:\Users\itsre\OneDrive\바탕 화면\새 폴더\새 폴더\Duolingo 어닝콜 FY24.3Q.docx"
    ]

@pytest.fixture
def services():
    return {
        "extractor": DocumentExtractor(),
        "chunker": RAGOptimizedChunker(llm_service=LLMService()),
        "embedding": EmbeddingService(),
        "rag": RAGService()
    }

@pytest.mark.asyncio
async def test_document_extraction(test_docs_path, services):
    """문서 추출 테스트"""
    for doc_path in test_docs_path:
        mime_type = mimetypes.guess_type(doc_path)[0]
        with open(doc_path, 'rb') as f:
            content = f.read()
        
        doc_text = services["extractor"].extract_text(content, mime_type)
        assert doc_text, f"문서 추출 실패: {Path(doc_path).name}"
        logger.info(f"문서 추출 성공: {Path(doc_path).name}")
        logger.debug(f"추출된 텍스트 길이: {len(doc_text)} 문자")

@pytest.mark.asyncio
async def test_document_chunking(test_docs_path, services):
    """문서 청킹 테스트"""
    for doc_path in test_docs_path:
        mime_type = mimetypes.guess_type(doc_path)[0]
        with open(doc_path, 'rb') as f:
            content = f.read()
        
        doc_text = services["extractor"].extract_text(content, mime_type)
        chunks = await services["chunker"].process_document(doc_text)
        
        assert chunks, f"문서 청킹 실패: {Path(doc_path).name}"
        logger.info(f"청크 생성 완료: {len(chunks)}개")
        
        # 청크 품질 확인
        for i, chunk in enumerate(chunks):
            assert chunk.content, f"빈 청크 발견: chunk_{i}"
            assert chunk.metadata.section_type, f"섹션 타입 누락: chunk_{i}"
            logger.debug(f"청크 {i}: {len(chunk.content)} 문자, 타입: {chunk.metadata.section_type}")

@pytest.mark.asyncio
async def test_embedding_creation(test_docs_path, services):
    """임베딩 생성 테스트"""
    for doc_path in test_docs_path:
        mime_type = mimetypes.guess_type(doc_path)[0]
        with open(doc_path, 'rb') as f:
            content = f.read()
        
        doc_text = services["extractor"].extract_text(content, mime_type)
        chunks = await services["chunker"].process_document(doc_text)
        
        # 파일명에서 한글 제거하고 영문 ID 생성
        doc_id = f"test_doc_nvidia_q2"
        vectors = []
        
        for i, chunk in enumerate(chunks):
            embedding = await services["embedding"].create_embedding(chunk.content)
            assert embedding is not None, f"임베딩 생성 실패: chunk_{i}"
            assert len(embedding) == 1536, f"잘못된 임베딩 차원: {len(embedding)}"
            
            vector = {
                "id": f"{doc_id}_chunk_{i}",
                "values": embedding,
                "metadata": {
                    "document_id": doc_id,
                    "chunk_index": i,
                    "content": chunk.content,
                    "section_type": chunk.metadata.section_type,
                    "importance": chunk.metadata.importance
                }
            }
            vectors.append(vector)
            
        success = await services["embedding"].store_vectors(vectors)
        assert success, f"벡터 저장 실패: {doc_id}"
        logger.info(f"임베딩 저장 완료: {len(vectors)}개 벡터")

@pytest.mark.asyncio
async def test_chat_mode(services):
    """채팅 모드 테스트"""
    chat_prompt = ChatPrompt()
    chat_query = "두 회사의 실적을 비교 분석해주세요"
    
    # 관련 청크 검색
    chat_results = await services["embedding"].search_similar(
        query=chat_query,
        top_k=5,
        min_score=0.5
    )
    assert chat_results, "채팅 모드 검색 실패"
    logger.info(f"검색된 관련 청크: {len(chat_results)}개")
    
    # 검색 결과 구조 확인
    for i, result in enumerate(chat_results):
        logger.debug(f"\n검색 결과 {i} 구조:")
        logger.debug(f"전체 키: {result.keys()}")
        logger.debug(f"전체 내용: {result}")
        if 'metadata' in result:
            logger.debug(f"메타데이터 키: {result['metadata'].keys()}")
            logger.debug(f"메타데이터 내용: {result['metadata']}")
    
    # 응답 생성 전에 검색 결과 확인
    context_texts = []
    for result in chat_results:
        if 'metadata' in result and 'text' in result['metadata']:
            context_texts.append(result['metadata']['text'])
        elif 'text' in result:
            context_texts.append(result['text'])
    
    # 패턴과 쿼리 분석 정보 생성 (실제 구현에 맞게 수정 필요)
    keywords = {}
    query_analysis = {}
    
    # 응답 생성
    chat_response = await chat_prompt.analyze_async(
        content="\n".join(context_texts),
        user_query=chat_query,
        keywords=keywords,
        query_analysis=query_analysis
    )
    assert chat_response, "채팅 응답 생성 실패"
    logger.info("=== 채팅 모드 응답 ===")
    logger.info(f"질문: {chat_query}")
    logger.info(f"응답:\n{chat_response}\n")

@pytest.mark.asyncio
async def test_table_mode(services):
    """테이블 모드 테스트"""
    table_prompt = TablePrompt()
    table_query = "2024년 매출액이 얼마인가요?"
    
    # 관련 청크 검색
    table_results = await services["embedding"].search_similar(
        query=table_query,
        top_k=3,
        min_score=0.5
    )
    assert table_results, "테이블 모드 검색 실패"
    logger.info(f"검색된 관련 청크: {len(table_results)}개")
    
    # 검색 결과 구조 확인
    for i, result in enumerate(table_results):
        logger.debug(f"\n검색 결과 {i} 구조:")
        logger.debug(f"전체 키: {result.keys()}")
        logger.debug(f"전체 내용: {result}")
        if 'metadata' in result:
            logger.debug(f"메타데이터 키: {result['metadata'].keys()}")
            logger.debug(f"메타데이터 내용: {result['metadata']}")
    
    # 응답 생성 전에 검색 결과 확인
    context_texts = []
    for result in table_results:
        if 'metadata' in result and 'text' in result['metadata']:
            context_texts.append(result['metadata']['text'])
        elif 'text' in result:
            context_texts.append(result['text'])
    
    # 패턴과 쿼리 분석 정보 생성
    keywords = {}
    query_analysis = {}
    
    # 응답 생성
    table_response = await table_prompt.analyze_async(
        content="\n".join(context_texts),
        query=table_query,
        keywords=keywords,
        query_analysis=query_analysis
    )
    assert table_response, "테이블 응답 생성 실패"
    logger.info("=== 테이블 모드 응답 ===")
    logger.info(f"질문: {table_query}")
    logger.info(f"응답:\n{table_response}\n")

async def run_all_tests():
    """모든 테스트를 실행"""
    # fixture 값 직접 생성
    test_docs = [
        r"C:\Users\itsre\OneDrive\바탕 화면\새 폴더\새 폴더\NVIDIA 어닝콜 FY25.2Q.docx"
    ]
    
    services_dict = {
        "extractor": DocumentExtractor(),
        "chunker": RAGOptimizedChunker(llm_service=LLMService()),
        "embedding": EmbeddingService(),
        "rag": RAGService()
    }

    logger.info("=== 문서 추출 테스트 시작 ===")
    await test_document_extraction(test_docs, services_dict)
    
    logger.info("\n=== 문서 청킹 테스트 시작 ===")
    await test_document_chunking(test_docs, services_dict)
    
    logger.info("\n=== 임베딩 생성 테스트 시작 ===")
    await test_embedding_creation(test_docs, services_dict)
    
    logger.info("\n=== 채팅 모드 테스트 시작 ===")
    await test_chat_mode(services_dict)
    
    logger.info("\n=== 테이블 모드 테스트 시작 ===")
    await test_table_mode(services_dict)

if __name__ == "__main__":
    asyncio.run(run_all_tests())
