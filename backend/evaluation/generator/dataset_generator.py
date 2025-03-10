"""
평가를 위한 데이터셋 생성 모듈
"""
import os
import json
import random
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path
import hashlib
import glob

from langchain_community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.language_models import BaseLanguageModel
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, field_validator

# 평가 시스템 설정 불러오기
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DOCS_DIR, DATASETS_DIR, DATASET_CONFIG

class GeneratedQuery(BaseModel):
    """생성된 쿼리 모델"""
    question: str = Field(description="쿼리 질문")
    answer: str = Field(description="쿼리에 대한 답변")
    relevant_doc_indices: List[int] = Field(description="관련 문서 인덱스 목록")
    
    @field_validator("relevant_doc_indices")
    def validate_doc_indices(cls, v):
        if not v:
            raise ValueError("적어도 하나의 관련 문서 인덱스가 있어야 합니다")
        return v

class RAGEvaluationDataset(BaseModel):
    """RAG 평가용 데이터셋 모델"""
    name: str = Field(description="데이터셋 이름")
    queries: List[Dict[str, Any]] = Field(description="쿼리 목록")
    documents: List[Dict[str, Any]] = Field(description="문서 목록")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="메타데이터")

def load_documents_from_directory(
    directory_path: str, 
    glob_pattern: str = "**/*.pdf"
) -> List[Document]:
    """
    디렉토리에서 문서를 로드합니다.
    
    Args:
        directory_path (str): 문서 디렉토리 경로
        glob_pattern (str): 로드할 파일의 glob 패턴
        
    Returns:
        List[Document]: 로드된 문서 리스트
    """
    print(f"[load_documents_from_directory] 문서 로드 시작: {directory_path}")
    print(f"[load_documents_from_directory] 패턴 사용: {glob_pattern}")
    
    documents = []
    directory_path = os.path.abspath(directory_path)
    file_paths = []
    
    # glob을 사용하여 파일 찾기
    try:
        for file_path in glob.glob(os.path.join(directory_path, glob_pattern), recursive=True):
            if os.path.isfile(file_path):
                file_paths.append(file_path)
                
        print(f"[load_documents_from_directory] 찾은 파일 수: {len(file_paths)}")
        
        if len(file_paths) == 0:
            print(f"[load_documents_from_directory] 경고: 파일을 찾을 수 없음. 디렉토리 경로 확인 필요: {directory_path}")
            # 디렉토리 내용 확인
            print(f"[load_documents_from_directory] 디렉토리 내용:")
            for root, dirs, files in os.walk(directory_path):
                print(f"  디렉토리: {root}")
                for d in dirs:
                    print(f"    - {d}/ (디렉토리)")
                for f in files:
                    print(f"    - {f} (파일)")
        
        # 파일 로드
        for file_path in file_paths:
            try:
                print(f"[load_documents_from_directory] 파일 로드 중: {file_path}")
                file_extension = os.path.splitext(file_path)[1].lower()
                
                if file_extension == '.pdf':
                    loader = PyPDFLoader(file_path=file_path)
                    file_documents = loader.load()
                elif file_extension in ['.txt', '.md', '.html']:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    file_documents = [Document(page_content=content, metadata={"source": file_path})]
                else:
                    print(f"[load_documents_from_directory] 지원되지 않는 파일 형식: {file_extension}, 파일: {file_path}")
                    continue
                
                # 문서 ID 추가
                for doc in file_documents:
                    doc.metadata["id"] = f"doc_{len(documents)}"
                    documents.append(doc)
                    
                print(f"[load_documents_from_directory] {file_path}에서 {len(file_documents)}개 청크 로드됨")
                
            except Exception as e:
                print(f"[load_documents_from_directory] 파일 '{file_path}' 로드 중 오류 발생: {str(e)}")
                
    except Exception as e:
        print(f"[load_documents_from_directory] 디렉토리 검색 중 오류 발생: {str(e)}")
    
    print(f"[load_documents_from_directory] 총 {len(documents)}개 청크 로드 완료")
    
    return documents

