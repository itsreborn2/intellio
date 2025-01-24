import google.generativeai as genai
import os
import sys
import vertexai
from vertexai.language_models import TextEmbeddingModel
import logging
from dotenv import load_dotenv
from google.oauth2 import service_account
from langchain.text_splitter import RecursiveCharacterTextSplitter
from openai import OpenAI

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
        "안녕하세요, 한국어 텍스트입니다.",
            "자연어 처리는 인공지능의 중요한 분야입니다.",
            "KF-Deberta는 한국어에 특화된 모델입니다.",
            "이 모델은 한국어 문장의 의미를 잘 파악합니다."
    ]
    
    try:
        # 임베딩 생성
        embeddings = model.get_embeddings(texts)
        
        # 결과 출력
        for i, embedding in enumerate(embeddings):
            logger.info(f"Text {i+1}: {texts[i]}")
            logger.info(f"Embedding dimension: {len(embedding.values)}")
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

def test_deepseek():
    API_KEY = "sk-3a57a56bfeae4a5288a6757c3d5b243a"
    client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
        ],
        stream=False
    )

    print(response.choices[0].message.content)
    pass
if __name__ == "__main__":
    #test_vertex_embedding()
    #test_kakao_embedding() 
    test_deepseek()