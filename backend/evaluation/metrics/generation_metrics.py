"""
응답 생성(Generation) 품질 평가를 위한 메트릭 모듈
"""
import json
import time
import numpy as np
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path
from datetime import datetime
from langchain_core.language_models import BaseLanguageModel
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

def evaluate_factual_consistency(
    response: str, 
    reference_texts: List[str], 
    llm: BaseLanguageModel
) -> Dict[str, Any]:
    """
    응답의 사실적 일관성을 평가합니다.
    
    Args:
        response (str): 평가할 응답 텍스트
        reference_texts (List[str]): 참조 문서 텍스트 리스트
        llm (BaseLanguageModel): 평가에 사용할 LLM
    
    Returns:
        Dict[str, Any]: 사실적 일관성 평가 결과
    """
    prompt_template = """
    당신은 생성된 응답의 품질을 평가하는 전문가입니다.
    아래의 참조 문서들을 바탕으로 생성된 응답의 사실적 일관성을 0부터 10까지의 점수로 평가해주세요.
    
    # 참조 문서들:
    {reference_texts}
    
    # 평가할 응답:
    {response}
    
    # 평가 기준:
    - 응답이 참조 문서의 정보와 일치하는가?
    - 응답이 참조 문서에 없는 정보를 포함하는가? (환각)
    - 응답이 참조 문서의 정보를 왜곡하는가?
    
    # 평가 방법:
    1. JSON 형식으로 다음 필드를 포함하여 응답하세요:
       - score: 0-10 사이의 정수 점수
       - hallucinations: 환각 정보 리스트
       - contradictions: 모순된 정보 리스트
       - reasoning: 이 점수를 준 이유
    
    응답은 다음과 같은 JSON 형식으로 작성하세요:
    ```json
    {
      "score": 점수,
      "hallucinations": ["환각1", "환각2", ...],
      "contradictions": ["모순1", "모순2", ...],
      "reasoning": "점수 부여 이유"
    }
    ```
    """
    
    # 참조 문서 결합
    combined_references = "\n\n".join([f"문서 {i+1}: {text}" for i, text in enumerate(reference_texts)])
    
    # 프롬프트 생성
    prompt = PromptTemplate.from_template(prompt_template)
    
    # 평가 수행
    chain = prompt | llm | StrOutputParser()
    
    try:
        result_str = chain.invoke({
            "reference_texts": combined_references,
            "response": response
        })
        
        # JSON 문자열 추출 (백틱 제거)
        json_str = result_str.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
        
        # JSON 파싱
        result = json.loads(json_str)
        
        # 결과 형식화
        return {
            "factual_consistency_score": result.get("score", 0),
            "hallucinations": result.get("hallucinations", []),
            "contradictions": result.get("contradictions", []),
            "reasoning": result.get("reasoning", "")
        }
    except Exception as e:
        print(f"평가 중 오류 발생: {e}")
        return {
            "factual_consistency_score": 0,
            "hallucinations": [],
            "contradictions": [],
            "reasoning": f"평가 중 오류 발생: {e}"
        }