def split_documents(documents: List[Document], chunk_size: int = 1000, chunk_overlap: int = 100) -> List[Document]:
    """
    문서 리스트를 분할합니다.
    
    Args:
        documents (List[Document]): 분할할 문서 리스트
        chunk_size (int): 청크 크기
        chunk_overlap (int): 청크 오버랩
        
    Returns:
        List[Document]: 분할된 문서 리스트
    """
    print(f"[split_documents] 문서 분할 시작: {len(documents)}개 문서")
    print(f"[split_documents] 청크 크기: {chunk_size}, 오버랩: {chunk_overlap}")
    
    split_docs = []
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    try:
        split_docs = []
        
        for i, doc in enumerate(documents):
            try:
                print(f"[split_documents] 문서 {i+1}/{len(documents)} 분할 중 (길이: {len(doc.page_content)} 문자)")
                
                splits = text_splitter.split_text(doc.page_content)
                print(f"[split_documents] 문서 {i+1} 분할 결과: {len(splits)}개 청크")
                
                for j, split in enumerate(splits):
                    doc_id = f"{doc.metadata.get('id', f'doc_{i}')}_{j}"
                    metadata = doc.metadata.copy()
                    metadata["id"] = doc_id
                    metadata["chunk_index"] = j
                    metadata["source_doc_id"] = doc.metadata.get("id", f"doc_{i}")
                    
                    split_docs.append(Document(page_content=split, metadata=metadata))
            except Exception as e:
                print(f"[split_documents] 문서 {i+1} 분할 중 오류 발생: {str(e)}")
                
        print(f"[split_documents] 문서 분할 완료: {len(split_docs)}개 청크 생성됨")
            
    except Exception as e:
        print(f"[split_documents] 문서 분할 중 오류 발생: {str(e)}")
    
    return split_docs

def generate_queries_from_doc(
    document: Document, 
    num_queries: int = 3, 
    llm: Optional[BaseLanguageModel] = None
) -> List[Dict[str, Any]]:
    """
    문서로부터 평가용 쿼리를 생성합니다.
    
    Args:
        document (Document): 쿼리를 생성할 문서
        num_queries (int): 생성할 쿼리 수
        llm (Optional[BaseLanguageModel]): 사용할 언어 모델
        
    Returns:
        List[Dict[str, Any]]: 생성된 쿼리 리스트
    """
    print(f"[generate_queries_from_doc] 쿼리 생성 시작 (목표: {num_queries}개)")
    print(f"[generate_queries_from_doc] 문서 길이: {len(document.page_content)} 문자")
    
    if not llm:
        print(f"[generate_queries_from_doc] LLM이 없으므로 기본 ChatOpenAI 모델 초기화 중...")
        llm = ChatOpenAI(model="gpt-4", temperature=0.7)
    
    prompt_template = """
    다음 문서에서 {num_queries}개의 질문-답변 쌍을 생성해주세요.
    질문은 문서의 내용을 기반으로 하며, 명확하고 구체적이어야 합니다.
    답변은 정확하고 완전해야 하며, 문서에서 직접 추출해야 합니다.
    
    문서 내용:
    {document_content}
    
    다음 형식으로 JSON 배열을 반환해주세요:
    ```json
    [
      {{
        "question": "문서 내용에 기반한 질문",
        "answer": "문서에서 추출한 답변"
      }},
      ...
    ]
    ```
    
    질문은 다양한 형태(사실 확인, 설명 요청, 정보 요청 등)여야 하며, 간단한 키워드 일치로 찾을 수 없는 복잡한 질문도 포함해야 합니다.
    """
    
    # 프롬프트 생성
    print(f"[generate_queries_from_doc] PromptTemplate 생성 중...")
    prompt = PromptTemplate.from_template(prompt_template)
    
    # 쿼리 생성
    try:
        print(f"[generate_queries_from_doc] 쿼리 생성 체인 실행 중...")
        chain = prompt | llm | StrOutputParser()
        result = chain.invoke({
            "document_content": document.page_content,
            "num_queries": num_queries
        })
        
        # JSON 추출
        print(f"[generate_queries_from_doc] 응답에서 JSON 추출 중...")
        json_start = result.find('[')
        json_end = result.rfind(']') + 1
        
        if json_start != -1 and json_end != -1:
            print(f"[generate_queries_from_doc] JSON 찾음: {json_start}~{json_end}")
            json_str = result[json_start:json_end]
            queries = json.loads(json_str)
            
            # 문서 ID 추가
            for query in queries:
                query["relevant_doc_ids"] = [document.metadata["id"]]
            
            print(f"[generate_queries_from_doc] 쿼리 생성 성공: {len(queries)}개")
            return queries
        else:
            print(f"[generate_queries_from_doc] JSON 형식을 찾을 수 없음. 응답: {result[:100]}...")
            return []
    except Exception as e:
        print(f"쿼리 생성 중 오류 발생: {str(e)}")
        return []

