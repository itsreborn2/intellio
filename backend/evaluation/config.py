import os
from pathlib import Path
from typing import Dict, List, Optional

# 기본 경로 설정
BASE_DIR = Path(__file__).parent
DOCS_DIR = BASE_DIR / "docs"
DATASETS_DIR = BASE_DIR / "datasets"
RESULTS_DIR = BASE_DIR / "results"

# 결과 디렉토리가 없으면 생성
RESULTS_DIR.mkdir(exist_ok=True)

# 임베딩 모델 설정
EMBEDDING_MODELS = {
    "text-embedding-3-small": "openai",
    "text-embedding-3-large": "openai",
    "text-embedding-ada-002": "openai",
    "text-multilingual-embedding-002": "google",
    "text-embedding-005": "google",
    "dragonkue/bge-m3-ko": "huggingface"
}

# LangSmith 설정
LANGSMITH_API_KEY = os.environ.get("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT_PREFIX = "rag_evaluation"

# 평가 데이터셋 설정
DATASET_CONFIG = {
    "standard": {
        "name": "standard_evaluation",
        "size": 20,
        "num_samples":10,
        "doc_chunk_size":1500,
        "doc_chunk_overlap":200,
        "description": "표준 RAG 평가 데이터셋"
    },
    "robustness": {
        "name": "robustness_evaluation",
        "size": 10,
        "num_samples":10,
        "doc_chunk_size":1500,
        "doc_chunk_overlap":200,
        "description": "시스템 견고성 평가 데이터셋"
    },
    "domain": {
        "name": "domain_evaluation",
        "size": 10,
        "num_samples":10,
        "doc_chunk_size":1500,
        "doc_chunk_overlap":200,
        "description": "도메인 특화 평가 데이터셋"
    }
}

# 메트릭 설정
METRICS_CONFIG = {
    "embedding": ["similarity", "average_difference", "mrr", "optimal_threshold", "f1_score"],
    "retrieval": ["precision", "recall", "ndcg", "diversity"],
    "generation": ["faithfulness", "answer_relevancy", "context_precision"]
}

# 임계값 범위 설정
THRESHOLD_RANGE = {
    "start": 0.0,
    "end": 1.0,
    "step": 0.01
} 