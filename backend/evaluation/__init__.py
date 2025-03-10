"""
RAG 평가 시스템 (RAG Evaluation System)

임베딩 성능, 검색 품질, 생성 품질 및 전체 RAG 시스템의 견고성을 종합적으로 평가하는 시스템입니다.
"""

__version__ = "0.1.0"

# 주요 클래스와 함수를 패키지 레벨로 노출
from evaluation.main import RAGEvaluator
from evaluation.langsmith_eval.langsmith_evaluator import LangSmithEvaluator, RAGEvaluationExample
from evaluation.generator.dataset_generator import load_documents_from_directory, split_documents 