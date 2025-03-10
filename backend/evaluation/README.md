# RAG 평가 시스템 (RAG Evaluation System)

임베딩 성능, 검색 품질, 생성 품질 및 전체 RAG 시스템의 견고성을 종합적으로 평가하는 시스템입니다.

## 주요 기능

- **임베딩 평가**: 다양한 임베딩 모델의 성능 평가
- **검색 품질 평가**: 기본 메트릭(Precision@K, Recall@K, NDCG, MRR 등) 및 고급 메트릭 지원
- **생성 품질 평가**: 사실 일관성, 응답 품질, 관련성 등 평가
- **견고성 평가**: 다양한 쿼리 변형에 대한 시스템 견고성 측정
- **LangSmith 통합**: LangSmith를 통한 더 세밀한 평가 및 추적 지원

## 디렉토리 구조

```
evaluation/
├── config.py                  # 설정 파일
├── main.py                    # 메인 평가 모듈
├── test_evaluation.py         # 테스트 스크립트
├── datasets/                  # 생성된 데이터셋 저장 디렉토리
├── docs/                      # 평가에 사용되는 문서
├── generator/                 # 데이터셋 및 쿼리 변형 생성기
│   ├── dataset_generator.py   # 데이터셋 생성 도구
│   └── query_variations.py    # 쿼리 변형 생성 도구
├── langsmith/                 # LangSmith 통합 모듈
│   └── langsmith_evaluator.py # LangSmith 평가기
├── metrics/                   # 평가 메트릭 모듈
│   ├── embedding_metrics.py   # 임베딩 메트릭
│   ├── retrieval_metrics.py   # 검색 메트릭
│   └── generation_metrics.py  # 생성 메트릭
└── results/                   # 평가 결과 저장 디렉토리
```

## 설치 요구사항

다음 패키지가 필요합니다:

- langchain
- langchain-openai
- langchain-community
- langchain-core
- langsmith
- numpy
- faiss-cpu (또는 faiss-gpu)
- openai
- tiktoken
- pydantic

## 설정 방법

1. `config.py` 파일에서 다음 설정을 확인하세요:
   - `DOCS_DIR`: 평가에 사용할 문서 디렉토리 경로
   - `DATASETS_DIR`: 데이터셋 저장 디렉토리 경로
   - `RESULTS_DIR`: 결과 저장 디렉토리 경로
   - `EMBEDDING_MODELS`: 평가할 임베딩 모델 설정
   - `DATASET_CONFIGS`: 생성할 데이터셋 설정
   - `LANGSMITH_API_KEY`: LangSmith API 키 (선택사항)
   - `LANGSMITH_PROJECT_PREFIX`: LangSmith 프로젝트 접두사

2. LangSmith 사용을 위해 환경 변수를 설정하세요 (선택사항):
   ```
   export LANGCHAIN_API_KEY=your_langsmith_api_key
   ```

## 사용 방법

### 1. 데이터셋 생성

```python
from main import RAGEvaluator

# 평가기 초기화
evaluator = RAGEvaluator()

# 데이터셋 생성
dataset_paths = evaluator.generate_datasets()
```

또는 명령줄에서:

```bash
python main.py --generate-datasets
```

### 2. 임베딩 모델 평가

```python
# 임베딩 모델 평가
results = evaluator.evaluate_embeddings(models=["openai-text-embedding-3-small", "huggingface-all-MiniLM-L6-v2"])
```

또는 명령줄에서:

```bash
python main.py --evaluate-embeddings
```

### 3. 검색기 평가

```python
# 검색기 평가 (자체 구현 검색기 필요)
from your_module import your_retriever

retrieval_results = evaluator.evaluate_retriever(
    retriever_name="your_retriever",
    retriever_fn=your_retriever,
    dataset_path="path/to/dataset.json",
    advanced=True
)
```

### 4. 생성 모델 평가

```python
# 생성 모델 평가
def your_generator(query, docs):
    # 생성 로직 구현
    return generated_response

generation_results = evaluator.evaluate_generator(
    generator_name="your_generator",
    generator_fn=your_generator,
    dataset_path="path/to/dataset.json"
)

# 엔드투엔드 평가
e2e_results = evaluator.evaluate_generator(
    generator_name="your_e2e_system",
    generator_fn=your_generator,
    dataset_path="path/to/dataset.json",
    retriever_fn=your_retriever
)
```

### 5. 견고성 평가

```python
# 견고성 평가
robustness_results = evaluator.evaluate_retriever_robustness(
    retriever_name="your_retriever",
    retriever_fn=your_retriever,
    dataset_path="path/to/dataset.json",
    variation_types=["typo", "incomplete", "semantic"]
)
```

### 6. 전체 시스템 평가

```python
# RAG 시스템 설정
rag_system_config = {
    "name": "your_rag_system",
    "embedding_models": ["openai-text-embedding-3-small"],
    "retriever": {
        "name": "your_retriever",
        "instance": your_retriever
    },
    "generator": {
        "name": "your_generator",
        "instance": your_llm,
        "system_prompt": "Your system prompt here"
    },
    "datasets": ["basic_dataset", "complex_dataset"]
}

# 전체 평가 실행
results = evaluator.run_full_evaluation(rag_system_config)
```

### 7. LangSmith 평가

```python
# LangSmith 활성화
evaluator = RAGEvaluator(use_langsmith=True)

# LangSmith 데이터셋 준비
dataset_id = evaluator.prepare_langsmith_dataset("path/to/dataset.json")

# LangSmith로 검색 평가
langsmith_results = evaluator.langsmith_evaluator.evaluate_retrieval(
    dataset_id=dataset_id,
    retriever_name="your_retriever",
    retriever_fn=lambda query: [doc.page_content for doc in your_retriever.get_relevant_documents(query)]
)
```

## 테스트 실행

간단한 테스트를 실행하려면:

```bash
python test_evaluation.py
```

이 스크립트는 테스트 검색기와 생성기를 생성하고 데이터셋을 생성한 후 기본 평가를 실행합니다.

## 평가 결과

모든 평가 결과는 `RESULTS_DIR`에 JSON 파일로 저장됩니다. 각 파일은 다음 정보를 포함합니다:

- 평가 타임스탬프
- 평가된 모델 이름
- 평가 메트릭 및 점수
- 세부 결과

LangSmith를 사용하는 경우 LangSmith 대시보드에서 더 자세한 평가 결과를 볼 수 있습니다. 