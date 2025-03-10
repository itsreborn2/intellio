"""
LangSmith를 활용한 RAG 시스템 평가 모듈
"""
import os
import json
import time
from langchain_google_genai import ChatGoogleGenerativeAI
import numpy as np
import re
from typing import Dict, List, Any, Optional, Union, Callable, Set
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel
import uuid
import math

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langsmith import Client
from langsmith.evaluation import RunEvaluator, EvaluationResult
from langsmith.schemas import Example, Run, RunTypeEnum
from langchain_openai import OpenAIEmbeddings
#from langchain_chat_openai import ChatOpenAI

# 평가 시스템 설정 불러오기
from evaluation.config import LANGSMITH_API_KEY, LANGSMITH_PROJECT_PREFIX, RESULTS_DIR

def extract_doc_number(doc_id):
    """문서 ID에서 숫자 부분을 추출"""
    if not isinstance(doc_id, str):
        return None
    numbers = re.findall(r'\d+(?:_\d+)*', doc_id)
    return numbers[0] if numbers else None

def extract_filename_parts(path):
    """파일 경로에서 유용한 부분들을 추출"""
    parts = []
    try:
        # 전체 경로
        parts.append(path)
        
        # 파일명 (확장자 포함)
        basename = os.path.basename(path)
        parts.append(basename)
        
        # 확장자 제거한 파일명
        filename_no_ext = os.path.splitext(basename)[0]
        parts.append(filename_no_ext)
        
        # 파일명에서 숫자 추출
        numbers = re.findall(r'\d+', basename)
        parts.extend(numbers)
        
        # P 다음에 오는 숫자 (예: P82 -> 82)
        p_numbers = re.findall(r'P(\d+)', basename)
        parts.extend(p_numbers)
    except:
        pass
# JSON 직렬화를 위한 커스텀 인코더 추가
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)