def generate_synthetic_dataset(
    docs_dir: Union[str, Path],
    output_path: Union[str, Path],
    dataset_name: str,
    num_samples: int = 100,
    num_docs_per_sample: int = 5,
    doc_chunk_size: int = 1000,
    doc_chunk_overlap: int = 100,
    llm: Optional[BaseLanguageModel] = None
) -> RAGEvaluationDataset:
    """
    합성 평가 데이터셋을 생성합니다.
    
    Args:
        docs_dir (Union[str, Path]): 문서 디렉토리 경로
        output_path (Union[str, Path]): 출력 파일 경로
        dataset_name (str): 데이터셋 이름
        num_samples (int): 생성할 샘플 수
        num_docs_per_sample (int): 샘플당 문서 수
        doc_chunk_size (int): 문서 청크 크기
        doc_chunk_overlap (int): 문서 청크 오버랩
        llm (Optional[BaseLanguageModel]): 사용할 언어 모델
        
    Returns:
        RAGEvaluationDataset: 생성된 데이터셋
    """
    print(f"[generate_synthetic_dataset] 데이터셋 '{dataset_name}' 생성 시작")
    print(f"[generate_synthetic_dataset] 문서 로드 중: {docs_dir}")
    
    # 문서 로드 및 분할
    raw_documents = load_documents_from_directory(docs_dir, glob_pattern="**/*.pdf")
    print(f"[generate_synthetic_dataset] 로드된 문서 수: {len(raw_documents)}")
    
    split_documents_list = split_documents(
        raw_documents, 
        chunk_size=doc_chunk_size, 
        chunk_overlap=doc_chunk_overlap
    )
    
    print(f"[generate_synthetic_dataset] 분할된 문서 청크 수: {len(split_documents_list)}")
    
    # 문서 수가 충분한지 확인
    if len(split_documents_list) < num_docs_per_sample:
        print(f"경고: 문서 수가 부족합니다. 요청한 {num_docs_per_sample}개 대신 {len(split_documents_list)}개를 사용합니다.")
        num_docs_per_sample = len(split_documents_list)
    
    # 데이터셋 생성
    dataset = RAGEvaluationDataset(
        name=dataset_name,
        queries=[],
        documents=[],
        metadata={
            "source_dir": str(docs_dir),
            "num_samples": num_samples,
            "num_docs_per_sample": num_docs_per_sample,
            "doc_chunk_size": doc_chunk_size,
            "doc_chunk_overlap": doc_chunk_overlap,
            "total_documents": len(split_documents_list)
        }
    )
    
    # 문서 추가
    print(f"[generate_synthetic_dataset] 문서를 데이터셋에 추가 중...")
    for i, doc in enumerate(split_documents_list):
        dataset.documents.append({
            "id": doc.metadata["id"],
            "content": doc.page_content,
            "metadata": doc.metadata
        })
    
    # LLM 초기화
    if llm is None:
        print(f"[generate_synthetic_dataset] LLM이 없으므로 기본 ChatOpenAI 모델 초기화 중...")
        llm = ChatOpenAI(model="gpt-4", temperature=0.7)
    
    # 쿼리 생성
    print(f"[generate_synthetic_dataset] 쿼리 생성 시작 (목표: {num_samples}개)")
    query_count = 0
    
    # 최대 시도 횟수 설정 (각 문서당 최대 시도 수)
    max_attempts_per_doc = 3
    
    for doc_idx, doc in enumerate(split_documents_list):
        if query_count >= num_samples:
            break
            
        print(f"[generate_synthetic_dataset] 문서 {doc_idx+1}/{len(split_documents_list)}에서 쿼리 생성 중...")
        
        # 각 문서에서 최대 num_queries 개의 쿼리 생성 시도
        num_queries = min(3, num_samples - query_count)
        
        for attempt in range(max_attempts_per_doc):
            try:
                queries = generate_queries_from_doc(doc, num_queries=num_queries, llm=llm)
                
                if queries:
                    # 쿼리 추가
                    dataset.queries.extend(queries)
                    query_count += len(queries)
                    print(f"[generate_synthetic_dataset] 문서 {doc_idx+1}에서 {len(queries)}개 쿼리 생성 성공 (총 {query_count}/{num_samples})")
                    break
                else:
                    print(f"[generate_synthetic_dataset] 문서 {doc_idx+1}에서 쿼리 생성 실패 (시도 {attempt+1}/{max_attempts_per_doc})")
            except Exception as e:
                print(f"쿼리 생성 중 오류 발생: {str(e)}")
                
                if attempt == max_attempts_per_doc - 1:
                    print(f"[generate_synthetic_dataset] 문서 {doc_idx+1}에서 최대 시도 횟수 초과, 다음 문서로 넘어갑니다.")
    
    print(f"[generate_synthetic_dataset] 데이터셋 생성 완료: {dataset_name} ({len(dataset.queries)}개 쿼리, {len(dataset.documents)}개 문서)")
    
    # 데이터셋 저장
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(dataset.model_dump_json(indent=2))
    
    return dataset

