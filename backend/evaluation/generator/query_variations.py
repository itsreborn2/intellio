"""
평가를 위한 쿼리 변형 생성 모듈
"""
import re
import random
from typing import List, Dict, Any, Callable, Optional
from langchain_core.language_models import BaseLanguageModel
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

def generate_typo_variations(query: str, n: int = 2) -> List[str]:
    """
    쿼리에 오타를 추가하여 변형을 생성합니다.
    
    Args:
        query (str): 원본 쿼리
        n (int): 생성할 변형 수
    
    Returns:
        List[str]: 오타가 포함된 쿼리 변형 리스트
    """
    variations = []
    words = query.split()
    
    # 충분한 길이의 단어가 있는지 확인
    valid_words = [w for w in words if len(w) > 3]
    if not valid_words:
        valid_words = words
    
    for _ in range(n):
        if not words:
            continue
            
        # 변형할 단어 선택
        word_to_change = random.choice(valid_words)
        word_idx = words.index(word_to_change)
        
        # 변형 유형 선택
        variation_type = random.choice(["swap", "remove", "replace", "add"])
        
        if variation_type == "swap" and len(word_to_change) > 3:
            # 인접한 문자 위치 교환
            idx = random.randint(0, len(word_to_change) - 2)
            new_word = word_to_change[:idx] + word_to_change[idx+1] + word_to_change[idx] + word_to_change[idx+2:]
            
        elif variation_type == "remove" and len(word_to_change) > 3:
            # 문자 제거
            idx = random.randint(0, len(word_to_change) - 1)
            new_word = word_to_change[:idx] + word_to_change[idx+1:]
            
        elif variation_type == "replace":
            # 문자 대체
            idx = random.randint(0, len(word_to_change) - 1)
            replacements = "abcdefghijklmnopqrstuvwxyz"
            replacement = random.choice(replacements)
            new_word = word_to_change[:idx] + replacement + word_to_change[idx+1:]
            
        else:  # "add"
            # 문자 추가
            idx = random.randint(0, len(word_to_change))
            additions = "abcdefghijklmnopqrstuvwxyz"
            addition = random.choice(additions)
            new_word = word_to_change[:idx] + addition + word_to_change[idx:]
        
        # 변형된 쿼리 생성
        new_words = words.copy()
        new_words[word_idx] = new_word
        variation = " ".join(new_words)
        
        if variation != query and variation not in variations:
            variations.append(variation)
    
    return variations

def generate_incomplete_queries(query: str, n: int = 2) -> List[str]:
    """
    불완전한 쿼리 변형을 생성합니다.
    
    Args:
        query (str): 원본 쿼리
        n (int): 생성할 변형 수
    
    Returns:
        List[str]: 불완전한 쿼리 변형 리스트
    """
    variations = []
    words = query.split()
    
    if len(words) <= 2:
        # 쿼리가 너무 짧으면 일부만 사용
        for _ in range(min(n, len(words))):
            idx = random.randint(0, len(words) - 1)
            variations.append(words[idx])
        return variations
    
    for _ in range(n):
        # 제거할 단어 수 결정 (10% ~ 40%)
        remove_count = max(1, int(len(words) * random.uniform(0.1, 0.4)))
        
        # 제거할 단어 선택
        indices_to_remove = random.sample(range(len(words)), remove_count)
        
        # 변형 생성
        new_words = [w for i, w in enumerate(words) if i not in indices_to_remove]
        variation = " ".join(new_words)
        
        if variation != query and variation not in variations:
            variations.append(variation)
    
    return variations

def generate_semantic_variations(
    query: str, 
    n: int = 2, 
    llm: Optional[BaseLanguageModel] = None
) -> List[str]:
    """
    의미적으로 유사하지만 다른 표현의 쿼리 변형을 생성합니다.
    
    Args:
        query (str): 원본 쿼리
        n (int): 생성할 변형 수
        llm (Optional[BaseLanguageModel]): 사용할 언어 모델
    
    Returns:
        List[str]: 의미적으로 유사한 쿼리 변형 리스트
    """
    if not llm:
        #llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
        llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", temperature=0.7)
    
    prompt_template = """
    다음 쿼리를 의미는 유지하면서 다르게 표현한 {n}개의 변형을 생성해주세요.
    이 변형들은 같은 검색 결과를 반환할 수 있도록 의미적으로 유사해야 합니다.
    
    원본 쿼리: {query}
    
    각 변형은 새 줄에 표시하고, 줄 번호(1., 2., 등)를 붙이지 마세요. 
    변형만 반환하고 다른 설명이나 텍스트는 포함하지 마세요.
    """
    
    # 프롬프트 생성
    prompt = PromptTemplate.from_template(prompt_template)
    
    # 변형 생성
    chain = prompt | llm | StrOutputParser()
    
    try:
        result = chain.invoke({"query": query, "n": n})
        
        # 결과 파싱
        variations = [line.strip() for line in result.strip().split('\n') if line.strip()]
        
        # 중복 및 원본과 동일한 항목 제거
        variations = [v for v in variations if v != query]
        variations = list(dict.fromkeys(variations))  # 중복 제거
        
        return variations[:n]
    
    except Exception as e:
        print(f"의미적 변형 생성 중 오류 발생: {e}")
        return []

