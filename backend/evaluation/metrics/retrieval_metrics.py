"""
검색(Retrieval) 성능 평가를 위한 메트릭 모듈
"""
import json
import time
import numpy as np
from typing import Dict, List, Any, Set, Optional
from pathlib import Path
from datetime import datetime
from collections import Counter

def calculate_precision_at_k(relevant_docs: Set[str], retrieved_docs: List[str], k: int) -> float:
    """
    상위 k개 검색 결과의 정밀도(Precision@k)를 계산합니다.
    
    Args:
        relevant_docs (Set[str]): 관련 문서 ID 집합
        retrieved_docs (List[str]): 검색된 문서 ID 리스트 (순위 순)
        k (int): 상위 k개 결과 고려
        
    Returns:
        float: Precision@k 값 (0~1)
    """
    if not retrieved_docs or k <= 0:
        return 0.0
        
    k = min(k, len(retrieved_docs))
    top_k_docs = retrieved_docs[:k]
    
    relevant_in_top_k = sum(1 for doc_id in top_k_docs if doc_id in relevant_docs)
    precision_at_k = relevant_in_top_k / k
    
    return precision_at_k

def calculate_recall_at_k(relevant_docs: Set[str], retrieved_docs: List[str], k: int) -> float:
    """
    상위 k개 검색 결과의 재현율(Recall@k)을 계산합니다.
    
    Args:
        relevant_docs (Set[str]): 관련 문서 ID 집합
        retrieved_docs (List[str]): 검색된 문서 ID 리스트 (순위 순)
        k (int): 상위 k개 결과 고려
        
    Returns:
        float: Recall@k 값 (0~1)
    """
    if not retrieved_docs or not relevant_docs or k <= 0:
        return 0.0
        
    k = min(k, len(retrieved_docs))
    top_k_docs = retrieved_docs[:k]
    
    relevant_in_top_k = sum(1 for doc_id in top_k_docs if doc_id in relevant_docs)
    recall_at_k = relevant_in_top_k / len(relevant_docs)
    
    return recall_at_k

def calculate_ndcg_at_k(relevant_docs: Dict[str, float], retrieved_docs: List[str], k: int) -> float:
    """
    상위 k개 검색 결과의 NDCG(Normalized Discounted Cumulative Gain)를 계산합니다.
    
    Args:
        relevant_docs (Dict[str, float]): 관련 문서 ID와 관련성 점수 딕셔너리
        retrieved_docs (List[str]): 검색된 문서 ID 리스트 (순위 순)
        k (int): 상위 k개 결과 고려
        
    Returns:
        float: NDCG@k 값 (0~1)
    """
    if not retrieved_docs or not relevant_docs or k <= 0:
        return 0.0
        
    k = min(k, len(retrieved_docs))
    
    # DCG 계산
    dcg = 0
    for i, doc_id in enumerate(retrieved_docs[:k], 1):
        rel = relevant_docs.get(doc_id, 0)
        dcg += rel / np.log2(i + 1)
    
    # 이상적인 순서로 정렬된 문서 리스트 생성
    ideal_order = sorted(relevant_docs.keys(), key=lambda x: relevant_docs[x], reverse=True)[:k]
    
    # IDCG 계산
    idcg = 0
    for i, doc_id in enumerate(ideal_order, 1):
        rel = relevant_docs[doc_id]
        idcg += rel / np.log2(i + 1)
    
    # NDCG 계산
    ndcg = dcg / idcg if idcg > 0 else 0
    
    return ndcg

def calculate_mrr(relevant_docs: Set[str], retrieved_docs: List[str]) -> float:
    """
    검색 결과의 MRR(Mean Reciprocal Rank)을 계산합니다.
    
    Args:
        relevant_docs (Set[str]): 관련 문서 ID 집합
        retrieved_docs (List[str]): 검색된 문서 ID 리스트 (순위 순)
        
    Returns:
        float: MRR 값 (0~1)
    """
    if not retrieved_docs or not relevant_docs:
        return 0.0
        
    # 첫 번째 관련 문서의 순위 찾기
    for i, doc_id in enumerate(retrieved_docs, 1):
        if doc_id in relevant_docs:
            return 1.0 / i
    
    return 0.0