def evaluate_coherence(response: str, llm: BaseLanguageModel) -> Dict[str, Any]:
    """
    응답의 일관성과 연결성을 평가합니다.
    
    Args:
        response (str): 평가할 응답 텍스트
        llm (BaseLanguageModel): 평가에 사용할 LLM
    
    Returns:
        Dict[str, Any]: 일관성 평가 결과
    """
    prompt_template = """
    당신은 텍스트의 품질을 평가하는 전문가입니다.
    아래 제공된 텍스트의 일관성(coherence)과 연결성(cohesion)을 0부터 10까지의 점수로 평가해주세요.
    
    # 평가할 텍스트:
    {response}
    
    # 평가 기준:
    - 논리적 흐름: 문장과 단락이 논리적으로 연결되는가?
    - 일관성: 전체 텍스트가 일관된 주제나 주장을 유지하는가?
    - 연결성: 문장 간, 단락 간 전환이 자연스러운가?
    - 구조: 텍스트가 잘 구조화되어 있는가?
    
    # 평가 방법:
    1. JSON 형식으로 다음 필드를 포함하여 응답하세요:
       - coherence_score: 0-10 사이의 일관성 점수
       - issues: 발견된 일관성 문제 리스트
       - reasoning: 이 점수를 준 이유
    
    응답은 다음과 같은 JSON 형식으로 작성하세요:
    ```json
    {
      "coherence_score": 점수,
      "issues": ["문제1", "문제2", ...],
      "reasoning": "점수 부여 이유"
    }
    ```
    """
    
    # 프롬프트 생성
    prompt = PromptTemplate.from_template(prompt_template)
    
    # 평가 수행
    chain = prompt | llm | StrOutputParser()
    
    try:
        result_str = chain.invoke({"response": response})
        
        # JSON 문자열 추출 (백틱 제거)
        json_str = result_str.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
        
        # JSON 파싱
        result = json.loads(json_str)
        
        # 결과 형식화
        return {
            "coherence_score": result.get("coherence_score", 0),
            "issues": result.get("issues", []),
            "reasoning": result.get("reasoning", "")
        }
    except Exception as e:
        print(f"평가 중 오류 발생: {e}")
        return {
            "coherence_score": 0,
            "issues": [f"평가 중 오류 발생: {e}"],
            "reasoning": f"평가 중 오류 발생: {e}"
        }

def evaluate_relevance(
    query: str, 
    response: str, 
    llm: BaseLanguageModel
) -> Dict[str, Any]:
    """
    쿼리에 대한 응답의 관련성을 평가합니다.
    
    Args:
        query (str): 원본 쿼리
        response (str): 평가할 응답 텍스트
        llm (BaseLanguageModel): 평가에 사용할 LLM
    
    Returns:
        Dict[str, Any]: 관련성 평가 결과
    """
    prompt_template = """
    당신은 생성된 응답의 품질을 평가하는 전문가입니다.
    아래 제공된 쿼리에 대한 응답의 관련성을 0부터 10까지의 점수로 평가해주세요.
    
    # 쿼리:
    {query}
    
    # 응답:
    {response}
    
    # 평가 기준:
    - 응답이 쿼리에 직접적으로 관련되는가?
    - 응답이 쿼리의 의도에 맞게 생성되었는가?
    - 응답이 쿼리에서 요구하는 정보를 모두 포함하는가?
    - 응답에 불필요한 정보가 포함되어 있는가?
    
    # 평가 방법:
    1. JSON 형식으로 다음 필드를 포함하여 응답하세요:
       - relevance_score: 0-10 사이의 관련성 점수
       - missing_info: 누락된 정보 리스트
       - irrelevant_info: 불필요한 정보 리스트
       - reasoning: 이 점수를 준 이유
    
    응답은 다음과 같은 JSON 형식으로 작성하세요:
    ```json
    {
      "relevance_score": 점수,
      "missing_info": ["누락정보1", "누락정보2", ...],
      "irrelevant_info": ["불필요정보1", "불필요정보2", ...],
      "reasoning": "점수 부여 이유"
    }
    ```
    """
    
    # 프롬프트 생성
    prompt = PromptTemplate.from_template(prompt_template)
    
    # 평가 수행
    chain = prompt | llm | StrOutputParser()
    
    try:
        result_str = chain.invoke({
            "query": query,
            "response": response
        })
        
        # JSON 문자열 추출 (백틱 제거)
        json_str = result_str.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
        
        # JSON 파싱
        result = json.loads(json_str)
        
        # 결과 형식화
        return {
            "relevance_score": result.get("relevance_score", 0),
            "missing_info": result.get("missing_info", []),
            "irrelevant_info": result.get("irrelevant_info", []),
            "reasoning": result.get("reasoning", "")
        }
    except Exception as e:
        print(f"평가 중 오류 발생: {e}")
        return {
            "relevance_score": 0,
            "missing_info": [],
            "irrelevant_info": [f"평가 중 오류 발생: {e}"],
            "reasoning": f"평가 중 오류 발생: {e}"
        }

