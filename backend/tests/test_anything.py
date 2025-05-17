import asyncio
from datetime import datetime
import os
import sys
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from common.app import LoadEnvGlobal
# 환경 변수 로드
LoadEnvGlobal()
from common.services.embedding_models import EmbeddingModelType
from common.services.embedding import EmbeddingService

from common.services.llm_models import LLMModels
import vertexai
from vertexai.language_models import TextEmbeddingModel
from loguru import logger

from google.oauth2 import service_account

from openai import OpenAI
from common.core.config import settings

from langchain_openai import OpenAIEmbeddings

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai.embeddings import VertexAIEmbeddings

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from rich.console import Console





# 로깅 설정
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

async def test_google_storage_service():
    from common.services.storage import GoogleCloudStorageService
    
    storage = GoogleCloudStorageService(
        project_id=settings.GOOGLE_CLOUD_PROJECT,
        bucket_name=settings.GOOGLE_CLOUD_STORAGE_BUCKET_STOCKEASY,
        credentials_path=settings.GOOGLE_APPLICATION_CREDENTIALS
    )
    folder_path = Path("telegram_files/2025-02-28")
    
    # 폴더 내 모든 파일 순회
    for file_path in folder_path.iterdir():
        if file_path.is_file():  # 파일인 경우에만 처리
            print(f"파일 처리 중: {file_path.name}")
            
            # 여기에 각 파일에 대한 처리 로직 추가
            # 예: 파일 업로드, 파일 처리 등
            
            # 예시: 파일 정보 출력
            file_size = file_path.stat().st_size
            print(f"  - 파일 크기: {file_size} 바이트")
            
            # 비동기 작업이 필요한 경우 await 사용
            # file_path = "telegram_files/2025-02-28/SK이터닉스［475150］매력적인_신성장_동력_확보_20250228_Kiwoom_982560.pdf"
            target_path = "Stockeasy/collected_auto/탤래그램/dev/공식/"
            target_full_path = target_path + file_path.name
            await storage.upload_from_filename(target_full_path, file_path)

    
    #ss = await storage.get_download_url("AMD AI 컨퍼런스_2023.12.06.docx")
    #print(ss)
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
    print(f"bucket: {settings.GOOGLE_CLOUD_STORAGE_BUCKET_DOCEASY}")
    bucket = storage_client.bucket(settings.GOOGLE_CLOUD_STORAGE_BUCKET_DOCEASY)
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

def test_upstage_embedding():
    embed_service = EmbeddingService()
    embed_service.change_model(EmbeddingModelType.UPSTAGE)
    
    text = "DeepSeek 성능이 매우 좋아졌다고 최근 기사에 많이 나오네. 얼마나 좋아졌니?"
    query_result = embed_service.create_single_embedding(text)
    print(query_result[:5])
    print(f'dimension : {len(query_result)}')

