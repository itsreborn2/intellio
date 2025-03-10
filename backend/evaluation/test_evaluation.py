"""
RAG 평가 시스템 테스트 모듈
"""
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai import VertexAIEmbeddings
from common.app import LoadEnvGlobal
# 환경 변수 로드
LoadEnvGlobal()

os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
os.environ["LANGCHAIN_PROJECT"] = "test_evaluation"

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader, DirectoryLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.documents import Document

# 평가 시스템 모듈 로드
import evaluation.main
from evaluation.main import RAGEvaluator
from evaluation.generator.dataset_generator import load_documents_from_directory, split_documents


from loguru import logger

def format_docs(docs: List[Document]) -> str:
    """
    문서 리스트를 문자열로 포맷팅합니다.
    
    Args:
        docs (List[Document]): 문서 리스트
        
    Returns:
        str: 포맷팅된 문서 내용
    """
    print(f"[format_docs] 문서 포맷팅 중 ({len(docs)}개 문서)")
    return "\n\n".join([doc.page_content for doc in docs])

def create_test_retriever(docs_dir: str = "./docs/sample"):
    """
    테스트용 검색기를 생성합니다.
    
    Args:
        docs_dir (str): 문서 디렉토리 경로
        
    Returns:
        VectorStoreRetriever: 문서 검색기
    """
    print(f"[create_test_retriever] 검색기 생성 시작: {docs_dir}")
    logger.info(f"검색기 생성 시작: {docs_dir}")
    
    try:
        # 문서 로드
        print(f"[create_test_retriever] 문서 로드 중: {docs_dir}")
        documents = []
        
        # 디렉토리 내 파일 직접 로드 (인코딩 문제 해결)
        import os
        for root, _, files in os.walk(docs_dir):
            for file in files:
                file_path = os.path.join(root, file)
                file_ext = os.path.splitext(file)[1].lower()
                
                try:
                    if file_ext == '.txt':
                        # UTF-8로 먼저 시도
                        try:
                            loader = TextLoader(file_path, encoding='utf-8')
                            file_docs = loader.load()
                            documents.extend(file_docs)
                            print(f"[create_test_retriever] 파일 로드 성공(UTF-8): {file_path}")
                        except UnicodeDecodeError:
                            # UTF-8 실패 시 CP949로 시도
                            loader = TextLoader(file_path, encoding='cp949')
                            file_docs = loader.load()
                            documents.extend(file_docs)
                            print(f"[create_test_retriever] 파일 로드 성공(CP949): {file_path}")
                    elif file_ext == '.pdf':
                        loader = PyPDFLoader(file_path)
                        file_docs = loader.load()
                        documents.extend(file_docs)
                        print(f"[create_test_retriever] PDF 파일 로드 성공: {file_path}")
                    # 추가 파일 형식에 대한 지원을 여기에 추가할 수 있습니다
                except Exception as e:
                    print(f"[create_test_retriever] 파일 로드 실패: {file_path}, 오류: {str(e)}")
                    logger.error(f"파일 로드 실패: {file_path}, 오류: {str(e)}")
        
        print(f"[create_test_retriever] 로드된 청크 수: {len(documents)}")
        logger.info(f"로드된 청크 수: {len(documents)}")
        
        if len(documents) == 0:
            print(f"[create_test_retriever] 경고: 문서가 로드되지 않았습니다! 디렉토리를 확인하세요: {docs_dir}")
            print(f"[create_test_retriever] 디렉토리 내용 확인 중...")
            # 디렉토리 내용 확인
            for root, dirs, files in os.walk(docs_dir):
                print(f"  디렉토리: {root}")
                for d in dirs:
                    print(f"    - {d}/ (디렉토리)")
                for f in files:
                    print(f"    - {f} (파일)")
        
        # 문서 분할
        print(f"[create_test_retriever] 문서 분할 중...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        splits = text_splitter.split_documents(documents)
        print(f"[create_test_retriever] 분할된 문서 청크 수: {len(splits)}")
        logger.info(f"분할된 문서 청크 수: {len(splits)}")
        
        # 임베딩 모델 초기화
        print(f"[create_test_retriever] 임베딩 모델 초기화 중...")
        #embeddings = OpenAIEmbeddings()
        location = os.getenv("GOOGLE_LOCATION_VERTEXAI")
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_VERTEXAI")
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_file(credentials_path)
        print(f"location: {location}")
        print(f"credentials_path: {credentials_path}")
        embeddings = VertexAIEmbeddings(
                                    model="text-multilingual-embedding-002",
                                    location=location,
                                    credentials=credentials)
        
        # 벡터 스토어 생성
        print(f"[create_test_retriever] 벡터 스토어 생성 중...")
        vector_store = FAISS.from_documents(splits, embeddings)
        
        # 검색기 생성
        print(f"[create_test_retriever] 검색기 생성 완료")
        logger.info(f"검색기 생성 완료")
        
        return vector_store.as_retriever(search_kwargs={"k": 4})
    
    except Exception as e:
        logger.error(f"검색기 생성 실패: {e}")
        print(f"[create_test_retriever] 검색기 생성 실패: {str(e)}")
        raise

def create_test_rag_chain(retriever, llm=None):
    """
    테스트용 RAG 체인을 생성합니다.
    
    Args:
        retriever: 검색기
        llm: 언어 모델
        
    Returns:
        Chain: RAG 체인
    """
    print(f"[create_test_rag_chain] RAG 체인 생성 시작")
    
    try:
        # 언어 모델 초기화
        if llm is None:
            print(f"[create_test_rag_chain] 언어 모델 초기화 중...")
            #llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
            llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", temperature=0.1)
        
        # 시스템 프롬프트
        print(f"[create_test_rag_chain] 시스템 프롬프트 설정 중...")
        system_prompt = """
        당신은 유용하고 정확한 정보를 제공하는 AI 어시스턴트입니다.
        제공된 컨텍스트만을 기반으로 질문에 답변하세요.
        컨텍스트에 관련 정보가 없는 경우 모른다고 솔직히 인정하세요.
        """
        
        # 프롬프트 템플릿
        print(f"[create_test_rag_chain] 프롬프트 템플릿 생성 중...")
        template = """
        <시스템>
        {system_prompt}
        </시스템>
    
        <컨텍스트>
        {context}
        </컨텍스트>
    
        <인간>
        {question}
        </인간>
    
        <AI>
        """
        
        # 프롬프트 인스턴스 생성
        print(f"[create_test_rag_chain] 프롬프트 인스턴스 생성 중...")
        prompt = ChatPromptTemplate.from_template(template)
        
        # RAG 체인 구성
        print(f"[create_test_rag_chain] RAG 체인 구성 중...")
        rag_chain = {
            "context": retriever | format_docs,
            "question": RunnablePassthrough(),
            "system_prompt": RunnablePassthrough() | (lambda _: system_prompt)
        } | prompt | llm | StrOutputParser()
        
        print(f"[create_test_rag_chain] RAG 체인 생성 완료")
        
        return rag_chain
        
    except Exception as e:
        print(f"[create_test_rag_chain] RAG 체인 생성 실패: {str(e)}")
        logger.error(f"RAG 체인 생성 실패: {e}")
        raise

def run_sample_evaluation():
    """
    샘플 평가를 실행합니다.
    """
    print(f"[run_sample_evaluation] 샘플 평가 시작")
    
    # 작업 디렉토리 설정
    docs_dir = "./evaluation/docs/sample"
    datasets_dir = "./evaluation/datasets/sample"
    results_dir = "./evaluation/results/sample"
    
    print(f"[run_sample_evaluation] 작업 디렉토리 설정 - 문서: {docs_dir}, 데이터셋: {datasets_dir}, 결과: {results_dir}")
    
    # 초기화
    try:
        print(f"[run_sample_evaluation] RAGEvaluator 초기화 중...")
        evaluator = RAGEvaluator(
            docs_dir=docs_dir,
            datasets_dir=datasets_dir,
            results_dir=results_dir,
            use_langsmith=False
        )
        print(f"[run_sample_evaluation] RAGEvaluator 초기화 완료")
    except Exception as e:
        logger.error(f"RAGEvaluator 초기화 실패: {e}")
        print(f"[run_sample_evaluation] RAGEvaluator 초기화 실패: {str(e)}")
        return None
    
    # 검색기 초기화
    try:
        print(f"[run_sample_evaluation] 테스트 검색기 초기화 중...")
        retriever = create_test_retriever(docs_dir)
        print(f"[run_sample_evaluation] 테스트 검색기 초기화 완료")
    except Exception as e:
        logger.error(f"검색기 초기화 실패: {e}")
        print(f"[run_sample_evaluation] 검색기 초기화 실패: {str(e)}")
        return None
    
    # 체인 초기화
    try:
        print(f"[run_sample_evaluation] 테스트 RAG 체인 초기화 중...")
        chain = create_test_rag_chain(retriever)
        print(f"[run_sample_evaluation] 테스트 RAG 체인 초기화 완료")
    except Exception as e:
        logger.error(f"체인 초기화 실패: {e}")
        print(f"[run_sample_evaluation] 체인 초기화 실패: {str(e)}")
        return None
    
    # 샘플 쿼리 생성
    sample_query = "인공지능의 발전 방향은 무엇인가요?"
    print(f"[run_sample_evaluation] 샘플 쿼리: '{sample_query}'")
    
    # 검색 평가
    try:
        print(f"[run_sample_evaluation] 샘플 검색 평가 시작...")
        retrieved_docs = retriever.get_relevant_documents(sample_query)
        print(f"[run_sample_evaluation] 검색된 문서 수: {len(retrieved_docs)}")
        
        if retrieved_docs:
            for i, doc in enumerate(retrieved_docs[:3]):  # 처음 3개만 출력
                print(f"[run_sample_evaluation] 문서 {i+1} 미리보기: {doc.page_content[:100]}...")
        else:
            print(f"[run_sample_evaluation] 검색된 문서 없음!")
    except Exception as e:
        logger.error(f"검색 평가 실패: {e}")
        print(f"[run_sample_evaluation] 검색 평가 실패: {str(e)}")
        return None
    
    # 생성 평가
    try:
        print(f"[run_sample_evaluation] 샘플 생성 평가 시작...")
        chain_result = chain.invoke(sample_query)
        print(f"[run_sample_evaluation] 생성 결과: {chain_result[:100]}...")
    except Exception as e:
        logger.error(f"생성 평가 실패: {e}")
        print(f"[run_sample_evaluation] 생성 평가 실패: {str(e)}")
        return None
    
    # 평가 완료
    print(f"[run_sample_evaluation] 샘플 평가 완료")
    
    return {
        "retrieval": {"docs": [doc.page_content for doc in retrieved_docs]},
        "generation": {"result": chain_result}
    }

def run_langsmith_evaluation():
    """
    LangSmith를 사용한 샘플 평가를 실행합니다.
    """
    logger.info("LangSmith 평가 시작")
    
    # 평가기 초기화
    evaluator = RAGEvaluator(use_langsmith=True)
    
    # LangSmith를 사용할 수 없는 경우
    if not evaluator.use_langsmith:
        logger.error("LangSmith가 비활성화되어 있습니다. API 키를 확인하세요.")
        return
    
    # 데이터셋 생성
    dataset_paths = evaluator.generate_datasets()
    
    if not dataset_paths:
        logger.error("데이터셋 생성 실패")
        return
    
    dataset_path = dataset_paths[0]
    logger.info(f"사용할 데이터셋: {dataset_path}")
    print(f"사용할 데이터셋: {dataset_path}")
    
    # 테스트 검색기 생성
    retriever = create_test_retriever(evaluator.docs_dir)
    
    # 테스트 RAG 체인 생성
    rag_chain = create_test_rag_chain(retriever)
    
    # 테스트 생성기 함수
    def test_generator(query, docs):
        context = "\n\n".join(docs)
        return rag_chain.invoke(query)
    
    # LangSmith 데이터셋 준비
    dataset_id = evaluator.prepare_langsmith_dataset(dataset_path)
    print(f"dataset_id: {dataset_id}")
    if not dataset_id:
        logger.error("LangSmith 데이터셋 준비 실패")
        return
    
    # 검색 평가
    retrieval_results = evaluator.langsmith_evaluator.evaluate_retrieval(
        retriever=retriever,
        dataset_id=dataset_id,
        retriever_name="test_retriever"
    )
    logger.info(f"LangSmith 검색 평가 완료")
    
    # 생성 평가
    generation_results = evaluator.langsmith_evaluator.evaluate_generation(
        dataset_id=dataset_id,
        generation_model_name="test_generator",
        generation_fn=test_generator,
        retriever_fn=lambda query: [doc.page_content for doc in retriever.get_relevant_documents(query)]
    )
    logger.info(f"LangSmith 생성 평가 완료")
    
    logger.info("LangSmith 평가 완료")
    
    return {
        "retrieval": retrieval_results,
        "generation": generation_results
    }

if __name__ == "__main__":
    import sys
    
    print("=" * 80)
    print("테스트 평가 프로그램 시작")
    print("=" * 80)
    
    # 실행 모드 확인
    if len(sys.argv) > 1 and sys.argv[1] == "run_langsmith":
        print("LangSmith 평가 모드로 실행합니다.")
        logger.info("LangSmith 평가 모드로 실행합니다.")
        result = run_langsmith_evaluation()
    else:
        print("일반 샘플 평가 모드로 실행합니다.")
        logger.info("일반 샘플 평가 모드로 실행합니다.")
        result = run_sample_evaluation()
    
    print("=" * 80)
    print("테스트 평가 프로그램 종료")
    if result:
        print(f"결과: 성공")
    else:
        print(f"결과: 실패 또는 결과 없음")
    print("=" * 80) 