def evaluate_helpfulness(
    query: str, 
    response: str, 
    llm: BaseLanguageModel
) -> Dict[str, Any]:
    """
    응답의 유용성을 평가합니다.
    
    Args:
        query (str): 원본 쿼리
        response (str): 평가할 응답 텍스트
        llm (BaseLanguageModel): 평가에 사용할 LLM
    
    Returns:
        Dict[str, Any]: 유용성 평가 결과
    """
    prompt_template = """
    당신은 생성된 응답의 유용성을 평가하는 전문가입니다.
    아래 제공된 쿼리에 대한 응답의 유용성을 0부터 10까지의 점수로 평가해주세요.
    
    # 쿼리:
    {query}
    
    # 응답:
    {response}
    
    # 평가 기준:
    - 응답이 사용자에게 실질적인 도움을 제공하는가?
    - 응답이 행동 가능한 정보를 제공하는가?
    - 응답이 사용자의 문제를 해결하는 데 도움이 되는가?
    - 응답이 명확하고 이해하기 쉬운가?
    
    # 평가 방법:
    1. JSON 형식으로 다음 필드를 포함하여 응답하세요:
       - helpfulness_score: 0-10 사이의 유용성 점수
       - improvements: 개선 가능한 부분 리스트
       - strengths: 응답의 강점 리스트
       - reasoning: 이 점수를 준 이유
    
    응답은 다음과 같은 JSON 형식으로 작성하세요:
    ```json
    {
      "helpfulness_score": 점수,
      "improvements": ["개선점1", "개선점2", ...],
      "strengths": ["강점1", "강점2", ...],
      "reasoning": "점수 부여 이유"
    }
    ```
    """
    
    # 프롬프트 생성
    prompt = PromptTemplate.from_template(prompt_template)
    
    # 평가 수행
    chain = prompt | llm | StrOutputParser()
    
    try:
        result_str = chain.invoke({
            "query": query,
            "response": response
        })
        
        # JSON 문자열 추출 (백틱 제거)
        json_str = result_str.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
        
        # JSON 파싱
        result = json.loads(json_str)
        
        # 결과 형식화
        return {
            "helpfulness_score": result.get("helpfulness_score", 0),
            "improvements": result.get("improvements", []),
            "strengths": result.get("strengths", []),
            "reasoning": result.get("reasoning", "")
        }
    except Exception as e:
        print(f"평가 중 오류 발생: {e}")
        return {
            "helpfulness_score": 0,
            "improvements": [f"평가 중 오류 발생: {e}"],
            "strengths": [],
            "reasoning": f"평가 중 오류 발생: {e}"
        }

def evaluate_completeness(
    query: str, 
    response: str, 
    llm: BaseLanguageModel
) -> Dict[str, Any]:
    """
    응답의 완전성을 평가합니다.
    
    Args:
        query (str): 원본 쿼리
        response (str): 평가할 응답 텍스트
        llm (BaseLanguageModel): 평가에 사용할 LLM
    
    Returns:
        Dict[str, Any]: 완전성 평가 결과
    """
    prompt_template = """
    당신은 생성된 응답의 완전성을 평가하는 전문가입니다.
    아래 제공된 쿼리에 대한 응답의 완전성을 0부터 10까지의 점수로 평가해주세요.
    
    # 쿼리:
    {query}
    
    # 응답:
    {response}
    
    # 평가 기준:
    - 응답이 쿼리의 모든 측면을 다루는가?
    - 응답이 충분한 세부 정보와 컨텍스트를 제공하는가?
    - 응답에서 중요한 정보나 측면이 누락되었는가?
    - 응답이 쿼리에 대해 종합적인 이해를 보여주는가?
    
    # 평가 방법:
    1. JSON 형식으로 다음 필드를 포함하여 응답하세요:
       - completeness_score: 0-10 사이의 완전성 점수
       - missing_aspects: 누락된 측면 리스트
       - reasoning: 이 점수를 준 이유
    
    응답은 다음과 같은 JSON 형식으로 작성하세요:
    ```json
    {
      "completeness_score": 점수,
      "missing_aspects": ["누락측면1", "누락측면2", ...],
      "reasoning": "점수 부여 이유"
    }
    ```
    """
    
    # 프롬프트 생성
    prompt = PromptTemplate.from_template(prompt_template)
    
    # 평가 수행
    chain = prompt | llm | StrOutputParser()
    
    try:
        result_str = chain.invoke({
            "query": query,
            "response": response
        })
        
        # JSON 문자열 추출 (백틱 제거)
        json_str = result_str.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
        
        # JSON 파싱
        result = json.loads(json_str)
        
        # 결과 형식화
        return {
            "completeness_score": result.get("completeness_score", 0),
            "missing_aspects": result.get("missing_aspects", []),
            "reasoning": result.get("reasoning", "")
        }
    except Exception as e:
        print(f"평가 중 오류 발생: {e}")
        return {
            "completeness_score": 0,
            "missing_aspects": [f"평가 중 오류 발생: {e}"],
            "reasoning": f"평가 중 오류 발생: {e}"
        }

