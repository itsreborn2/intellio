import asyncio
import os
import sys
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from common.app import LoadEnvGlobal
from common.services.llm_models import LLMModels
import vertexai
from vertexai.language_models import TextEmbeddingModel
import logging

from google.oauth2 import service_account
from langchain.text_splitter import RecursiveCharacterTextSplitter

from openai import OpenAI
from common.core.config import settings

from langchain_openai import OpenAIEmbeddings
from langchain_core.messages import BaseMessage, ChatMessage, ai
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleVectorStore
#from langchain.embeddings import VertexAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
#from langchain_community.embeddings import VertexAIEmbeddings
from langchain_google_vertexai.embeddings import VertexAIEmbeddings

from langsmith import Client
from langchain_core.tracers import LangChainTracer
from langchain_core.callbacks import CallbackManager
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.globals import set_debug

from rich import print as rprint
from rich.panel import Panel
from rich.console import Console
from rich.table import Table

# 환경 변수 로드
LoadEnvGlobal()


# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_google_storage_service():
    from common.services.storage import GoogleCloudStorageService
    storage = GoogleCloudStorageService(
        project_id=settings.GOOGLE_CLOUD_PROJECT,
        bucket_name=settings.GOOGLE_CLOUD_STORAGE_BUCKET,
        credentials_path=settings.GOOGLE_APPLICATION_CREDENTIALS
    )
    #await storage.upload_file("test2.txt", "Hello, World!2222222")
    ss = await storage.get_download_url("AMD AI 컨퍼런스_2023.12.06.docx")
    print(ss)
    #storage.upload_file("test3.txt", "Hello, World!3333333")

def test_google_storage():
    # 인증 설정
    from google.cloud import storage
    from google.oauth2 import service_account
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_VERTEXAI", "")
    credentials = service_account.Credentials.from_service_account_file(credentials_path)

    # 스토리지 클라이언트 초기화
    storage_client = storage.Client(credentials=credentials)
    buckets = list(storage_client.list_buckets())
    print("Storage Buckets:", [bucket.name for bucket in buckets])
    # 버킷 접근
    print(f"bucket: {settings.GOOGLE_CLOUD_STORAGE_BUCKET}")
    bucket = storage_client.bucket(settings.GOOGLE_CLOUD_STORAGE_BUCKET)
    # # 테스트 파일 업로드
    # blob = bucket.blob('test.txt')
    # blob.upload_from_string('Hello, World!')

    # 기존 파이 업로그
    # file_path = 'D:/Work/닥이지_테스트문서/화장품_3QPre_견조한_업황,_실적은_기대치_부합_예상.pdf'# 파일명만 추출 (경로 제외)
    # file_name = os.path.basename(file_path)
    
    # # 스토리지에 업로드 (documents 폴더 아래에 저장)
    # blob = bucket.blob(f'doc/{file_name}')
    # blob.upload_from_filename(file_path)
    
    # print(f"파일 업로드 완료: {file_name}")
    blobs = bucket.list_blobs()
    print("\n=== 전체 파일 목록 ===")
    for blob in blobs:
        print(f"- {blob.name} (크기: {blob.size} bytes)")


    #2. 특정 폴더 내 파일 리스트
    prefix = "doc/"  # 폴더 경로
    delimiter = "/"        # 폴더 구분자
    blobs = bucket.list_blobs(prefix=prefix, delimiter=delimiter)
    
    print(f"\n=== {prefix} 폴더 내 파일 목록 ===")
    for blob in blobs:
        print(f"- {blob.name}")
    
    # 3. 폴더 목록 (prefix로 시작하는 하위 폴더들)
    print(f"\n=== {prefix} 하위 폴더 목록 ===")
    for prefix in blobs.prefixes:
        print(f"- {prefix}")

    blobs = bucket.list_blobs()
    print("\n=== 상세 파일 정보 ===")
    for blob in blobs:
        print(f"""
파일명: {blob.name}
크기: {blob.size:,} bytes
생성일: {blob.time_created}
수정일: {blob.updated}
Content Type: {blob.content_type}
다운로드 URL: {blob.public_url if blob.public_url else '비공개'}
-------------------""")