class RAGEvaluationExample(BaseModel):
    """RAG 평가를 위한 예제 데이터 모델"""
    query: str
    ground_truth: str
    retrieved_documents: List[str]
    expected_sources: List[str]
    generated_response: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class CorrectnessEvaluator(RunEvaluator):
    """정확성 평가기"""
    def __init__(self, embedding_model=None):
        """
        Args:
            embedding_model: 임베딩 모델 (없으면 기본 모델 사용)
        """
        # 임베딩 모델 초기화 (API 키가 환경 변수에 이미 설정되어 있다고 가정)
        try:
            self.embedding_model = embedding_model or OpenAIEmbeddings()
            self.use_embeddings = True
        except Exception as e:
            print(f"임베딩 모델 초기화 실패: {e}")
            self.use_embeddings = False
        
    def evaluate_run(self, run, example) -> EvaluationResult:
        prediction = run.outputs.get("output", "")
        reference = example.outputs.get("ground_truth", "")
        
        # 정확히 일치하는 경우
        if prediction.strip() == reference.strip():
            score = 1.0
            comment = "완벽히 일치합니다."
            return EvaluationResult(
                key="correctness",
                score=score,
                comment=comment
            )
        
        # 다양한 메트릭 계산
        lexical_score = self._calculate_lexical_similarity(prediction, reference)
        rouge_score = self._calculate_rouge_score(prediction, reference)
        
        # 의미적 유사도 계산 (가능한 경우)
        semantic_score = 0.0
        if self.use_embeddings:
            try:
                semantic_score = self._calculate_semantic_similarity(prediction, reference)
            except Exception as e:
                print(f"의미적 유사도 계산 실패: {e}")
                semantic_score = lexical_score  # 실패 시 어휘적 유사도로 대체
        else:
            semantic_score = lexical_score  # 임베딩 모델이 없으면 어휘적 유사도로 대체
        
        # 가중 평균으로 최종 점수 계산 (의미적 유사도에 더 높은 가중치)
        final_score = 0.5 * semantic_score + 0.3 * rouge_score + 0.2 * lexical_score
        
        # 점수에 따른 코멘트
        if final_score > 0.8:
            comment = "매우 정확합니다."
        elif final_score > 0.6:
            comment = "대체로 정확합니다."
        elif final_score > 0.4:
            comment = "부분적으로 정확합니다."
        else:
            comment = "정확도가 낮습니다."
        
        return EvaluationResult(
            key="correctness",
            score=final_score,
            comment=f"정확성 점수: {final_score:.2f} - {comment}"
        )
    
    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """의미적 유사도 계산 (임베딩 기반)"""
        try:
            # 텍스트 임베딩 생성
            embedding1 = self.embedding_model.embed_query(text1)
            embedding2 = self.embedding_model.embed_query(text2)
            
            # 코사인 유사도 계산
            similarity = self._cosine_similarity(embedding1, embedding2)
            return similarity
        except Exception as e:
            print(f"의미적 유사도 계산 중 오류: {e}")
            return 0.0
    
    def _cosine_similarity(self, vec1, vec2):
        """코사인 유사도 계산"""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        return dot_product / (norm1 * norm2) if norm1 * norm2 > 0 else 0.0
    
    def _calculate_lexical_similarity(self, text1: str, text2: str) -> float:
        """어휘적 유사도 계산 (자카드 유사도)"""
        # 공백 제거 및 소문자 변환
        text1 = text1.strip().lower()
        text2 = text2.strip().lower()
        
        # 각 텍스트를 단어 집합으로 변환
        set1 = set(text1.split())
        set2 = set(text2.split())
        
        # 자카드 유사도 계산: 교집합 크기 / 합집합 크기
        if not set1 or not set2:
            return 0.0
            
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_rouge_score(self, text1: str, text2: str) -> float:
        """ROUGE-L 점수 계산 (최장 공통 부분 시퀀스 기반)"""
        try:
            # 간단한 ROUGE-L 구현
            words1 = text1.lower().split()
            words2 = text2.lower().split()
            
            # LCS 길이 계산
            lcs_length = self._lcs_length(words1, words2)
            
            # ROUGE-L 계산
            if not words1 or not words2:
                return 0.0
                
            precision = lcs_length / len(words1) if words1 else 0
            recall = lcs_length / len(words2) if words2 else 0
            
            # F1 점수 계산
            if precision + recall > 0:
                return 2 * precision * recall / (precision + recall)
            return 0.0
        except Exception as e:
            print(f"ROUGE 점수 계산 중 오류: {e}")
            return 0.0
    
    def _lcs_length(self, seq1, seq2):
        """최장 공통 부분 시퀀스(LCS) 길이 계산"""
        m, n = len(seq1), len(seq2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if seq1[i-1] == seq2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        
        return dp[m][n]

class RelevanceEvaluator(RunEvaluator):
    """관련성 평가기"""
    def __init__(self, llm=None):
        """
        Args:
            llm: 평가에 사용할 LLM (없으면 기본 모델 사용)
        """
        try:
            # LLM 초기화 (없으면 기본 ChatOpenAI 사용)
            #self.llm = llm or ChatOpenAI(temperature=0, model="gpt-3.5-turbo")
            self.llm = llm or ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", temperature=0)
            self.use_llm = True
            
            # 임베딩 모델 초기화 (API 키가 환경 변수에 이미 설정되어 있다고 가정)
            try:
                self.embedding_model = OpenAIEmbeddings()
                self.use_embeddings = True
            except Exception as e:
                print(f"임베딩 모델 초기화 실패: {e}")
                self.use_embeddings = False
                
        except Exception as e:
            print(f"LLM 초기화 실패: {e}")
            self.use_llm = False
    
    def evaluate_run(self, run, example) -> EvaluationResult:
        prediction = run.outputs.get("output", "")
        query = example.inputs.get("query", "")
        
        # LLM과 기존 방식을 조합한 관련성 평가
        if self.use_llm:
            try:
                llm_score = self._calculate_llm_relevance(prediction, query)
                traditional_score = self._calculate_relevance_score(prediction, query)
                semantic_score = 0
                
                # 의미적 유사도 계산 (가능한 경우)
                if self.use_embeddings:
                    try:
                        semantic_score = self._calculate_semantic_relevance(prediction, query)
                    except Exception as e:
                        print(f"의미적 관련성 계산 실패: {e}")
                        semantic_score = traditional_score
                else:
                    semantic_score = traditional_score
                
                # 가중치 조합 (LLM 50%, 의미적 30%, 전통적 20%)
                score = 0.5 * llm_score + 0.3 * semantic_score + 0.2 * traditional_score
            except Exception as e:
                print(f"LLM 기반 관련성 평가 실패: {e}")
                score = self._calculate_relevance_score(prediction, query)
        else:
            score = self._calculate_relevance_score(prediction, query)
        
        if score > 0.8:
            comment = "매우 관련성이 높습니다."
        elif score > 0.6:
            comment = "관련성이 높은 편입니다."
        elif score > 0.4:
            comment = "부분적으로 관련이 있습니다."
        else:
            comment = "관련성이 낮습니다."
        
        return EvaluationResult(
            key="relevance",
            score=score,
            comment=f"관련성 점수: {score:.2f} - {comment}"
        )
    
    def _calculate_llm_relevance(self, prediction: str, query: str) -> float:
        """LLM을 사용하여 예측과 쿼리의 관련성을 평가합니다."""
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""
                당신은 텍스트 응답과 쿼리 간의 관련성을 평가하는 전문가입니다.
                응답이 쿼리에서 요청한 정보를 직접적으로 다루는지
                - 응답이 쿼리의 의도와 맥락을 이해하고 있는지
                - 응답이 쿼리와 관련된 주요 개념과 주제를 포함하는지
                오직 숫자만 출력해주세요 (0~10).
            """),
            HumanMessage(content=f"""
                쿼리: {query}
                
                응답: {prediction}
                
                관련성 점수 (0~10):
            """)
        ])
        
        try:
            response = self.llm.invoke(prompt)
            # 응답에서 숫자만 추출
            score_text = re.search(r'(\d+(\.\d+)?)', response.content)
            if score_text:
                score = float(score_text.group(1))
                # 0-10 범위를 0-1 범위로 변환
                return min(1.0, max(0.0, score / 10.0))
            return 0.5  # 기본값
        except Exception as e:
            print(f"LLM 관련성 평가 중 오류: {e}")
            return 0.5
    
    def _calculate_semantic_relevance(self, prediction: str, query: str) -> float:
        """임베딩을 사용한 의미적 관련성 계산"""
        try:
            # 텍스트 임베딩 생성
            query_embedding = self.embedding_model.embed_query(query)
            prediction_embedding = self.embedding_model.embed_query(prediction)
            
            # 코사인 유사도 계산
            dot_product = sum(a * b for a, b in zip(query_embedding, prediction_embedding))
            norm1 = sum(a * a for a in query_embedding) ** 0.5
            norm2 = sum(b * b for b in prediction_embedding) ** 0.5
            similarity = dot_product / (norm1 * norm2) if norm1 * norm2 > 0 else 0.0
            
            return similarity
        except Exception as e:
            print(f"의미적 관련성 계산 중 오류: {e}")
            return 0.0
    
    def _calculate_relevance_score(self, prediction: str, query: str) -> float:
        """
        예측 결과와 쿼리 간의 관련성 점수를 계산합니다.
        키워드 매칭과 문맥 관련성을 고려합니다.
        """
        # 소문자 변환 및 기본 전처리
        prediction_lower = prediction.lower()
        query_lower = query.lower()
        
        # 1. 키워드 매칭 점수 (50%)
        keywords = [word for word in query_lower.split() if len(word) > 2]  # 짧은 단어 제외
        if not keywords:
            keywords = query_lower.split()
            
        keyword_matches = sum(1 for keyword in keywords if keyword in prediction_lower)
        keyword_score = keyword_matches / max(1, len(keywords))
        
        # 2. 문맥 관련성 점수 (50%)
        # 쿼리의 핵심 구문이 예측에 포함되어 있는지 확인
        query_phrases = self._extract_phrases(query_lower)
        phrase_matches = sum(1 for phrase in query_phrases if phrase in prediction_lower)
        phrase_score = phrase_matches / max(1, len(query_phrases))
        
        # 최종 점수 계산 (키워드 50%, 구문 50%)
        final_score = 0.5 * keyword_score + 0.5 * phrase_score
        
        return min(1.0, final_score)
    
    def _extract_phrases(self, text: str) -> List[str]:
        """텍스트에서 의미 있는 구문을 추출합니다."""
        words = text.split()
        phrases = []
        
        # 2단어 구문 추출
        if len(words) >= 2:
            phrases.extend([" ".join(words[i:i+2]) for i in range(len(words)-1)])
        
        # 3단어 구문 추출 (있는 경우)
        if len(words) >= 3:
            phrases.extend([" ".join(words[i:i+3]) for i in range(len(words)-2)])
            
        return phrases

class FaithfulnessEvaluator(RunEvaluator):
    """충실도 평가기"""
    def __init__(self, llm=None):
        """
        Args:
            llm: 평가에 사용할 LLM (없으면 기본 모델 사용)
        """
        try:
            # LLM 초기화 (없으면 기본 ChatOpenAI 사용)
            #self.llm = llm or ChatOpenAI(temperature=0, model="gpt-3.5-turbo")
            self.llm = llm or ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", temperature=0)
            self.use_llm = True
        except Exception as e:
            print(f"LLM 초기화 실패: {e}")
            self.use_llm = False
    
    def evaluate_run(self, run, example) -> EvaluationResult:
        prediction = run.outputs.get("output", "")
        retrieved_docs = example.inputs.get("retrieved_documents", [])
        
        # LLM과 기존 방식을 조합한 충실도 평가
        if self.use_llm and retrieved_docs:
            try:
                llm_score = self._calculate_llm_faithfulness(prediction, retrieved_docs)
                traditional_score = self._calculate_faithfulness_score(prediction, retrieved_docs)
                
                # 가중치 조합 (LLM 70%, 전통적 30%)
                score = 0.7 * llm_score + 0.3 * traditional_score
            except Exception as e:
                print(f"LLM 기반 충실도 평가 실패: {e}")
                score = self._calculate_faithfulness_score(prediction, retrieved_docs)
        else:
            score = self._calculate_faithfulness_score(prediction, retrieved_docs)
        
        if score > 0.8:
            comment = "매우 충실하게 문서 내용을 반영합니다."
        elif score > 0.6:
            comment = "대체로 문서 내용에 충실합니다."
        elif score > 0.4:
            comment = "부분적으로 문서 내용을 반영합니다."
        else:
            comment = "문서 내용과 일치하지 않는 부분이 많습니다."
        
        return EvaluationResult(
            key="faithfulness",
            score=score,
            comment=f"충실도 점수: {score:.2f} - {comment}"
        )
    
    def _calculate_llm_faithfulness(self, prediction: str, retrieved_docs: List[str]) -> float:
        """LLM을 사용하여 예측이 검색된 문서에 얼마나 충실한지 평가합니다."""
        # 문서 내용 결합 (너무 길 경우 일부만 사용)
        doc_content = " ".join(retrieved_docs)
        if len(doc_content) > 4000:
            doc_content = doc_content[:4000] + "..."
        
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""
                당신은 텍스트 응답이 주어진 문서 내용에 얼마나 충실한지 평가하는 전문가입니다.
                응답이 문서 내용에만 기반하고 있는지, 혹은 문서에 없는 정보를 생성했는지 평가하세요.
                다음 기준으로 0~10 척도의 점수를 매겨주세요:
                - 10: 응답이 전적으로 문서 내용에만 기반하고, 어떤 정보도 추가/변경하지 않음
                - 7-9: 대부분 문서 내용에 충실하지만, 사소한 추론이나 요약이 있음
                - 4-6: 문서 내용을 일부 반영하지만, 문서에 없는 내용도 포함됨
                - 1-3: 응답이 대부분 문서 내용과 관련이 없음
                - 0: 응답이 전혀 문서 내용을 반영하지 않음
                
                환각(hallucination)이나 문서에 없는 정보 생성을 감지하는 데 주의하세요.
                오직 숫자만 출력해주세요 (0~10).
            """),
            HumanMessage(content=f"""
                문서 내용: {doc_content}
                
                응답: {prediction}
                
                충실도 점수 (0~10):
            """)
        ])
        
        try:
            response = self.llm.invoke(prompt)
            # 응답에서 숫자만 추출
            score_text = re.search(r'(\d+(\.\d+)?)', response.content)
            if score_text:
                score = float(score_text.group(1))
                # 0-10 범위를 0-1 범위로 변환
                return min(1.0, max(0.0, score / 10.0))
            return 0.5  # 기본값
        except Exception as e:
            print(f"LLM 충실도 평가 중 오류: {e}")
            return 0.5
    
    def _calculate_faithfulness_score(self, prediction: str, retrieved_docs: List[str]) -> float:
        """
        예측 결과가 검색된 문서 내용에 얼마나 충실한지 점수를 계산합니다.
        """
        if not retrieved_docs or not prediction:
            return 0.0
            
        # 문서 내용 결합
        doc_content = " ".join(retrieved_docs).lower()
        prediction_lower = prediction.lower()
        
        # 1. 단어 기반 충실도 (40%)
        doc_words = set(w for w in doc_content.split() if len(w) > 3)  # 짧은 단어 제외
        prediction_words = set(w for w in prediction_lower.split() if len(w) > 3)
        
        if not doc_words or not prediction_words:
            word_score = 0.0
        else:
            # 예측에 사용된 단어 중 문서에 있는 단어의 비율
            common_words = doc_words.intersection(prediction_words)
            word_score = len(common_words) / len(prediction_words) if prediction_words else 0.0
        
        # 2. 구문 기반 충실도 (60%)
        prediction_phrases = self._extract_phrases(prediction_lower)
        
        if not prediction_phrases:
            phrase_score = 0.0
        else:
            # 예측의 구문이 문서에 포함된 비율
            phrase_matches = sum(1 for phrase in prediction_phrases if phrase in doc_content)
            phrase_score = phrase_matches / len(prediction_phrases)
        
        # 최종 점수 계산 (단어 40%, 구문 60%)
        final_score = 0.4 * word_score + 0.6 * phrase_score
        
        return min(1.0, final_score)
    
    def _extract_phrases(self, text: str) -> List[str]:
        """텍스트에서 의미 있는 구문을 추출합니다."""
        words = text.split()
        phrases = []
        
        # 2단어 구문 추출
        if len(words) >= 2:
            phrases.extend([" ".join(words[i:i+2]) for i in range(len(words)-1)])
        
        # 3단어 구문 추출 (있는 경우)
        if len(words) >= 3:
            phrases.extend([" ".join(words[i:i+3]) for i in range(len(words)-2)])
            
        return phrases