def evaluate_generation_comprehensive(
    query: str,
    response: str,
    reference_texts: List[str],
    llm: BaseLanguageModel = None
) -> Dict[str, Any]:
    """
    응답의 종합적인 품질을 평가합니다.
    
    Args:
        query (str): 원본 쿼리
        response (str): 평가할 응답 텍스트
        reference_texts (List[str]): 참조 문서 텍스트 리스트
        llm (BaseLanguageModel, optional): 평가에 사용할 LLM. 기본값은 None(자동 생성)
    
    Returns:
        Dict[str, Any]: 종합 평가 결과
    """
    # LLM이 제공되지 않은 경우 기본 모델 사용
    if llm is None:
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    # 모든 평가 실행
    start_time = time.time()
    
    factual_result = evaluate_factual_consistency(response, reference_texts, llm)
    coherence_result = evaluate_coherence(response, llm)
    relevance_result = evaluate_relevance(query, response, llm)
    helpfulness_result = evaluate_helpfulness(query, response, llm)
    completeness_result = evaluate_completeness(query, response, llm)
    
    end_time = time.time()
    
    # 종합 점수 계산 (가중치 적용)
    weighted_scores = {
        "factual_consistency": factual_result["factual_consistency_score"] * 0.3,
        "coherence": coherence_result["coherence_score"] * 0.15,
        "relevance": relevance_result["relevance_score"] * 0.2,
        "helpfulness": helpfulness_result["helpfulness_score"] * 0.2,
        "completeness": completeness_result["completeness_score"] * 0.15
    }
    
    overall_score = sum(weighted_scores.values())
    
    # 종합 결과 생성
    results = {
        "overall_score": overall_score,
        "weighted_scores": weighted_scores,
        "evaluation_time_seconds": end_time - start_time,
        "detailed_results": {
            "factual_consistency": factual_result,
            "coherence": coherence_result,
            "relevance": relevance_result,
            "helpfulness": helpfulness_result,
            "completeness": completeness_result
        }
    }
    
    return results

def save_generation_evaluation_results(
    results: Dict[str, Any], 
    model_name: str, 
    results_dir: Path
) -> None:
    """
    생성 평가 결과를 저장합니다.
    
    Args:
        results (Dict[str, Any]): 평가 결과
        model_name (str): 평가한 모델 이름
        results_dir (Path): 결과 저장 디렉토리
    """
    results_with_meta = {
        "model_name": model_name,
        "timestamp": datetime.now().isoformat(),
        "results": results
    }
    
    # 결과를 JSON 파일로 저장
    results_file = results_dir / f"{model_name}_generation_evaluation_report.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results_with_meta, f, ensure_ascii=False, indent=2)
    
    print(f"생성 평가 결과 저장됨: {results_file}") 