def test_vertex_embedding():
    # Vertex AI 초기화
    project_id = os.getenv("GOOGLE_PROJECT_ID_VERTEXAI")
    location = os.getenv("GOOGLE_LOCATION_VERTEXAI", "asia-northeast3")
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_VERTEXAI", "")
    if not project_id:
        raise ValueError("GOOGLE_PROJECT_ID_VERTEXAI 환경 변수가 설정되지 않았습니다.")
    print(f'project_id: {project_id}')
    print(f'location: {location}')
    print(f'credentials_path: {credentials_path}')
    # 서비스 계정 키 JSON 파일로부터 credentials 객체 생성
    credentials = service_account.Credentials.from_service_account_file(credentials_path)
    

    vertexai.init(project=project_id, location=location, credentials=credentials)
    
    # 임베딩 모델 로드
    #model = TextEmbeddingModel.from_pretrained("textembedding-gecko@latest")
    model = TextEmbeddingModel.from_pretrained("text-multilingual-embedding-002")
    #model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    
    # 테스트할 텍스트
    texts = [
        "DeepSeek 성능이 매우 좋아졌다고 최근 기사에 많이 나오네. 얼마나 좋아졌니?",
    ]
    
    try:
        # 임베딩 생성
        embeddings = model.get_embeddings(texts)
        
        # 결과 출력
        for i, embedding in enumerate(embeddings):
            #logger.info(f"Text {i+1}: {texts[i]}")
            #logger.info(f"Embedding dimension: {len(embedding.values)}")
            logger.info(f"First 5 values: {embedding.values[:5]}")
            logger.info("-" * 50)
            
        return True
        
    except Exception as e:
        logger.error(f"임베딩 생성 중 오류 발생: {str(e)}")
        raise

def test_kakao_embedding():
    """KF-Deberta 모델을 사용한 임베딩 테스트"""
    try:
        from transformers import AutoModel, AutoTokenizer
        import torch
        
        # 모델과 토크나이저 로드
        model = AutoModel.from_pretrained(settings.KAKAO_EMBEDDING_MODEL_PATH)
        tokenizer = AutoTokenizer.from_pretrained(settings.KAKAO_EMBEDDING_MODEL_PATH)
        

        # 테스트할 텍스트
        texts = [
            "안녕하세요, 한국어 텍스트입니다.",
            "자연어 처리는 인공지능의 중요한 분야입니다.",
            "KF-Deberta는 한국어에 특화된 모델입니다.",
            "이 모델은 한국어 문장의 의미를 잘 파악합니다."
        ]
        
        logger.info("KF-Deberta 임베딩 테스트 시작")
        
        #text_splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(tokenizer)
        for i, text in enumerate(texts):
            # 토큰화
            inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            tokens = tokenizer.tokenize(text)
            other_tokens = tokenizer.encode(text)
            logger.info(f"토큰화 결과: {tokens}, 토큰수: {len(tokens)}")
            logger.info(f"토큰화 결과: {other_tokens}, 토큰수: {len(other_tokens)}")
            # 모델 추론
            with torch.no_grad():
                outputs = model(**inputs)
            
            # [CLS] 토큰의 임베딩 추출 (문장 전체 표현)
            sentence_embedding = outputs.last_hidden_state[0, 0, :].numpy()
            
            logger.info(f"\nText {i+1}: {text}")
            #logger.info(f"임베딩 차원: {len(sentence_embedding)}")
            #logger.info(f"처음 5개 값: {sentence_embedding[:5]}")
            logger.info("-" * 50)
        
        return True
        
    except Exception as e:
        logger.error(f"KF-Deberta 임베딩 생성 중 오류 발생: {str(e)}")
        raise
def test_kakao_gen():
    from transformers import AutoModel, AutoTokenizer
    import torch
    
    # 모델과 토크나이저 로드
    model = AutoModel.from_pretrained(settings.KAKAO_EMBEDDING_MODEL_PATH)
    tokenizer = AutoTokenizer.from_pretrained(settings.KAKAO_EMBEDDING_MODEL_PATH)
        
    # 메시지 내용 추출
    text = "안녕"
    
    # 토큰화 및 모델 입력 준비
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    
    # 모델 추론
    with torch.no_grad():
        model_output = model(**inputs)
    
    # 마지막 히든 스테이트 사용
    last_hidden_state = model_output.last_hidden_state
    
    # 마지막 토큰의 임베딩을 사용하여 응답 생성
    last_token_embedding = last_hidden_state[0, -1, :]
    
    # 임베딩을 문자열로 변환
    response = f"{last_token_embedding[:5].tolist()}"
    print(response)
def test_kakao_llm():
    llm = LLMModels()
    response = llm.generate("안녕하세요", "반갑게 인사해줘")
    print(response)
    
def test_openai_embedding():
    API_KEY = settings.OPENAI_API_KEY
    if not API_KEY:
        raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
    
    embeddings = OpenAIEmbeddings(api_key=settings.OPENAI_API_KEY,
                                  model="text-embedding-ada-002")
    text = "DeepSeek 성능이 매우 좋아졌다고 최근 기사에 많이 나오네. 얼마나 좋아졌니?"
    query_result = embeddings.embed_query(text)
    print(query_result[:5])