def calculate_diversity(retrieved_docs: List[Dict[str, Any]], method: str = "content") -> float:
    """
    검색 결과의 다양성을 계산합니다.
    
    Args:
        retrieved_docs (List[Dict[str, Any]]): 검색된 문서 리스트
        method (str): 다양성 계산 방법 ('content', 'source', 'metadata')
        
    Returns:
        float: 다양성 점수 (0~1)
    """
    if not retrieved_docs:
        return 0.0
    
    if method == "content":
        # 내용 기반 다양성 계산 (예: 텍스트 유사도 기반)
        # 실제 구현에서는 문서 내용 간 유사도를 계산하여 평균 차이 등을 측정
        # 이 예제에서는 간단하게 대체
        return 0.7
    
    elif method == "source":
        # 출처 기반 다양성 계산
        sources = [doc.get("source", "") for doc in retrieved_docs]
        unique_sources = set(sources)
        return len(unique_sources) / len(retrieved_docs)
    
    elif method == "metadata":
        # 메타데이터 기반 다양성 계산
        categories = [doc.get("category", "") for doc in retrieved_docs]
        category_count = Counter(categories)
        entropy = -sum((count/len(retrieved_docs)) * np.log2(count/len(retrieved_docs)) 
                      for count in category_count.values())
        max_entropy = np.log2(len(category_count)) if category_count else 0
        return entropy / max_entropy if max_entropy > 0 else 0
    
    return 0.0

def measure_retrieval_time(retriever: Any, queries: List[str], n_samples: int = 5) -> Dict[str, float]:
    """
    검색 속도를 측정합니다.
    
    Args:
        retriever (Any): 평가할 검색기
        queries (List[str]): 테스트 쿼리 리스트
        n_samples (int): 측정 샘플 수
        
    Returns:
        Dict[str, float]: 검색 시간 측정 결과 (평균, 최소, 최대)
    """
    times = []
    
    for query in queries[:n_samples]:
        start_time = time.time()
        retriever.get_relevant_documents(query)
        end_time = time.time()
        
        query_time = (end_time - start_time) * 1000  # milliseconds
        times.append(query_time)
    
    return {
        "avg_time_ms": sum(times) / len(times),
        "min_time_ms": min(times),
        "max_time_ms": max(times)
    }

def evaluate_retrieval_simple(
    retriever: Any,
    queries: List[str],
    relevant_docs: Dict[str, List[str]],
    k_values: List[int] = [1, 3, 5, 10]
) -> Dict[str, Any]:
    """
    검색기의 기본 성능을 평가합니다.
    
    Args:
        retriever (Any): 평가할 검색기
        queries (List[str]): 테스트 쿼리 리스트
        relevant_docs (Dict[str, List[str]]): 쿼리별 관련 문서 ID 리스트
        k_values (List[int]): 평가할 k 값 리스트
        
    Returns:
        Dict[str, Any]: 평가 결과
    """
    results = {
        "precision": {f"p@{k}": 0.0 for k in k_values},
        "recall": {f"r@{k}": 0.0 for k in k_values},
        "ndcg": {f"ndcg@{k}": 0.0 for k in k_values},
        "mrr": 0.0,
        "retrieval_time": {}
    }
    
    all_precision = {k: [] for k in k_values}
    all_recall = {k: [] for k in k_values}
    all_ndcg = {k: [] for k in k_values}
    all_mrr = []
    
    # 쿼리별 평가
    for query in queries:
        # 검색 실행
        retrieved_documents = retriever.get_relevant_documents(query)
        retrieved_ids = [doc.metadata.get("id", "") for doc in retrieved_documents]
        
        # 관련 문서 ID
        relevant_doc_ids = set(relevant_docs.get(query, []))
        
        # 관련 문서 점수 (단순화: 모든 관련 문서는 1점)
        relevant_doc_scores = {doc_id: 1.0 for doc_id in relevant_doc_ids}
        
        # 각 k에 대한 평가
        for k in k_values:
            precision_k = calculate_precision_at_k(relevant_doc_ids, retrieved_ids, k)
            recall_k = calculate_recall_at_k(relevant_doc_ids, retrieved_ids, k)
            ndcg_k = calculate_ndcg_at_k(relevant_doc_scores, retrieved_ids, k)
            
            all_precision[k].append(precision_k)
            all_recall[k].append(recall_k)
            all_ndcg[k].append(ndcg_k)
        
        # MRR 계산
        mrr = calculate_mrr(relevant_doc_ids, retrieved_ids)
        all_mrr.append(mrr)
    
    # 평균 계산
    for k in k_values:
        results["precision"][f"p@{k}"] = sum(all_precision[k]) / len(all_precision[k])
        results["recall"][f"r@{k}"] = sum(all_recall[k]) / len(all_recall[k])
        results["ndcg"][f"ndcg@{k}"] = sum(all_ndcg[k]) / len(all_ndcg[k])
    
    results["mrr"] = sum(all_mrr) / len(all_mrr)
    
    # 검색 시간 측정
    results["retrieval_time"] = measure_retrieval_time(retriever, queries)
    
    return results