def generate_complex_dataset(
    docs_dir: str,
    output_path: str,
    dataset_name: str,
    num_samples: int = 100,
    complexity_types: List[str] = None,
    doc_chunk_size: int = 1000,
    doc_chunk_overlap: int = 100,
    llm: Optional[BaseLanguageModel] = None
) -> RAGEvaluationDataset:
    """
    복잡한 평가 데이터셋을 생성합니다.
    
    Args:
        docs_dir (str): 문서 디렉토리 경로
        output_path (str): 출력 파일 경로
        dataset_name (str): 데이터셋 이름
        num_samples (int): 생성할 샘플 수
        complexity_types (List[str]): 복잡성 유형 목록
        doc_chunk_size (int): 문서 청크 크기
        doc_chunk_overlap (int): 문서 청크 오버랩
        llm (Optional[BaseLanguageModel]): 사용할 언어 모델
        
    Returns:
        RAGEvaluationDataset: 생성된 데이터셋
    """
    print(f"[generate_complex_dataset] 복잡한 데이터셋 '{dataset_name}' 생성 시작")
    print(f"[generate_complex_dataset] 문서 디렉토리: {docs_dir}")
    
    if complexity_types is None:
        complexity_types = ["multi_hop", "reasoning", "numerical", "comparison"]
    
    print(f"[generate_complex_dataset] 복잡성 유형: {complexity_types}")
    
    # 문서 로드 및 분할
    print(f"[generate_complex_dataset] 문서 로드 중...")
    raw_documents = load_documents_from_directory(docs_dir, glob_pattern="**/*.pdf")
    print(f"[generate_complex_dataset] 로드된 문서 수: {len(raw_documents)}")
    
    if len(raw_documents) == 0:
        print(f"[generate_complex_dataset] 경고: 문서가 로드되지 않았습니다! 디렉토리 확인 필요: {docs_dir}")
        return None
        
    print(f"[generate_complex_dataset] 문서 분할 중...")
    split_documents_list = split_documents(
        raw_documents, 
        chunk_size=doc_chunk_size, 
        chunk_overlap=doc_chunk_overlap
    )
    print(f"[generate_complex_dataset] 분할된 문서 청크 수: {len(split_documents_list)}")
    
    # LLM 초기화
    if not llm:
        print(f"[generate_complex_dataset] LLM이 없으므로 기본 ChatOpenAI 모델 초기화 중...")
        llm = ChatOpenAI(model="gpt-4", temperature=0.7)
    
    # 데이터셋 초기화
    print(f"[generate_complex_dataset] 데이터셋 초기화 중...")
    dataset = RAGEvaluationDataset(name=dataset_name)
    
    # 문서 추가
    print(f"[generate_complex_dataset] 문서를 데이터셋에 추가 중...")
    for doc in split_documents_list:
        dataset.add_document(doc)
    
    # 쿼리 생성
    print(f"[generate_complex_dataset] 복잡한 쿼리 생성 시작 (총 {num_samples}개 목표)...")
    queries_per_type = num_samples // len(complexity_types)
    remaining_queries = num_samples % len(complexity_types)
    
    generated_queries = 0
    
    # 복잡성 유형별 쿼리 생성
    for complexity_type in complexity_types:
        type_query_count = queries_per_type + (1 if remaining_queries > 0 else 0)
        if remaining_queries > 0:
            remaining_queries -= 1
        
        print(f"[generate_complex_dataset] '{complexity_type}' 유형 쿼리 {type_query_count}개 생성 중...")
        
        # 복잡성 유형별 쿼리 생성 로직
        type_prompt_template = COMPLEXITY_TEMPLATES.get(complexity_type, COMPLEXITY_TEMPLATES["default"])
        
        # 각 쿼리 생성
        for i in range(type_query_count):
            try:
                # 무작위 문서 선택 (2개)
                if len(split_documents_list) < 2:
                    print(f"[generate_complex_dataset] 경고: 문서가 부족합니다. 최소 2개 필요 (현재: {len(split_documents_list)}개)")
                    selected_docs = split_documents_list[:min(2, len(split_documents_list))]
                else:
                    selected_docs = random.sample(split_documents_list, min(2, len(split_documents_list)))
                
                # 문서 내용 결합
                combined_content = "\n\n".join([doc.page_content for doc in selected_docs])
                
                print(f"[generate_complex_dataset] '{complexity_type}' 쿼리 {i+1}/{type_query_count} 생성 중...")
                
                # 프롬프트 생성
                prompt = PromptTemplate.from_template(type_prompt_template)
                
                # 쿼리 생성
                chain = prompt | llm | StrOutputParser()
                result = chain.invoke({
                    "document_content": combined_content,
                    "complexity_type": complexity_type
                })
                
                # JSON 추출
                json_start = result.find('{')
                json_end = result.rfind('}') + 1
                
                if json_start != -1 and json_end != -1:
                    json_str = result[json_start:json_end]
                    query_data = json.loads(json_str)
                    
                    # 메타데이터 추가
                    query_data["complexity_type"] = complexity_type
                    query_data["relevant_doc_ids"] = [doc.metadata["id"] for doc in selected_docs]
                    
                    # 데이터셋에 쿼리 추가
                    dataset.add_query(query_data)
                    generated_queries += 1
                    print(f"[generate_complex_dataset] 쿼리 추가 성공: '{query_data.get('question', '')[:50]}...'")
                else:
                    print(f"[generate_complex_dataset] JSON 형식을 찾을 수 없음. 응답: {result[:100]}...")
            except Exception as e:
                print(f"[generate_complex_dataset] 쿼리 생성 중 오류 발생: {str(e)}")
    
    print(f"[generate_complex_dataset] 데이터셋 생성 완료: {generated_queries}개 쿼리, {len(dataset.documents)}개 문서")
    
    # 데이터셋 저장
    print(f"[generate_complex_dataset] 데이터셋 저장 중: {output_path}")
    dataset.save(output_path)
    
    return dataset