def generate_multilingual_variations(
    query: str, 
    languages: List[str] = None,
    llm: Optional[BaseLanguageModel] = None
) -> List[str]:
    """
    다국어 쿼리 변형을 생성합니다.
    
    Args:
        query (str): 원본 쿼리
        languages (List[str]): 변환할 언어 목록
        llm (Optional[BaseLanguageModel]): 사용할 언어 모델
    
    Returns:
        List[str]: 다국어 쿼리 변형 리스트
    """
    if not languages:
        languages = ["영어", "일본어", "중국어", "프랑스어"]
    
    if not llm:
        #llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", temperature=0)
    
    prompt_template = """
    다음 쿼리를 지정된 언어로 번역해주세요:
    
    쿼리: {query}
    언어: {language}
    
    번역만 반환하고 다른 설명이나 텍스트는 포함하지 마세요.
    """
    
    # 프롬프트 생성
    prompt = PromptTemplate.from_template(prompt_template)
    
    # 번역 체인
    chain = prompt | llm | StrOutputParser()
    
    variations = []
    for language in languages:
        try:
            translation = chain.invoke({"query": query, "language": language})
            translation = translation.strip()
            
            if translation and translation != query:
                variations.append(translation)
        
        except Exception as e:
            print(f"{language}로 번역 중 오류 발생: {e}")
    
    return variations

def generate_ambiguous_queries(
    query: str, 
    n: int = 2,
    llm: Optional[BaseLanguageModel] = None
) -> List[str]:
    """
    모호한 쿼리 변형을 생성합니다.
    
    Args:
        query (str): 원본 쿼리
        n (int): 생성할 변형 수
        llm (Optional[BaseLanguageModel]): 사용할 언어 모델
    
    Returns:
        List[str]: 모호한 쿼리 변형 리스트
    """
    if not llm:
        #llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
        llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", temperature=0.7)
    
    prompt_template = """
    다음 쿼리를 의도적으로 모호하게 만든 {n}개의 변형을 생성해주세요.
    이 변형들은 원래 쿼리의 일부 의미를 유지하되, 정확히 무엇을 물어보는지 명확하지 않아야 합니다.
    
    원본 쿼리: {query}
    
    각 변형은 새 줄에 표시하고, 줄 번호(1., 2., 등)를 붙이지 마세요.
    변형만 반환하고 다른 설명이나 텍스트는 포함하지 마세요.
    """
    
    # 프롬프트 생성
    prompt = PromptTemplate.from_template(prompt_template)
    
    # 변형 생성
    chain = prompt | llm | StrOutputParser()
    
    try:
        result = chain.invoke({"query": query, "n": n})
        
        # 결과 파싱
        variations = [line.strip() for line in result.strip().split('\n') if line.strip()]
        
        # 중복 및 원본과 동일한 항목 제거
        variations = [v for v in variations if v != query]
        variations = list(dict.fromkeys(variations))  # 중복 제거
        
        return variations[:n]
    
    except Exception as e:
        print(f"모호한 변형 생성 중 오류 발생: {e}")
        return []

def generate_all_variations(
    query: str,
    variation_types: List[str] = None,
    llm: Optional[BaseLanguageModel] = None
) -> Dict[str, List[str]]:
    """
    모든 유형의 쿼리 변형을 생성합니다.
    
    Args:
        query (str): 원본 쿼리
        variation_types (List[str]): 생성할 변형 유형 목록
        llm (Optional[BaseLanguageModel]): 사용할 언어 모델
    
    Returns:
        Dict[str, List[str]]: 변형 유형별 쿼리 변형 리스트
    """
    if not variation_types:
        variation_types = ["typo", "incomplete", "semantic", "multilingual", "ambiguous"]
    
    if not llm:
        #llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
        llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", temperature=0.7)
    
    variations = {}
    
    if "typo" in variation_types:
        variations["typo"] = generate_typo_variations(query, n=2)
    
    if "incomplete" in variation_types:
        variations["incomplete"] = generate_incomplete_queries(query, n=2)
    
    if "semantic" in variation_types:
        variations["semantic"] = generate_semantic_variations(query, n=2, llm=llm)
    
    if "multilingual" in variation_types:
        variations["multilingual"] = generate_multilingual_variations(query, llm=llm)
    
    if "ambiguous" in variation_types:
        variations["ambiguous"] = generate_ambiguous_queries(query, n=2, llm=llm)
    
    return variations

def get_query_variations_generator(
    variation_types: List[str] = None,
    llm: Optional[BaseLanguageModel] = None
) -> Callable[[str], List[str]]:
    """
    쿼리 변형 생성기 함수를 반환합니다.
    
    Args:
        variation_types (List[str]): 생성할 변형 유형 목록
        llm (Optional[BaseLanguageModel]): 사용할 언어 모델
    
    Returns:
        Callable[[str], List[str]]: 쿼리 변형 생성 함수
    """
    if not variation_types:
        variation_types = ["typo", "incomplete", "semantic"]
    
    if not llm:
        #llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
        llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", temperature=0.7)
        
    def generate_variations(query: str) -> List[str]:
        """
        주어진 쿼리에 대한 변형을 생성합니다.
        
        Args:
            query (str): 원본 쿼리
            
        Returns:
            List[str]: 쿼리 변형 리스트
        """
        variations_dict = generate_all_variations(query, variation_types, llm)
        
        # 모든 변형을 하나의 리스트로 결합
        all_variations = []
        for var_type, vars_list in variations_dict.items():
            all_variations.extend(vars_list)
        
        # 중복 제거
        all_variations = list(dict.fromkeys(all_variations))
        
        return all_variations
    
    return generate_variations 