def test_langchain_google_embedding():
    credentials = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS_VERTEXAI")
    )
    
    embeddings = VertexAIEmbeddings(
                                    model="text-multilingual-embedding-002",
                                    credentials=credentials)
    
    text = "DeepSeek 성능이 매우 좋아졌다고 최근 기사에 많이 나오네. 얼마나 좋아졌니?"
    #query_result = embeddings.embed_query(text)
    query_result = embeddings.embed([text], embeddings_task_type="SEMANTIC_SIMILARITY")
    
    print(query_result[0][:5])
def test_langsmith():
    # Gemini 모델 초기화
    llm = ChatGoogleGenerativeAI(
        model="models/gemini-2.0-flash-exp",
        convert_system_message_to_human=True,
        temperature=0.7,
        google_api_key=settings.GEMINI_API_KEY,
    )
    
    # 프롬프트 템플릿 정의
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "당신은 전문적이고 도움이 되는 AI 어시스턴트입니다. 한국어로 자연스럽게 대화하며, 정확하고 유용한 정보를 제공합니다."),
        ("user", "{input}")
    ])
    
    # 출력 파서 정의
    output_parser = StrOutputParser()
    
    # 테스트 실행
    questions = [
        "한국의 역대 대통령 이름만 알려줘",
    ]
    
    for question in questions:
        print(f"\n질문: {question}")
        try:
            # 1. 프롬프트 템플릿으로 메시지 생성
            formatted_messages = prompt_template.format_messages(input=question)
            
            # 2. LLM으로 응답 생성
            llm_response = llm.invoke(formatted_messages)
            
            # 3. 출력 파서로 응답 파싱
            #final_response = output_parser.invoke(llm_response.content)
            
            print(f"응답: {llm_response.content}\n")
            print("-" * 50)
        except Exception as e:
            print(f"오류 발생: {str(e)}")
            raise
async def test_langsmith2():
    # Gemini 모델 초기화
    llm = ChatGoogleGenerativeAI(
        model="models/gemini-2.0-flash-exp",
        convert_system_message_to_human=True,
        temperature=0.7,
        google_api_key=settings.GEMINI_API_KEY,
    )
    
    # 프롬프트 템플릿 정의
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "당신은 전문적이고 도움이 되는 AI 어시스턴트입니다. 한국어로 자연스럽게 대화하며, 정확하고 유용한 정보를 제공합니다."),
        ("user", "{input}")
    ])
    
    # 테스트 실행
    questions = [
        "오늘의 가장 언급이 많이된 뉴스는?",
    ]
    
    for question in questions:
        print(f"\n질문: {question}")
        try:
            formatted_messages = prompt_template.format_messages(input=question)
            
            async for chunk in llm.astream(formatted_messages):
                if chunk.content:
                    print(chunk.content, end="", flush=True)
            
            print("\n" + "-" * 50)
        except Exception as e:
            print(f"오류 발생: {str(e)}")
            raise

def test_get_gemini_models():
    # 프로젝트 이름을 입력합니다.
    from google.ai import generativelanguage_v1beta
    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY) # YOUR_API_KEY를 실제 API 키로 변경

    # 사용 가능한 모델 목록 조회
    try:
        for model in genai.list_models():
            print(f"모델 이름: {model.name}")
            print(f"표시 이름: {model.display_name}")
            print("---")
    except Exception as e:
        print(f"오류 발생: {e}")
def test_gemini_generate():
    llm = LLMModels()
    print(f'settings.GEMINI_API_KEY: {settings.GEMINI_API_KEY}')
    response = llm.generate("안녕하세요", "반갑게 인사해줘")
    
    print(response.content)
def test_func():
    
    console = Console()
    
    

    
    
    
    
    
async def test_func_aync():
    from common.services.vector_store_manager import VectorStoreManager
    from common.services.embedding_models import EmbeddingModelType
    from stockeasy.services.telegram.rag import TelegramRAGService

    rag_service = TelegramRAGService()
    messages = await rag_service.search_messages("로봇주들 급락이 심한데, 왜 이래?", 5)
    summary = await rag_service.summarize(messages)
    print(summary)
    
if __name__ == "__main__":
    #print(os.getcwd())
    #test_google_storage()
    #asyncio.run(test_google_storage_service())
    test_gemini_generate()
    #test_vertex_embedding()
    #test_kakao_embedding() 
    #test_kakao_llm()
    
    #test_kakao_gen()
    #test_openai()
    #test_func()
    #test_langchain_google_embedding()
    #asyncio.run(test_langsmith2())
    #asyncio.run(test_func_aync())