def generate_predefined_datasets(
    llm: Optional[BaseLanguageModel] = None
) -> List[RAGEvaluationDataset]:
    """
    설정에 정의된 데이터셋을 생성합니다.
    
    Args:
        llm (Optional[BaseLanguageModel]): 사용할 언어 모델
        
    Returns:
        List[RAGEvaluationDataset]: 생성된 데이터셋 리스트
    """
    if not llm:
        llm = ChatOpenAI(model="gpt-4", temperature=0.7)
    
    datasets = []
    
    # 데이터셋 디렉토리 생성
    Path(DATASETS_DIR).mkdir(exist_ok=True, parents=True)
    
    # 설정된 데이터셋 생성
    for dataset_type, dataset_config in DATASET_CONFIG.items():
        dataset_name = dataset_config["name"]
        dataset_type = dataset_config.get("type", "synthetic")
        
        output_path = Path(DATASETS_DIR) / f"{dataset_name}.json"
        
        if dataset_type == "synthetic":
            dataset = generate_synthetic_dataset(
                docs_dir=DOCS_DIR,
                output_path=output_path,
                dataset_name=dataset_name,
                num_samples=dataset_config.get("num_samples", 50),
                num_docs_per_sample=dataset_config.get("num_docs_per_sample", 3),
                doc_chunk_size=dataset_config.get("doc_chunk_size", 1000),
                doc_chunk_overlap=dataset_config.get("doc_chunk_overlap", 100),
                llm=llm
            )
        elif dataset_type == "complex":
            dataset = generate_complex_dataset(
                docs_dir=DOCS_DIR,
                output_path=output_path,
                dataset_name=dataset_name,
                num_samples=dataset_config.get("num_samples", 30),
                complexity_types=dataset_config.get("complexity_types", None),
                doc_chunk_size=dataset_config.get("doc_chunk_size", 1000),
                doc_chunk_overlap=dataset_config.get("doc_chunk_overlap", 100),
                llm=llm
            )
        else:
            print(f"알 수 없는 데이터셋 유형: {dataset_type}")
            continue
        
        datasets.append(dataset)
        print(f"데이터셋 생성 완료: {dataset_name} ({len(dataset.queries)}개 쿼리, {len(dataset.documents)}개 문서)")
    
    return datasets

def load_dataset(dataset_path: Union[str, Path]) -> RAGEvaluationDataset:
    """
    데이터셋을 로드합니다.
    
    Args:
        dataset_path (Union[str, Path]): 데이터셋 파일 경로
        
    Returns:
        RAGEvaluationDataset: 로드된 데이터셋
    """
    dataset_path = Path(dataset_path)
    
    if not dataset_path.exists():
        raise FileNotFoundError(f"데이터셋 파일을 찾을 수 없습니다: {dataset_path}")
    
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset_json = json.load(f)

    return RAGEvaluationDataset.model_validate(dataset_json) 