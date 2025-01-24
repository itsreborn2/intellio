import os
import openai
import pinecone
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import PyPDFLoader

# Step 1: OpenAI 및 Pinecone API 키 설정
openai.api_key = os.getenv("OPENAI_API_KEY")  # OpenAI API 키
pinecone.init(
    api_key=os.getenv("PINECONE_API_KEY"),  # Pinecone API 키
    environment="us-west1-gcp"  # Pinecone 환경 (예: us-west1-gcp)
)

# Step 2: Pinecone 인덱스 생성 또는 연결
index_name = "example-index"
if index_name not in pinecone.list_indexes():
    pinecone.create_index(name=index_name, dimension=1536, metric="cosine")
index = pinecone.Index(index_name)

# Step 3: 파일에서 텍스트 추출 (PDF 로더 사용)
def extract_text_from_file(file_path):
    loader = PyPDFLoader(file_path)
    documents = loader.load()
    return " ".join([doc.page_content for doc in documents])

# Step 4: 텍스트 분리 (청킹)
def split_text_into_chunks(text, chunk_size=1500, chunk_overlap=200):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " "]
    )
    chunks = splitter.split_text(text)
    return chunks

# Step 5: OpenAI 임베딩 생성 함수 정의
def get_embedding(text, model="text-embedding-ada-002"):
    response = openai.Embedding.create(input=[text], model=model)
    return response['data'][0]['embedding']

# Step 6: 청크 임베딩 생성 및 Pinecone에 업로드
def embed_and_store_chunks(chunks):
    for i, chunk in enumerate(chunks):
        embedding = get_embedding(chunk)  # 임베딩 생성
        metadata = {"text": chunk}       # 메타데이터 추가 (원본 텍스트 저장)
        index.upsert([(str(i), embedding, metadata)])  # Pinecone에 업로드

# Step 7: 전체 파이프라인 실행
def process_file(file_path):
    print("Step 1: Extracting text from file...")
    text = extract_text_from_file(file_path)
    
    print("Step 2: Splitting text into chunks...")
    chunks = split_text_into_chunks(text)
    
    print(f"Step 3: Generating embeddings and storing in Pinecone ({len(chunks)} chunks)...")
    embed_and_store_chunks(chunks)
    
    print("Process completed successfully!")

# 실행 예시 (사용자 업로드 파일 경로)
file_path = "path_to_your_uploaded_file.pdf"  # 사용자 업로드 파일 경로 입력
process_file(file_path)
