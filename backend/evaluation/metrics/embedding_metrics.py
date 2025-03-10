"""
임베딩 모델 평가를 위한 메트릭 모듈
"""
import json
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path
from datetime import datetime
from sklearn.metrics.pairwise import cosine_similarity

def get_embedding(text: str, model: Any) -> np.ndarray:
    """
    텍스트에 대한 임베딩 벡터를 반환합니다.
    
    Args:
        text (str): 임베딩할 텍스트
        model (Any): 임베딩 모델
        
    Returns:
        np.ndarray: 임베딩 벡터
    """
    # 모델 유형에 따라 임베딩 방식이 다를 수 있음
    if hasattr(model, "embed_query"):
        # LangChain 호환 모델
        return model.embed_query(text)
    elif hasattr(model, "encode"):
        # Sentence Transformers 호환 모델
        return model.encode(text)
    else:
        # 기타 모델의 경우 직접 호출 시도
        return model(text)

def calculate_similarity(text_embedding: np.ndarray, query_embedding: np.ndarray) -> float:
    """
    두 임베딩 벡터 간의 코사인 유사도를 계산합니다.
    
    Args:
        text_embedding (np.ndarray): 텍스트 임베딩 벡터
        query_embedding (np.ndarray): 쿼리 임베딩 벡터
        
    Returns:
        float: 코사인 유사도 (-1과 1 사이)
    """
    return float(cosine_similarity([text_embedding], [query_embedding])[0][0])

def find_optimal_threshold(
    text_embeddings: List[np.ndarray], 
    related_query_embeddings: List[np.ndarray], 
    unrelated_query_embeddings: List[np.ndarray],
    start: float = 0.0,
    end: float = 1.0,
    step: float = 0.01
) -> Tuple[float, float]:
    """
    관련 및 비관련 쿼리를 가장 잘 구분하는 최적의 임계값을 찾습니다.
    
    Args:
        text_embeddings (List[np.ndarray]): 텍스트 임베딩 벡터 목록
        related_query_embeddings (List[np.ndarray]): 관련 쿼리 임베딩 벡터 목록
        unrelated_query_embeddings (List[np.ndarray]): 비관련 쿼리 임베딩 벡터 목록
        start (float): 임계값 탐색 시작점
        end (float): 임계값 탐색 끝점
        step (float): 임계값 탐색 단계
        
    Returns:
        Tuple[float, float]: 최적 임계값과 해당 F1 점수
    """
    best_threshold = 0.0
    best_f1 = 0.0
    
    # 모든 관련 쿼리와 텍스트 간의 유사도 계산
    related_similarities = []
    for text_emb in text_embeddings:
        for query_emb in related_query_embeddings:
            similarity = calculate_similarity(text_emb, query_emb)
            related_similarities.append(similarity)
    
    # 모든 비관련 쿼리와 텍스트 간의 유사도 계산
    unrelated_similarities = []
    for text_emb in text_embeddings:
        for query_emb in unrelated_query_embeddings:
            similarity = calculate_similarity(text_emb, query_emb)
            unrelated_similarities.append(similarity)
    
    # 다양한 임계값에 대해 F1 점수 계산
    thresholds = np.arange(start, end + step, step)
    for threshold in thresholds:
        # 관련 쿼리 중 임계값보다 높은 유사도를 가진 것(실제 양성 중 예측된 양성)
        true_positives = sum(1 for s in related_similarities if s >= threshold)
        
        # 비관련 쿼리 중 임계값보다 낮은 유사도를 가진 것(실제 음성 중 예측된 음성)
        true_negatives = sum(1 for s in unrelated_similarities if s < threshold)
        
        # 비관련 쿼리 중 임계값보다 높은 유사도를 가진 것(실제 음성 중 예측된 양성)
        false_positives = len(unrelated_similarities) - true_negatives
        
        # 관련 쿼리 중 임계값보다 낮은 유사도를 가진 것(실제 양성 중 예측된 음성)
        false_negatives = len(related_similarities) - true_positives
        
        # 정밀도와 재현율 계산
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        
        # F1 점수 계산
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        # 가장 좋은 F1 점수와 임계값 저장
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = threshold
    
    return best_threshold, best_f1

def calculate_mrr(
    text_embeddings: List[np.ndarray],
    related_query_embeddings: List[np.ndarray],
    all_query_embeddings: List[np.ndarray]
) -> float:
    """
    평균 역수 순위(Mean Reciprocal Rank)를 계산합니다.
    
    Args:
        text_embeddings (List[np.ndarray]): 텍스트 임베딩 벡터 목록
        related_query_embeddings (List[np.ndarray]): 관련 쿼리 임베딩 벡터 목록
        all_query_embeddings (List[np.ndarray]): 모든 쿼리 임베딩 벡터 목록
        
    Returns:
        float: MRR 점수
    """
    reciprocal_ranks = []
    
    for i, text_emb in enumerate(text_embeddings):
        # 해당 텍스트와 관련된 쿼리 임베딩
        related_queries_for_text = related_query_embeddings[i] if i < len(related_query_embeddings) else []
        
        # 모든 쿼리와의 유사도 계산 및 순위 매기기
        similarities = [(j, calculate_similarity(text_emb, query_emb)) 
                        for j, query_emb in enumerate(all_query_embeddings)]
        
        # 유사도 기준 내림차순 정렬
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # 관련 쿼리의 순위 찾기
        for related_query_idx in related_queries_for_text:
            for rank, (query_idx, _) in enumerate(similarities, 1):
                if query_idx == related_query_idx:
                    reciprocal_ranks.append(1.0 / rank)
                    break
    
    # MRR 계산
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0
    return mrr