def test_bgem3_embedding():
    from sentence_transformers import SentenceTransformer

    # Download from the 🤗 Hub
    model = SentenceTransformer("dragonkue/bge-m3-ko")
    # Run inference
    sentences = [
        '수급권자 중 근로 능력이 없는 임산부는 몇 종에 해당하니?',
        '내년부터 저소득층 1세 미만 아동의 \n의료비 부담이 더 낮아진다!\n의료급여제도 개요\n□ (목적) 생활유지 능력이 없거나 생활이 어려운 국민들에게 발생하는 질병, 부상, 출산 등에 대해 국가가 의료서비스 제공\n□ (지원대상) 국민기초생활보장 수급권자, 타 법에 의한 수급권자 등\n\n| 구분 | 국민기초생활보장법에 의한 수급권자 | 국민기초생활보장법 이외의 타 법에 의한 수급권자 |\n| --- | --- | --- |\n| 1종 | ○ 국민기초생활보장 수급권자 중 근로능력이 없는 자만으로 구성된 가구 - 18세 미만, 65세 이상 - 4급 이내 장애인 - 임산부, 병역의무이행자 등 | ○ 이재민(재해구호법) ○ 의상자 및 의사자의 유족○ 국내 입양된 18세 미만 아동○ 국가유공자 및 그 유족․가족○ 국가무형문화재 보유자 및 그 가족○ 새터민(북한이탈주민)과 그 가족○ 5․18 민주화운동 관련자 및 그 유가족○ 노숙인 ※ 행려환자 (의료급여법 시행령) |\n| 2종 | ○ 국민기초생활보장 수급권자 중 근로능력이 있는 가구 | - |\n',
        '이어 이날 오후 1시30분부터 열릴 예정이던 스노보드 여자 슬로프스타일 예선 경기는 연기를 거듭하다 취소됐다. 조직위는 예선 없이 다음 날 결선에서 참가자 27명이 한번에 경기해 순위를 가리기로 했다.',
    ]
    embeddings = model.encode(sentences)
    print(embeddings.shape)
    # [3, 1024]

    # Get the similarity scores for the embeddings
    similarities = model.similarity(embeddings, embeddings)
    print(similarities.shape)
    # [3, 3]
    print(embeddings[0][:5])
    
    # text = "DeepSeek 성능이 매우 좋아졌다고 최근 기사에 많이 나오네. 얼마나 좋아졌니?"
    # query_result = embed_service.create_single_embedding(text)
    # print(query_result[:5])
    # print(f'dimension : {len(query_result)}')

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

    print(query_result[:5])
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
    #print(f'settings.GEMINI_API_KEY: {settings.GEMINI_API_KEY}')

    prompt = """너는 금융 및 주식 관련 질문 분류 전문가이자, LLM 기반 질문분류기 역할을 수행한다.
사용자가 입력한 질문을 아래의 기준에 따라 분석하고, 각 항목에 대해 분류 결과를 도출해줘.

1. 질문 주제:
   - [종목 기본 정보]: 기업의 재무, 배당, 주가, 시세 등 기초 정보와 관련된 질문.
   - [전망 관련]: 미래 전망, 투자 의견, 시장 분석, 미래 예측 등 미래의 흐름이나 전략에 관한 질문.
   - [기타]: 위 두 항목에 포함되지 않는 금융/주식 관련 기타 질문.

2. 답변 요구 수준:
   - [간단한 답변]: 단순 정보, 숫자 혹은 짧은 단답형 답변이 적절한 경우.
   - [긴 설명 요구]: 배경 정보, 근거 및 상세 설명이 필요한 경우.
   - [종합적 판단]: 다양한 변수와 복합적 요소를 고려해 판단해야 하는 경우.

3. 추가 옵션 (선택 사항):
   - 만약 분류 결과에 따라 특정 DB 조회나 임베딩 검색 옵션이 달라져야 한다면, 그에 맞는 제안도 함께 제공해줘.
   - 예를 들어, "종목 기본 정보"에 해당하면 재무 데이터베이스, "전망 관련"이라면 시장 분석 리포트를 참고하는 옵션 등을 제안할 수 있음.

사용자 질문 예시: "A기업의 배당률이 어떻게 되나요?"
- 분석 결과 예시:
   - 질문 주제: [종목 기본 정보]
   - 답변 요구 수준: [간단한 답변]
   - 추가 옵션: 재무 데이터베이스 조회

사용자 질문 예시: "B기업의 향후 성장 가능성과 시장 전망은 어떻게 보시나요?"
- 분석 결과 예시:
   - 질문 주제: [전망 관련]
   - 답변 요구 수준: [긴 설명 요구] 또는 [종합적 판단]
   - 추가 옵션: 시장 분석 리포트 및 전문가 의견 임베딩 검색

이와 같은 형식으로 사용자 질문에 대한 분류 결과를 도출해줘."""
    #response = llm.generate("삼성전자 살까?지금이니?", prompt)
    response = llm.generate("하이닉스 24년 매출은?", prompt)
    
    print(response.content)

    
async def test_func_aync():
    print(f"ENV : {settings.ENV}")
    from common.services.vector_store_manager import VectorStoreManager
    from common.services.embedding_models import EmbeddingModelType
    from stockeasy.services.telegram.rag import TelegramRAGService

    rag_service = TelegramRAGService()
    messages = await rag_service.search_messages("로봇주들 급락이 심한데, 왜 이래?", 5)
    summary = await rag_service.summarize(messages)
    #summary= await rag_service.test_func()
    
    print(summary)
def test_question_classifier():
    from stockeasy.services.telegram.question_classifier import QuestionClassifierService
    question_classifier = QuestionClassifierService()
    # 사용자의 입력을 반복적으로 처리하자
    # 터미널로 입력받고, q 입력시 반복 종료
    while True:
        question = input("질문을 입력하세요: ")
        if question == "q" or question == "ㅂ":
            break
        result = question_classifier.classify_question(question)
        #result = question_classifier.classify_question_with_deberta(question)
        print(result)
        print(f"질문주제: {result['질문주제']}")
        print(f"답변수준: {result['답변수준']}")
        print(f"추가옵션: {result['추가옵션']}")
        print(f"종목코드: {result['종목코드']}")
        print(f"종목명: {result['종목명']}")