class LangSmithEvaluator:
    """LangSmith를 사용한 RAG 시스템 평가 클래스"""
    
    def __init__(
        self,
        project_name: str,
        api_key: Optional[str] = None,
        llm: Optional[BaseLanguageModel] = None,
        evaluators: Optional[List[str]] = None
    ):
        """
        LangSmith 평가기 초기화
        
        Args:
            project_name (str): 프로젝트 이름 (LangSmith에서 사용)
            api_key (Optional[str]): LangSmith API 키
            llm (Optional[BaseLanguageModel]): 평가에 사용할 LLM
            evaluators (Optional[List[str]]): 사용할 내장 평가기 리스트
        """
        self.api_key = api_key or LANGSMITH_API_KEY
        os.environ["LANGCHAIN_API_KEY"] = self.api_key
        
        self.project_name = f"{LANGSMITH_PROJECT_PREFIX}_{project_name}"
        self.client = Client(api_key=self.api_key)
        
        # 사용할 평가기 목록 (LangSmith 내장 평가기)
        self.evaluators = evaluators or [
            "correctness",
            "relevance",
            "helpfulness",
            "faithfulness",
            "context_precision",
            "context_recall"
        ]
        
        # 평가기 초기화
        self._init_evaluators(llm)
        
        # 결과 저장 위치
        self.results_dir = Path(RESULTS_DIR)
        self.results_dir.mkdir(exist_ok=True, parents=True)

    def _init_evaluators(self, llm: Optional[BaseLanguageModel] = None):
        """평가기 초기화"""
        # 사용자 정의 평가기 초기화
        self.evaluator_instances = {
            "correctness": CorrectnessEvaluator(),
            "relevance": RelevanceEvaluator(llm=llm),
            "faithfulness": FaithfulnessEvaluator(llm=llm)
        }
        
    def setup_dataset(
        self, 
        examples: List[RAGEvaluationExample],
        dataset_name: Optional[str] = None
    ) -> str:
        """
        LangSmith에 데이터셋 설정
        
        Args:
            examples (List[RAGEvaluationExample]): 평가 예제 리스트
            dataset_name (Optional[str]): 데이터셋 이름
            
        Returns:
            str: 생성된 데이터셋 ID
        """
        dataset_name = dataset_name or f"{self.project_name}_dataset_{int(time.time())}"
        
        # 이미 데이터셋이 있는지 확인
        datasets = self.client.list_datasets()
        existing_dataset = next((ds for ds in datasets if ds.name == dataset_name), None)
        
        if existing_dataset:
            return existing_dataset.id
        
        # 데이터셋 생성
        langsmith_examples = []
        for example in examples:
            # 메타데이터에 문서 ID와 경로 매핑 정보 추가
            # expected_sources에 있는 ID들은 청크 ID (doc_15_0)이고,
            # 검색 결과에서 나오는 ID들은 실제 파일 경로인 경우 처리
            metadata = example.metadata or {}
            
            # ID-경로 매핑 사전을 메타데이터에 추가
            if not metadata.get("source_id_to_path"):
                source_id_to_path = {}
                
                # 검색된 문서에서 메타데이터를 추출하여 매핑 정보 생성
                if hasattr(example, "retrieved_documents_raw") and example.retrieved_documents_raw:
                    for doc in example.retrieved_documents_raw:
                        if hasattr(doc, "metadata") and isinstance(doc.metadata, dict):
                            source = doc.metadata.get("source")
                            doc_id = doc.metadata.get("id")
                            
                            if source and doc_id:
                                source_id_to_path[doc_id] = source
                            
                            # 대체 필드 확인
                            if not source:
                                for key in ["path", "file_path", "filename", "source_path"]:
                                    if key in doc.metadata:
                                        source = doc.metadata[key]
                                        if source:
                                            # doc_id는 metadata에서 직접 찾거나, 파일명에서 ID 형식으로 추출
                                            if not doc_id:
                                                # 파일명에서 추출 시도
                                                import os
                                                try:
                                                    basename = os.path.basename(source)
                                                    # PDF 페이지 번호 등으로 ID 생성을 시도
                                                    if "page" in doc.metadata:
                                                        page = doc.metadata["page"]
                                                        doc_id = f"doc_{page}_0"  # 청크 인덱스는 0으로 가정
                                                        source_id_to_path[doc_id] = source
                                                except:
                                                    pass
                
                # 메타데이터에 매핑 정보 추가
                if source_id_to_path:
                    metadata["source_id_to_path"] = source_id_to_path
                    print(f"[setup_dataset] ID-경로 매핑 정보 추가: {source_id_to_path}")
            
            # example의 메타데이터 업데이트
            example.metadata = metadata
            
            # LangSmith Example 형식으로 변환
            langsmith_example = Example(
                id=uuid.uuid4(),
                inputs={
                    "query": example.query,
                    "retrieved_documents": example.retrieved_documents
                },
                outputs={
                    "ground_truth": example.ground_truth,
                    "expected_sources": example.expected_sources,
                    "generated_response": example.generated_response or ""
                },
                metadata=example.metadata
            )
            langsmith_examples.append(langsmith_example)
        
        # LangSmith에 데이터셋 생성
        dataset = self.client.create_dataset(dataset_name=dataset_name)
        
        # 예제 추가
        for example in langsmith_examples:
            self.client.create_example(
                inputs=example.inputs,
                outputs=example.outputs,
                dataset_id=dataset.id,
                metadata=example.metadata
            )
        
        print(f"LangSmith 데이터셋 생성됨: {dataset_name} (ID: {dataset.id})")
        return dataset.id
    
    def evaluate_retrieval(
        self,
        retriever,
        dataset_id: str,
        retriever_name: str = "test_retriever",
        trace_project: str = "retrieval_evaluation",
        original_dataset_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        검색기의 성능을 평가합니다.
        
        Args:
            retriever: 평가할 검색기
            dataset_id (str): 평가할 데이터셋 ID
            retriever_name (str): 검색기 이름
            trace_project (str): 추적을 위한 프로젝트 이름
            original_dataset_path (Optional[str]): 원본 데이터셋 경로 (옵션)
            
        Returns:
            Dict[str, Any]: 평가 결과 요약
        """
        print(f"[evaluate_retrieval] 검색기 평가 시작: {retriever_name}")
        print(f"[evaluate_retrieval] 데이터셋 ID: {dataset_id}")
        
        examples = list(self.client.list_examples(dataset_id=dataset_id))
        print(f"[evaluate_retrieval] 평가할 예제 수: {len(examples)}")
        
        # 결과를 저장할 리스트 초기화
        all_results = []
        precision_scores = []
        recall_scores = []
        
        # 결과 저장을 위한 디렉토리 설정
        timestamp = int(time.time())
        results_filename = f"retrieval_evaluation_{retriever_name}_{timestamp}.json"
        results_file = self.results_dir / results_filename
        
        # 원본 데이터셋에서 직접 소스 ID-경로 매핑 정보 로드
        global_source_id_to_path = {}
        if original_dataset_path:
            try:
                import sys
                import os
                sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from generator.dataset_generator import load_dataset
                
                print(f"[evaluate_retrieval] 원본 데이터셋에서 소스 ID-경로 매핑 정보 로드 중: {original_dataset_path}")
                dataset = load_dataset(original_dataset_path)
                
                # 소스 ID와 파일 경로 매핑 생성
                for doc in dataset.documents:
                    doc_id = doc.get("id")
                    source = doc.get("metadata", {}).get("source")
                    if doc_id and source:
                        global_source_id_to_path[doc_id] = source
                
                print(f"[evaluate_retrieval] 로드된 소스 ID-경로 매핑 정보: {global_source_id_to_path}")
            except Exception as e:
                print(f"[evaluate_retrieval] 원본 데이터셋 로드 중 오류: {e}")
        
        for i, example in enumerate(examples):
            query = example.inputs["query"]
            expected_sources = example.outputs.get("expected_sources", [])
            
            # 메타데이터에서 소스 ID-경로 매핑 정보 확인
            source_id_to_path = {}
            example_metadata = getattr(example, "metadata", {}) or {}
            
            # 메타데이터 출력하여 디버깅
            print(f"[evaluate_retrieval] 예제 메타데이터: {example_metadata}")
            
            if isinstance(example_metadata, dict) and "source_id_to_path" in example_metadata:
                source_id_to_path = example_metadata["source_id_to_path"]
                print(f"[evaluate_retrieval] 예제에서 ID-경로 매핑 발견: {source_id_to_path}")
            
            # 글로벌 매핑 정보가 있으면 그것도 사용
            if global_source_id_to_path:
                source_id_to_path.update(global_source_id_to_path)
                print(f"[evaluate_retrieval] 글로벌 매핑 정보 추가됨")
            
            print(f"[evaluate_retrieval] 예제 {i+1}/{len(examples)} 평가 중...")
            print(f"[evaluate_retrieval] 쿼리: {query}")
            
            try:
                # 검색 수행
                retrieved_docs = retriever.get_relevant_documents(query)
                retrieved_docs_info = [
                    {
                        "page_content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                        "metadata": doc.metadata
                    }
                    for doc in retrieved_docs
                ]
                
                # LangSmith에 실행 기록 (API 호출의 최소화를 위해 필요한 경우만 수행)
                run_id = str(uuid.uuid4())
                if trace_project and self.client:
                    try:
                        self.client.create_run(
                            project_name=trace_project,
                            name=f"retrieval_{retriever_name}",
                            run_id=run_id,
                            run_type="retriever",
                            inputs={"query": query},
                            outputs={"retrieved_documents": retrieved_docs_info},
                            metadata={
                                "expected_sources": expected_sources,
                                "source_id_to_path": source_id_to_path
                            }
                        )
                    except Exception as e:
                        print(f"[evaluate_retrieval] LangSmith 실행 기록 오류: {e}")
                
                # 변환된 예상 소스 ID
                transformed_expected_sources = []
                for source_id in expected_sources:
                    if source_id in source_id_to_path:
                        # 매핑 정보를 사용하여 변환
                        transformed_source = source_id_to_path[source_id]
                        transformed_expected_sources.append(transformed_source)
                        print(f"[evaluate_retrieval] 소스 ID '{source_id}'를 경로 '{transformed_source}'로 변환")
                
                # 변환된 소스 사용 (있는 경우)
                evaluation_expected_sources = transformed_expected_sources if transformed_expected_sources else expected_sources
                print(f"[evaluate_retrieval] 평가에 사용할 최종 예상 소스: {evaluation_expected_sources}")
                
                # 정밀도 및 재현율 계산
                precision, recall, retrieved_sources, additional_metrics = self._calculate_precision_recall(
                    retrieved_docs, evaluation_expected_sources, example
                )
                
                # 결과 저장
                result = {
                    "query": query,
                    "retrieved_documents": retrieved_docs_info,
                    "expected_sources": expected_sources,
                    "retrieved_sources": retrieved_sources,
                    "precision": precision,
                    "recall": recall,
                    "f1": self._calculate_f1(precision, recall),
                    "run_id": run_id,
                    # 추가 지표 포함
                    "mrr": additional_metrics.get("mrr", 0.0),
                    "hit_at_1": additional_metrics.get("hit_at_1", 0.0),
                    "hit_at_3": additional_metrics.get("hit_at_3", 0.0),
                    "hit_at_5": additional_metrics.get("hit_at_5", 0.0),
                    "ndcg_at_3": additional_metrics.get("ndcg_at_3", 0.0),
                    "ndcg_at_5": additional_metrics.get("ndcg_at_5", 0.0)
                }
                all_results.append(result)
                
                # 정밀도 및 재현율 점수 저장
                precision_scores.append(precision)
                recall_scores.append(recall)
                
                print(f"[evaluate_retrieval] 정밀도: {precision:.2f}, 재현율: {recall:.2f}")
                
                # 중간 결과 저장 (주기적으로)
                if (i + 1) % 10 == 0 or (i + 1) == len(examples):
                    # 중간 요약 생성
                    current_avg_precision = sum(precision_scores) / len(precision_scores) if precision_scores else 0
                    current_avg_recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0
                    
                    interim_summary = {
                        "retriever_name": retriever_name,
                        "dataset_id": dataset_id,
                        "examples_processed": i + 1,
                        "total_examples": len(examples),
                        "current_avg_precision": current_avg_precision,
                        "current_avg_recall": current_avg_recall,
                        "results": all_results
                    }
                    
                    with open(results_file, "w", encoding="utf-8") as f:
                        json.dump(interim_summary, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
                    
                    print(f"[evaluate_retrieval] 중간 결과 저장됨 ({i+1}/{len(examples)}): {results_file}")
                
            except Exception as e:
                print(f"[evaluate_retrieval] 예제 평가 중 오류 발생: {str(e)}")
                # 오류 정보 기록하고 다음 예제로 진행
                result = {
                    "query": query,
                    "expected_sources": expected_sources,
                    "error": str(e),
                    "precision": 0.0,
                    "recall": 0.0
                }
                all_results.append(result)
                precision_scores.append(0.0)
                recall_scores.append(0.0)
        
        # 최종 요약 계산
        avg_precision = sum(precision_scores) / len(precision_scores) if precision_scores else 0
        avg_recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0
        f1_score = self._calculate_f1(avg_precision, avg_recall)
        
        # 추가 지표 평균 계산
        mrr_scores = [result.get("mrr", 0.0) for result in all_results if "mrr" in result]
        hit_at_1_scores = [result.get("hit_at_1", 0.0) for result in all_results if "hit_at_1" in result]
        hit_at_3_scores = [result.get("hit_at_3", 0.0) for result in all_results if "hit_at_3" in result]
        hit_at_5_scores = [result.get("hit_at_5", 0.0) for result in all_results if "hit_at_5" in result]
        ndcg_at_3_scores = [result.get("ndcg_at_3", 0.0) for result in all_results if "ndcg_at_3" in result]
        ndcg_at_5_scores = [result.get("ndcg_at_5", 0.0) for result in all_results if "ndcg_at_5" in result]
        
        avg_mrr = sum(mrr_scores) / len(mrr_scores) if mrr_scores else 0.0
        avg_hit_at_1 = sum(hit_at_1_scores) / len(hit_at_1_scores) if hit_at_1_scores else 0.0
        avg_hit_at_3 = sum(hit_at_3_scores) / len(hit_at_3_scores) if hit_at_3_scores else 0.0
        avg_hit_at_5 = sum(hit_at_5_scores) / len(hit_at_5_scores) if hit_at_5_scores else 0.0
        avg_ndcg_at_3 = sum(ndcg_at_3_scores) / len(ndcg_at_3_scores) if ndcg_at_3_scores else 0.0
        avg_ndcg_at_5 = sum(ndcg_at_5_scores) / len(ndcg_at_5_scores) if ndcg_at_5_scores else 0.0
        
        summary = {
            "retriever_name": retriever_name,
            "dataset_id": dataset_id,
            "timestamp": timestamp,
            "num_examples": len(examples),
            "avg_precision": avg_precision,
            "avg_recall": avg_recall,
            "f1_score": f1_score,
            "avg_mrr": avg_mrr,
            "avg_hit_at_1": avg_hit_at_1,
            "avg_hit_at_3": avg_hit_at_3,
            "avg_hit_at_5": avg_hit_at_5,
            "avg_ndcg_at_3": avg_ndcg_at_3,
            "avg_ndcg_at_5": avg_ndcg_at_5,
            "results_file": str(results_file)
        }
        
        # 최종 결과 저장
        final_result = {
            "summary": summary,
            "results": all_results
        }
        
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(final_result, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
        
        print(f"[evaluate_retrieval] 평가 완료")
        print(f"[evaluate_retrieval] 평균 정밀도: {avg_precision:.4f}")
        print(f"[evaluate_retrieval] 평균 재현율: {avg_recall:.4f}")
        print(f"[evaluate_retrieval] F1 점수: {f1_score:.4f}")
        print(f"[evaluate_retrieval] MRR: {avg_mrr:.4f}")
        print(f"[evaluate_retrieval] Hit@1: {avg_hit_at_1:.4f}")
        print(f"[evaluate_retrieval] Hit@3: {avg_hit_at_3:.4f}")
        print(f"[evaluate_retrieval] Hit@5: {avg_hit_at_5:.4f}")
        print(f"[evaluate_retrieval] NDCG@3: {avg_ndcg_at_3:.4f}")
        print(f"[evaluate_retrieval] NDCG@5: {avg_ndcg_at_5:.4f}")
        print(f"[evaluate_retrieval] 결과 저장됨: {results_file}")
        
        return summary
    
    def evaluate_generation(
        self,
        dataset_id: str,
        generation_model_name: str,
        generation_fn: Callable[[str, List[str]], str],
        retriever_fn: Optional[Callable[[str], List[str]]] = None
    ) -> Dict[str, Any]:
        """
        생성 모델의 성능을 평가합니다.
        
        Args:
            dataset_id (str): 평가할 데이터셋 ID
            generation_model_name (str): 생성 모델 이름
            generation_fn (Callable): 쿼리와 검색된 문서를 받아 응답을 생성하는 함수
            retriever_fn (Optional[Callable]): 쿼리를 받아 관련 문서를 반환하는 함수
            
        Returns:
            Dict[str, Any]: 평가 결과
        """
        print(f"[evaluate_generation] 생성 모델 평가 시작: {generation_model_name}")
        
        examples = list(self.client.list_examples(dataset_id=dataset_id))
        print(f"[evaluate_generation] 평가할 예제 수: {len(examples)}")
        
        all_scores = {
            "correctness": [],
            "relevance": [],
            "faithfulness": []
        }
        
        # 평가기 인스턴스 사용
        correctness_evaluator = self.evaluator_instances.get("correctness") or CorrectnessEvaluator()
        relevance_evaluator = self.evaluator_instances.get("relevance") or RelevanceEvaluator()
        faithfulness_evaluator = self.evaluator_instances.get("faithfulness") or FaithfulnessEvaluator()
        
        for i, example in enumerate(examples):
            query = example.inputs["query"]
            expected_ground_truth = example.outputs.get("ground_truth", "")
            
            print(f"[evaluate_generation] 예제 {i+1}/{len(examples)} 평가 중...")
            print(f"[evaluate_generation] 쿼리: {query}")
            
            # 관련 문서 가져오기
            if retriever_fn:
                retrieved_docs = retriever_fn(query)
            else:
                retrieved_docs = example.inputs.get("retrieved_documents", [])
                
            # 응답 생성
            try:
                generated_response = generation_fn(query, retrieved_docs)
                
                # 현재 시간 가져오기
                current_time = datetime.utcnow()
                
                # 실행 결과 구성
                run_data = Run(
                    id=str(uuid.uuid4()),
                    name=f"generation_evaluation",
                    run_type=RunTypeEnum.llm,
                    inputs={
                        "query": query,
                        "retrieved_documents": retrieved_docs
                    },
                    outputs={
                        "output": generated_response
                    },
                    reference_example_id=example.id,
                    start_time=current_time,  # 시작 시간 추가
                    end_time=current_time     # 종료 시간 추가 (간단히 동일한 시간 사용)
                )
                
                # 직접 평가 수행
                correctness_result = correctness_evaluator.evaluate_run(run_data, example)
                relevance_result = relevance_evaluator.evaluate_run(run_data, example)
                faithfulness_result = faithfulness_evaluator.evaluate_run(run_data, example)
                
                # 결과 저장
                all_scores["correctness"].append(correctness_result.score)
                all_scores["relevance"].append(relevance_result.score)
                all_scores["faithfulness"].append(faithfulness_result.score)
                
                print(f"[evaluate_generation] 평가 완료: correctness={correctness_result.score:.2f}, relevance={relevance_result.score:.2f}, faithfulness={faithfulness_result.score:.2f}")
                
            except Exception as e:
                print(f"[evaluate_generation] 평가 중 오류 발생: {e}")
                all_scores["correctness"].append(0.0)
                all_scores["relevance"].append(0.0)
                all_scores["faithfulness"].append(0.0)
        
        # 평균 점수 계산
        summary = {
            "avg_correctness": np.mean(all_scores["correctness"]),
            "avg_relevance": np.mean(all_scores["relevance"]),
            "avg_faithfulness": np.mean(all_scores["faithfulness"]),
            "sample_count": len(examples)
        }
        
        # 결과 저장
        timestamp = int(time.time())
        results_file = self.results_dir / f"generation_evaluation_{generation_model_name}_{timestamp}.json"
        
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump({
                "model": generation_model_name,
                "dataset_id": dataset_id,
                "timestamp": timestamp,
                "summary": summary,
                "scores": all_scores
            }, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
        
        print(f"[evaluate_generation] 평가 결과 저장됨: {results_file}")
        print(f"[evaluate_generation] 평가 요약:")
        for k, v in summary.items():
            print(f"  {k}: {v}")
        
        return {
            "summary": summary,
            "scores": all_scores,
            "results_file": str(results_file)
        }
    
    def evaluate_robustness(
        self,
        dataset_id: str,
        retriever_name: str,
        generation_model_name: str,
        retriever_fn: Callable[[str], List[str]],
        generation_fn: Callable[[str, List[str]], str],
        query_variations_fn: Callable[[str], List[str]]
    ) -> Dict[str, Any]:
        """
        RAG 시스템의 견고성을 평가합니다. 다양한 쿼리 변형에 대한 일관성을 측정합니다.
        
        Args:
            dataset_id (str): 평가할 데이터셋 ID
            retriever_name (str): 검색기 이름
            generation_model_name (str): 생성 모델 이름
            retriever_fn (Callable): 쿼리를 받아 관련 문서를 반환하는 함수
            generation_fn (Callable): 쿼리와 검색된 문서를 받아 응답을 생성하는 함수
            query_variations_fn (Callable): 쿼리 변형 생성 함수
            
        Returns:
            Dict[str, Any]: 평가 결과 요약
        """
        print(f"[evaluate_robustness] 강건성 평가 시작: {generation_model_name} / {retriever_name}")
        print(f"[evaluate_robustness] 데이터셋 ID: {dataset_id}")
        
        # 데이터셋에서 예제 가져오기
        examples = list(self.client.list_examples(dataset_id=dataset_id))
        print(f"[evaluate_robustness] 평가할 예제 수: {len(examples)}")
        
        # 결과 저장을 위한 리스트 초기화
        all_results = []
        consistency_scores = []
        
        # 결과 저장을 위한 디렉토리 설정
        timestamp = int(time.time())
        results_filename = f"robustness_evaluation_{retriever_name}_{generation_model_name}_{timestamp}.json"
        results_file = self.results_dir / results_filename
        
        # 각 예제에 대한 평가 수행
        for i, example in enumerate(examples):
            print(f"[evaluate_robustness] 예제 {i+1}/{len(examples)} 평가 중...")
            
            # 원본 쿼리 가져오기
            original_query = example.inputs["query"]
            print(f"[evaluate_robustness] 원본 쿼리: {original_query}")
            
            # 쿼리 변형 생성
            variations = query_variations_fn(original_query)
            print(f"[evaluate_robustness] 생성된 변형 수: {len(variations)}")
            
            if not variations:
                print(f"[evaluate_robustness] 변형이 생성되지 않았습니다. 다음 예제로 넘어갑니다.")
                continue
            
            # 모든 쿼리(원본 + 변형)에 대한 응답 생성
            all_queries = [original_query] + variations
            responses = []
            retrieved_docs_list = []
            
            for j, query in enumerate(all_queries):
                print(f"[evaluate_robustness] 쿼리 {j+1}/{len(all_queries)} 처리 중: {query}")
                
                # 문서 검색
                retrieved_docs = retriever_fn(query)
                retrieved_docs_list.append(retrieved_docs)
                
                # 문서가 검색되지 않은 경우
                if not retrieved_docs:
                    print(f"[evaluate_robustness] 문서가 검색되지 않았습니다.")
                    responses.append("")
                    continue
                
                # 응답 생성
                try:
                    response = generation_fn(query, retrieved_docs)
                    responses.append(response)
                    print(f"[evaluate_robustness] 응답 생성 성공: {response[:100]}...")
                except Exception as e:
                    print(f"[evaluate_robustness] 응답 생성 실패: {e}")
                    responses.append("")
            
            # 응답이 없는 경우
            if not any(responses):
                print(f"[evaluate_robustness] 모든 응답 생성에 실패했습니다. 다음 예제로 넘어갑니다.")
                continue
            
            # 일관성 점수 계산
            original_response = responses[0]
            consistency_results = []
            
            for j, (query, response) in enumerate(zip(all_queries[1:], responses[1:])):
                if not response:
                    continue
                
                # 응답 간 유사도 계산
                similarity = self._calculate_response_similarity(original_response, response)
                
                # 검색된 문서 간 유사도 계산
                doc_similarity = self._calculate_retrieved_docs_similarity(
                    retrieved_docs_list[0], retrieved_docs_list[j+1]
                )
                
                consistency_results.append({
                    "variation": query,
                    "response": response,
                    "response_similarity": similarity,
                    "doc_similarity": doc_similarity
                })
                
                print(f"[evaluate_robustness] 변형 {j+1} 일관성: {similarity:.4f}, 문서 유사도: {doc_similarity:.4f}")
            
            # 평균 일관성 점수 계산
            if consistency_results:
                avg_consistency = sum(r["response_similarity"] for r in consistency_results) / len(consistency_results)
                avg_doc_similarity = sum(r["doc_similarity"] for r in consistency_results) / len(consistency_results)
            else:
                avg_consistency = 0.0
                avg_doc_similarity = 0.0
            
            consistency_scores.append(avg_consistency)
            
            # 결과 저장
            result = {
                "original_query": original_query,
                "original_response": original_response,
                "variations": [all_queries[j+1] for j in range(len(consistency_results))],
                "variation_responses": [r["response"] for r in consistency_results],
                "consistency_results": consistency_results,
                "avg_consistency": avg_consistency,
                "avg_doc_similarity": avg_doc_similarity
            }
            all_results.append(result)
            
            print(f"[evaluate_robustness] 예제 {i+1} 평균 일관성: {avg_consistency:.4f}, 문서 유사도: {avg_doc_similarity:.4f}")
        
        # 요약 통계 계산
        if consistency_scores:
            avg_consistency = sum(consistency_scores) / len(consistency_scores)
            min_consistency = min(consistency_scores)
            max_consistency = max(consistency_scores)
        else:
            avg_consistency = 0.0
            min_consistency = 0.0
            max_consistency = 0.0
        
        summary = {
            "retriever_name": retriever_name,
            "generation_model_name": generation_model_name,
            "num_examples": len(examples),
            "avg_consistency": avg_consistency,
            "min_consistency": min_consistency,
            "max_consistency": max_consistency,
            "timestamp": timestamp
        }
        
        # 결과 저장
        results = {
            "summary": summary,
            "results": all_results
        }
        
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"[evaluate_robustness] 강건성 평가 완료: {avg_consistency:.4f}")
        print(f"[evaluate_robustness] 결과 저장됨: {results_file}")
        
        return {
            "summary": summary,
            "results": all_results,
            "results_file": str(results_file)
        }
    
    @staticmethod
    def _calculate_f1(precision: float, recall: float) -> float:
        """F1 점수를 계산합니다."""
        return (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
    def _calculate_response_similarity(self, response1: str, response2: str) -> float:
        """두 응답 간의 의미적 유사도를 계산합니다."""
        try:
            # 임베딩 유사도 계산 (코사인 유사도)
            if self.embedding_model:
                embedding1 = self.embedding_model.embed_query(response1)
                embedding2 = self.embedding_model.embed_query(response2)
                
                # 코사인 유사도 계산
                dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
                norm1 = math.sqrt(sum(a * a for a in embedding1))
                norm2 = math.sqrt(sum(b * b for b in embedding2))
                
                if norm1 > 0 and norm2 > 0:
                    cosine_similarity = dot_product / (norm1 * norm2)
                    return max(0.0, min(1.0, cosine_similarity))  # 0~1 범위로 제한
            
            # 임베딩 모델이 없거나 실패한 경우 텍스트 기반 유사도 계산
            return self._calculate_text_similarity(response1, response2)
            
        except Exception as e:
            print(f"[_calculate_response_similarity] 유사도 계산 오류: {e}")
            return self._calculate_text_similarity(response1, response2)
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """텍스트 기반 유사도 계산 (단어 중복 비율)"""
        if not text1 or not text2:
            return 0.0
            
        # 단어 집합 생성
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        # 자카드 유사도 계산
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_retrieved_docs_similarity(self, docs1: List, docs2: List) -> float:
        """두 검색 결과 집합 간의 유사도를 계산합니다."""
        if not docs1 or not docs2:
            return 0.0
            
        # 소스 정보 추출
        sources1 = set()
        sources2 = set()
        
        for doc in docs1:
            if hasattr(doc, 'metadata') and 'source' in doc.metadata:
                sources1.add(doc.metadata['source'])
        
        for doc in docs2:
            if hasattr(doc, 'metadata') and 'source' in doc.metadata:
                sources2.add(doc.metadata['source'])
        
        # 자카드 유사도 계산 (소스 기준)
        if sources1 and sources2:
            intersection = len(sources1.intersection(sources2))
            union = len(sources1.union(sources2))
            return intersection / union
            
        # 소스 정보가 없는 경우 콘텐츠 기반 유사도 계산
        content_similarities = []
        
        for doc1 in docs1:
            for doc2 in docs2:
                content1 = doc1.page_content if hasattr(doc1, 'page_content') else str(doc1)
                content2 = doc2.page_content if hasattr(doc2, 'page_content') else str(doc2)
                similarity = self._calculate_text_similarity(content1, content2)
                content_similarities.append(similarity)
        
        # 최대 유사도 반환
        return max(content_similarities) if content_similarities else 0.0
        
    def _calculate_precision_recall(self, retrieved_docs, expected_sources, example=None):
        """
        검색된 문서와 예상되는 소스 간의 정밀도와 재현율을 계산합니다.
        
        Args:
            retrieved_docs (List[Document]): 검색된 문서 목록
            expected_sources (List[str]): 예상되는 소스 ID 또는 경로 목록
            example: 평가 예제 (메타데이터 접근용, 선택 사항)
            
        Returns:
            Tuple[float, float, List[str], Dict]: 정밀도, 재현율, 검색된 소스 목록, 추가 지표
        """
        # 검색된 문서에서 소스(파일 경로) 정보 추출
        retrieved_sources = []
        for doc in retrieved_docs:
            if hasattr(doc, 'metadata') and 'source' in doc.metadata:
                source = doc.metadata['source']
                retrieved_sources.append(source)
                print(f"[_calculate_precision_recall] 문서 내용(일부): {doc.page_content[:150].replace(chr(10), ' ')}...")
        
        print(f"[_calculate_precision_recall] 검색된 문서 수: {len(retrieved_docs)}")
        print(f"[_calculate_precision_recall] 예상 소스 수: {len(expected_sources)}")
        print(f"[_calculate_precision_recall] 추출된 소스 목록: {retrieved_sources}")
        print(f"[_calculate_precision_recall] 예상 소스 목록: {expected_sources}")
        
        # 예상 소스가 실제 파일 경로가 아닌 ID 형태인 경우 변환 시도
        final_expected_sources = expected_sources
        source_id_to_path = {}
        
        # 메타데이터에서 소스 ID-경로 매핑 정보 확인
        if example and hasattr(example, 'metadata') and example.metadata:
            if isinstance(example.metadata, dict) and "source_id_to_path" in example.metadata:
                source_id_to_path = example.metadata["source_id_to_path"]
                print(f"[_calculate_precision_recall] 예제에서 ID-경로 매핑 발견: {source_id_to_path}")
                
                # 소스 ID를 경로로 변환
                transformed_expected_sources = []
                for source_id in expected_sources:
                    if source_id in source_id_to_path:
                        transformed_source = source_id_to_path[source_id]
                        transformed_expected_sources.append(transformed_source)
                        print(f"[_calculate_precision_recall] 소스 ID '{source_id}'를 경로 '{transformed_source}'로 변환")
                    else:
                        transformed_expected_sources.append(source_id)  # 변환할 수 없는 경우 원래 값 유지
                
                if transformed_expected_sources:
                    final_expected_sources = transformed_expected_sources
        
        print(f"[_calculate_precision_recall] 변환된 예상 소스: {final_expected_sources}")
        
        # 정규화 함수 정의
        def normalize_doc_id(doc_id):
            """문서 ID를 다양한 형태로 정규화합니다."""
            normalized = [doc_id]  # 원래 형태 포함
            
            # 파일 경로인 경우 처리
            if isinstance(doc_id, str) and ('\\' in doc_id or '/' in doc_id):
                # 백슬래시를 슬래시로 변환 (일관성 유지)
                normalized_path = doc_id.replace('\\', '/')
                normalized.append(normalized_path)
                
                # 경로에서 파일 이름만 추출
                file_name = os.path.basename(doc_id)
                normalized.append(file_name)
                
                # 확장자 제거
                name_without_ext = os.path.splitext(file_name)[0]
                normalized.append(name_without_ext)
                
                # 파일 이름에서 숫자 추출
                parts = extract_filename_parts(file_name)
                if parts:
                    normalized.extend(parts)
            
            # ID 형식인 경우 처리 (doc_15_0 같은 형태)
            else:
                # 숫자 부분 추출 (doc_15_0 -> 15_0)
                doc_number = extract_doc_number(doc_id)
                if doc_number:
                    normalized.append(doc_number)
                    parts = doc_number.split('_')
                    if len(parts) > 0:
                        normalized.append(parts[0])  # 첫 번째 숫자만 (15_0 -> 15)
                
                # 다양한 형식 추가
                if doc_id.startswith('doc_'):
                    suffix = doc_id[4:]  # doc_ 이후 부분
                    normalized.append(suffix)
                    normalized.append(f"document_{suffix}")
                    normalized.append(f"doc{suffix}")  # underscore 제거
                elif doc_id.startswith('document_'):
                    suffix = doc_id[9:]  # document_ 이후 부분
                    normalized.append(suffix)
                    normalized.append(f"doc_{suffix}")
                    if '_' in suffix:
                        clean_suffix = suffix.replace('_', '')
                        normalized.append(f"doc{clean_suffix}")
            
            return normalized
        
        # 모든 검색된 소스와 예상 소스 정규화
        all_retrieved_forms = []
        for source in retrieved_sources:
            source_forms = normalize_doc_id(source)
            all_retrieved_forms.extend(source_forms)
        
        all_expected_forms = []
        for source in final_expected_sources:
            source_forms = normalize_doc_id(source)
            all_expected_forms.extend(source_forms)
        
        print(f"[_calculate_precision_recall] 정규화된 검색 소스: {retrieved_sources}")
        print(f"[_calculate_precision_recall] 정규화된 예상 소스: {final_expected_sources}")
        
        # 관련 소스 계산 (검색된 소스와 예상 소스 간의 교집합)
        relevant_sources = 0
        relevant_indices = []  # 관련 문서의 인덱스 저장
        
        for expected_form in all_expected_forms:
            for i, retrieved_source in enumerate(retrieved_sources):
                retrieved_forms = normalize_doc_id(retrieved_source)
                if expected_form in retrieved_forms:
                    relevant_sources += 1
                    relevant_indices.append(i)
                    print(f"[_calculate_precision_recall] 매치 발견: {expected_form} ↔ {retrieved_source} (인덱스: {i})")
                    break  # 동일한 소스를 중복 계산하지 않음
        
        print(f"[_calculate_precision_recall] 관련 소스 수: {relevant_sources}")
        
        # 기본 지표 계산
        # 정밀도 = 관련 소스 / 검색된 소스
        precision = relevant_sources / len(retrieved_sources) if retrieved_sources else 0
        
        # 재현율 = 관련 소스 / 예상 소스
        recall = relevant_sources / len(final_expected_sources) if final_expected_sources else 1.0
        
        # 추가 지표 계산
        additional_metrics = {}
        
        # MRR (Mean Reciprocal Rank) 계산
        if relevant_indices:
            # 첫 번째로 관련있는 문서의 순위의 역수
            first_relevant_idx = min(relevant_indices)
            mrr = 1.0 / (first_relevant_idx + 1)  # 0-indexed → 1-indexed
            additional_metrics["mrr"] = mrr
            print(f"[_calculate_precision_recall] MRR: {mrr:.4f} (첫 번째 관련 문서 위치: {first_relevant_idx+1})")
        else:
            additional_metrics["mrr"] = 0.0
            print(f"[_calculate_precision_recall] MRR: 0.0000 (관련 문서 없음)")
        
        # Hit@k 계산 (k=1,3,5)
        for k in [1, 3, 5]:
            if k > len(retrieved_sources):
                continue
                
            # 상위 k개 문서 중에 관련 문서가 있는지 확인
            hit_at_k = any(idx < k for idx in relevant_indices)
            additional_metrics[f"hit_at_{k}"] = 1.0 if hit_at_k else 0.0
            print(f"[_calculate_precision_recall] Hit@{k}: {1.0 if hit_at_k else 0.0}")
        
        # NDCG@k (Normalized Discounted Cumulative Gain) 계산
        # 순위를 고려한 지표로, 순위가 높은 관련 문서에 더 높은 가중치 부여
        for k in [3, 5]:
            if k > len(retrieved_sources):
                continue
                
            dcg = 0.0
            idcg = 0.0
            
            # DCG 계산
            for i in range(min(k, len(retrieved_sources))):
                if i in relevant_indices:
                    # log2(i+2)는 1부터 시작하는 인덱스 기준, i=0일 때 log2(2)=1
                    dcg += 1.0 / math.log2(i + 2)
            
            # IDCG 계산 (이상적인 경우)
            for i in range(min(k, len(relevant_indices))):
                idcg += 1.0 / math.log2(i + 2)
            
            # NDCG 계산
            ndcg = dcg / idcg if idcg > 0 else 0.0
            additional_metrics[f"ndcg_at_{k}"] = ndcg
            print(f"[_calculate_precision_recall] NDCG@{k}: {ndcg:.4f}")
        
        print(f"[_calculate_precision_recall] 계산된 정밀도: {precision:.2f}, 재현율: {recall:.2f}")
        print(f"[_calculate_precision_recall] 추가 지표: {additional_metrics}")
        
        return precision, recall, retrieved_sources, additional_metrics 