def evaluate_embedding_model(
    texts: List[str], 
    related_queries: List[str], 
    unrelated_queries: List[str],
    model: Any,
    model_name: str,
    results_dir: Path
) -> Dict[str, Any]:
    """
    임베딩 모델을 평가하고 결과를 저장합니다.
    
    Args:
        texts (List[str]): 평가용 텍스트 목록
        related_queries (List[str]): 관련 쿼리 목록
        unrelated_queries (List[str]): 비관련 쿼리 목록
        model (Any): 평가할 임베딩 모델
        model_name (str): 모델 이름
        results_dir (Path): 결과 저장 디렉토리
        
    Returns:
        Dict[str, Any]: 평가 결과
    """
    print(f"모델 {model_name} 평가 중...")
    
    # 임베딩 생성
    text_embeddings = [get_embedding(text, model) for text in texts]
    related_query_embeddings = [get_embedding(query, model) for query in related_queries]
    unrelated_query_embeddings = [get_embedding(query, model) for query in unrelated_queries]
    all_query_embeddings = related_query_embeddings + unrelated_query_embeddings
    
    # 관련 쿼리와 비관련 쿼리 간의 유사도 차이 계산
    related_similarities = []
    for i, text_emb in enumerate(text_embeddings):
        for query_emb in related_query_embeddings:
            related_similarities.append(calculate_similarity(text_emb, query_emb))
    
    unrelated_similarities = []
    for i, text_emb in enumerate(text_embeddings):
        for query_emb in unrelated_query_embeddings:
            unrelated_similarities.append(calculate_similarity(text_emb, query_emb))
    
    avg_related_similarity = sum(related_similarities) / len(related_similarities)
    avg_unrelated_similarity = sum(unrelated_similarities) / len(unrelated_similarities)
    avg_difference = avg_related_similarity - avg_unrelated_similarity
    
    # 최적 임계값 찾기
    optimal_threshold, f1_score = find_optimal_threshold(
        text_embeddings, related_query_embeddings, unrelated_query_embeddings
    )
    
    # 성공률 계산 (최적 임계값으로 관련/비관련 구분 정확도)
    success_count = 0
    total_tests = len(related_similarities) + len(unrelated_similarities)
    
    for similarity in related_similarities:
        if similarity >= optimal_threshold:
            success_count += 1
            
    for similarity in unrelated_similarities:
        if similarity < optimal_threshold:
            success_count += 1
            
    success_rate = success_count / total_tests
    
    # MRR 계산
    mrr = calculate_mrr(text_embeddings, [related_query_embeddings], all_query_embeddings)
    
    # 다국어 평가 (간단히 구현)
    multilingual_similarity = avg_related_similarity  # 실제로는 다국어 쿼리로 테스트해야 함
    
    # 결과 저장
    results = {
        "model_name": model_name,
        "success_rate": round(success_rate, 2),
        "average_difference": round(avg_difference, 4),
        "mrr": round(mrr, 4),
        "optimal_threshold": round(optimal_threshold, 4),
        "f1_score": round(f1_score, 4),
        "multilingual_similarity": round(multilingual_similarity, 4),
        "timestamp": datetime.now().isoformat()
    }
    
    # 결과를 JSON 파일로 저장
    results_file = results_dir / f"{model_name}_embedding_evaluation_report.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"평가 결과 저장됨: {results_file}")
    return results

def evaluate_all_embedding_models(
    texts: List[str], 
    related_queries: List[str], 
    unrelated_queries: List[str],
    models: Dict[str, Any],
    results_dir: Path
) -> Dict[str, Dict[str, Any]]:
    """
    여러 임베딩 모델을 평가하고 비교합니다.
    
    Args:
        texts (List[str]): 평가용 텍스트 목록
        related_queries (List[str]): 관련 쿼리 목록
        unrelated_queries (List[str]): 비관련 쿼리 목록
        models (Dict[str, Any]): 모델 이름과 객체의 딕셔너리
        results_dir (Path): 결과 저장 디렉토리
        
    Returns:
        Dict[str, Dict[str, Any]]: 각 모델별 평가 결과
    """
    results = {}
    
    for model_name, model in models.items():
        model_results = evaluate_embedding_model(
            texts, related_queries, unrelated_queries, model, model_name, results_dir
        )
        results[model_name] = model_results
    
    # 비교 결과 저장
    comparison_file = results_dir / "embedding_models_comparison.json"
    with open(comparison_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    return results 