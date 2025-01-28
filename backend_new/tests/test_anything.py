import google.generativeai as genai
import os

import sys
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

import vertexai
from vertexai.language_models import TextEmbeddingModel
import logging
from dotenv import load_dotenv
from google.oauth2 import service_account
from langchain.text_splitter import RecursiveCharacterTextSplitter
from openai import OpenAI
from app.core.config import settings

from langchain_openai import OpenAIEmbeddings

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleVectorStore
#from langchain.embeddings import VertexAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
#from langchain_community.embeddings import VertexAIEmbeddings
from langchain_google_vertexai.embeddings import VertexAIEmbeddings

# 환경 변수 로드
load_dotenv()


def test_embedding():
    genai.configure(api_key='AIzaSyAAxQVz3-tMYra4YDIYp5JAoNrzdOaVl1Q')

    result = genai.embed_content(
            model="models/text-embedding-004",
            #model="models/multilingual-text-embedding",
            #content="What is the meaning of life?")
            content="안녕하세요 이런것도 되긴하나")

    print(str(result['embedding']))


# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_vertex_embedding():
    # Vertex AI 초기화
    project_id = os.getenv("GOOGLE_PROJECT_ID_VERTEXAI")
    location = os.getenv("GOOGLE_LOCATION_VERTEXAI", "asia-northeast3")
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_VERTEXAI", "")
    if not project_id:
        raise ValueError("GOOGLE_PROJECT_ID_VERTEXAI 환경 변수가 설정되지 않았습니다.")
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
        model = AutoModel.from_pretrained("app/kf-deberta")
        tokenizer = AutoTokenizer.from_pretrained("app/kf-deberta")
        
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

def test_openai_streaming():
    API_KEY = settings.OPENAI_API_KEY
    if not API_KEY:
        raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
    
    client = OpenAI(api_key=API_KEY)

    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",  # GPT-4 모델 사용
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "DeepSeek 성능이 매우 좋아졌다고 최근 기사에 많이 나오네. 얼마나 좋아졌니?"},
        ],
        stream=True
    )

    full_response = ""
    for chunk in response:
        if chunk.choices[0].delta.content is not None:
            content = chunk.choices[0].delta.content
            full_response += content
            print(content, end="", flush=True)
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
    #embeddings = GoogleGenerativeAIEmbeddings(api_key=os.getenv("GOOGLE_PROJECT_ID_VERTEXAI"), 
                                            #   model="text-multilingual-embedding-002",
                                            #   credentials=os.getenv("GOOGLE_APPLICATION_CREDENTIALS_VERTEXAI"))
    
    embeddings = VertexAIEmbeddings(
                                    model="text-multilingual-embedding-002",
                                    credentials=credentials)
    
    text = "DeepSeek 성능이 매우 좋아졌다고 최근 기사에 많이 나오네. 얼마나 좋아졌니?"
    #query_result = embeddings.embed_query(text)
    query_result = embeddings.embed([text], embeddings_task_type="SEMANTIC_SIMILARITY")
    
    print(query_result[0][:5])


def test_func():
    token = "###"
    is_only_markdown = bool(token.strip().replace('#', '').replace('*', '').replace('_', '').strip() == '')
    print(is_only_markdown)
if __name__ == "__main__":
    print(os.getcwd())
    #test_vertex_embedding()
    #test_kakao_embedding() 
    #test_openai()
    #test_func()
    test_langchain_google_embedding()