async def test_search_vectordb():
    from common.services.vector_store_manager import VectorStoreManager
    from common.services.embedding_models import EmbeddingModelType
    from common.services.retrievers.models import RetrievalResult
    from common.services.retrievers.semantic import SemanticRetriever, SemanticRetrieverConfig

    vs_manager = VectorStoreManager(embedding_model_type=EmbeddingModelType.GOOGLE_MULTI_LANG,
                                    project_name="stockeasy",
                                    namespace=settings.PINECONE_NAMESPACE_STOCKEASY_TELEGRAM)
    
    semantic_retriever = SemanticRetriever(config=SemanticRetrieverConfig(
                                                        min_score=0.6, # 최소 유사도 0.6 고정
                                                        ), vs_manager=vs_manager)

    # 시작일과 종료일 설정
    start_date = datetime(2025, 1, 1)  # 2024년 1월 1일
    end_date = datetime(2025, 3, 3)   # 2024년 3월 31일

    # ISO 형식으로 변환
    # Unix timestamp로 변환 (초 단위)
    start_timestamp = int(start_date.timestamp())
    end_timestamp = int(end_date.timestamp())

    # Pinecone 필터 쿼리
    filters = {
        "message_created_at": {
            "$gte": start_timestamp,
            "$lte": end_timestamp
        }
    }

    normalized_query = "한화에어로스페이스 실적이 왜 좋았지?"
    # # document_id와 함께 사용하는 경우
    # filters = {
    #     "created_at": {
    #         "$gte": start_date_str,
    #         "$lte": end_date_str
    #     },
    #     "document_id": {
    #         "$in": ["doc1", "doc2"]  # 특정 문서 ID 목록
    #     }
    # }
    all_chunks:RetrievalResult = await semantic_retriever.retrieve(
        query=normalized_query, 
        top_k=5,
        #filters=filters
    )
    # score 기준으로 내림차순 정렬
    sorted_documents = sorted(all_chunks.documents, key=lambda x: x.score, reverse=True)

    print(f"\n검색어: {normalized_query}")
    print("\n" + "="*100)
    
    for idx, doc in enumerate(sorted_documents, 1):
        # ISO 형식의 날짜 문자열을 datetime으로 파싱하고 한국 시간 형식으로 변환
        message_created_at_data = doc.metadata.get('message_created_at', '')
        created_at = None
        
        # message_created_at을 datetime 객체로 변환 (다양한 형식 지원)
        if isinstance(message_created_at_data, str):
            # ISO 형식 문자열인 경우
            try:
                created_at = datetime.fromisoformat(message_created_at_data)
            except (ValueError, TypeError):
                # ISO 형식이 아닌 경우 다른 형식 시도
                try:
                    # 유닉스 타임스탬프 문자열인지 확인
                    created_at = datetime.fromtimestamp(float(message_created_at_data))
                except (ValueError, TypeError):
                    # 기본값으로 현재 시간 사용
                    created_at = datetime.now()
        elif isinstance(message_created_at_data, (int, float)):
            # 유닉스 타임스탬프인 경우
            try:
                created_at = datetime.fromtimestamp(float(message_created_at_data))
            except (ValueError, TypeError):
                # 변환 실패 시 현재 시간 사용
                created_at = datetime.now()
        else:
            # 지원되지 않는 형식인 경우 현재 시간 사용
            created_at = datetime.now()
        
        created_at_str = created_at.strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"\n[검색결과 {idx}, 점수:{doc.score}]")
        print(f"채널명: {doc.metadata.get('channel_title', '채널명 없음')}")
        print(f"작성일시: {created_at_str}")
        print(f"내용: {doc.page_content}")
        print("-"*100)
    
    print(f"\n총 {len(all_chunks.documents)}개의 결과가 검색되었습니다.")
    
    
    
    
    
if __name__ == "__main__":
    #print(os.getcwd())
    #test_google_storage_service()
    #asyncio.run(test_google_storage_service())
    #test_gemini_generate()
    #test_question_classifier()
    #test_upstage_embedding()
    test_get_gemini_models()
    #test_bgem3_embedding()
    #test_vertex_embedding()
    #test_kakao_embedding() 
    #test_kakao_llm()
    
    #test_kakao_gen()
    #test_openai()
    #test_func()
    #test_langchain_google_embedding()
    #asyncio.run(test_langsmith2())
    #asyncio.run(test_func_aync())
    #asyncio.run(test_search_vectordb())