def evaluate_retrieval_advanced(
    retriever: Any,
    queries: List[str],
    relevant_docs: Dict[str, List[str]],
    k_values: List[int] = [1, 3, 5, 10],
    diversity_methods: List[str] = ["content", "source"]
) -> Dict[str, Any]:
    """
    검색기의 고급 성능을 평가합니다.
    
    Args:
        retriever (Any): 평가할 검색기
        queries (List[str]): 테스트 쿼리 리스트
        relevant_docs (Dict[str, List[str]]): 쿼리별 관련 문서 ID 리스트
        k_values (List[int]): 평가할 k 값 리스트
        diversity_methods (List[str]): 다양성 계산 방법 리스트
        
    Returns:
        Dict[str, Any]: 평가 결과
    """
    # 기본 평가 수행
    basic_results = evaluate_retrieval_simple(retriever, queries, relevant_docs, k_values)
    
    # 고급 평가 추가
    advanced_results = {
        "diversity": {method: 0.0 for method in diversity_methods},
        "query_complexity": {
            "simple": {},
            "complex": {}
        }
    }
    
    # 다양성 평가
    for method in diversity_methods:
        diversity_scores = []
        for query in queries:
            retrieved_documents = retriever.get_relevant_documents(query)
            diversity = calculate_diversity(retrieved_documents, method)
            diversity_scores.append(diversity)
        
        advanced_results["diversity"][method] = sum(diversity_scores) / len(diversity_scores)
    
    # 쿼리 복잡도별 성능 평가
    # (실제 구현에서는 쿼리 복잡도를 자동으로 판별하는 로직 필요)
    simple_queries = queries[:len(queries)//2]  # 임시로 첫 절반을 단순 쿼리로 가정
    complex_queries = queries[len(queries)//2:]  # 임시로 나머지 절반을 복잡한 쿼리로 가정
    
    simple_relevant_docs = {q: relevant_docs[q] for q in simple_queries if q in relevant_docs}
    complex_relevant_docs = {q: relevant_docs[q] for q in complex_queries if q in relevant_docs}
    
    if simple_queries and simple_relevant_docs:
        advanced_results["query_complexity"]["simple"] = evaluate_retrieval_simple(
            retriever, simple_queries, simple_relevant_docs, k_values
        )
    
    if complex_queries and complex_relevant_docs:
        advanced_results["query_complexity"]["complex"] = evaluate_retrieval_simple(
            retriever, complex_queries, complex_relevant_docs, k_values
        )
    
    # 결과 통합
    results = {**basic_results, **advanced_results}
    
    return results

def evaluate_retrieval_robustness(
    retriever: Any,
    original_queries: List[str],
    modified_queries: Dict[str, List[str]],
    relevant_docs: Dict[str, List[str]],
    k: int = 5
) -> Dict[str, Any]:
    """
    검색기의 견고성을 평가합니다.
    
    Args:
        retriever (Any): 평가할 검색기
        original_queries (List[str]): 원본 쿼리 리스트
        modified_queries (Dict[str, List[str]]): 쿼리 유형별 수정된 쿼리 목록
        relevant_docs (Dict[str, List[str]]): 쿼리별 관련 문서 ID 리스트
        k (int): 평가할 k 값
        
    Returns:
        Dict[str, Any]: 평가 결과
    """
    results = {
        "original": {},
        "typos": {},
        "incomplete": {},
        "ambiguous": {}
    }
    
    # 원본 쿼리에 대한 평가
    original_precision = []
    original_recall = []
    original_mrr = []
    
    for query in original_queries:
        # 검색 실행
        retrieved_documents = retriever.get_relevant_documents(query)
        retrieved_ids = [doc.metadata.get("id", "") for doc in retrieved_documents]
        
        # 관련 문서 ID
        relevant_doc_ids = set(relevant_docs.get(query, []))
        
        # 평가
        precision = calculate_precision_at_k(relevant_doc_ids, retrieved_ids, k)
        recall = calculate_recall_at_k(relevant_doc_ids, retrieved_ids, k)
        mrr = calculate_mrr(relevant_doc_ids, retrieved_ids)
        
        original_precision.append(precision)
        original_recall.append(recall)
        original_mrr.append(mrr)
    
    results["original"] = {
        f"precision@{k}": sum(original_precision) / len(original_precision) if original_precision else 0,
        f"recall@{k}": sum(original_recall) / len(original_recall) if original_recall else 0,
        "mrr": sum(original_mrr) / len(original_mrr) if original_mrr else 0
    }
    
    # 수정된 쿼리 유형별 평가
    for query_type, queries in modified_queries.items():
        type_precision = []
        type_recall = []
        type_mrr = []
        
        for query in queries:
            # 검색 실행
            retrieved_documents = retriever.get_relevant_documents(query)
            retrieved_ids = [doc.metadata.get("id", "") for doc in retrieved_documents]
            
            # 원본 쿼리를 찾아 관련 문서 ID 가져오기
            original_query = next((q for q in original_queries if query.startswith(q[:5])), None)
            if original_query:
                relevant_doc_ids = set(relevant_docs.get(original_query, []))
                
                # 평가
                precision = calculate_precision_at_k(relevant_doc_ids, retrieved_ids, k)
                recall = calculate_recall_at_k(relevant_doc_ids, retrieved_ids, k)
                mrr = calculate_mrr(relevant_doc_ids, retrieved_ids)
                
                type_precision.append(precision)
                type_recall.append(recall)
                type_mrr.append(mrr)
        
        if type_precision:
            results[query_type] = {
                f"precision@{k}": sum(type_precision) / len(type_precision),
                f"recall@{k}": sum(type_recall) / len(type_recall),
                "mrr": sum(type_mrr) / len(type_mrr),
                # 견고성 점수 (원본 대비 성능 유지 비율)
                "robustness_score": (sum(type_precision) / len(type_precision)) / 
                                    (sum(original_precision) / len(original_precision)) if original_precision else 0
            }
    
    return results

def save_retrieval_evaluation_results(results: Dict[str, Any], retriever_name: str, results_dir: Path) -> None:
    """
    검색 평가 결과를 저장합니다.
    
    Args:
        results (Dict[str, Any]): 평가 결과
        retriever_name (str): 평가한 검색기 이름
        results_dir (Path): 결과 저장 디렉토리
    """
    results_with_meta = {
        "retriever_name": retriever_name,
        "timestamp": datetime.now().isoformat(),
        "results": results
    }
    
    # 결과를 JSON 파일로 저장
    results_file = results_dir / f"{retriever_name}_retrieval_evaluation_report.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results_with_meta, f, ensure_ascii=False, indent=2)
    
    print(f"검색 평가 결과 저장됨: {results_file}") 