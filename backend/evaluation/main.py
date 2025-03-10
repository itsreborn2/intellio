"""
RAG 시스템 평가 메인 모듈
"""
import os
import argparse
import json
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import logging
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai import VertexAIEmbeddings
from common.app import LoadEnvGlobal
# 환경 변수 로드
LoadEnvGlobal()

os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
os.environ["LANGCHAIN_PROJECT"] = "evaluation_main"

from langsmith import Client
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# 평가 시스템 모듈 로드
from evaluation.config import (
    DOCS_DIR, DATASETS_DIR, RESULTS_DIR, EMBEDDING_MODELS, 
    DATASET_CONFIG, LANGSMITH_API_KEY, LANGSMITH_PROJECT_PREFIX
)
from evaluation.metrics.embedding_metrics import (
    evaluate_embedding_model, 
    evaluate_all_embedding_models
)
from evaluation.metrics.retrieval_metrics import (
    evaluate_retrieval_simple,
    evaluate_retrieval_advanced,
    evaluate_retrieval_robustness,
    save_retrieval_evaluation_results
)
from evaluation.metrics.generation_metrics import (
    evaluate_generation_comprehensive,
    save_generation_evaluation_results
)
from evaluation.generator.dataset_generator import (
    generate_predefined_datasets,
    load_dataset
)
from evaluation.generator.query_variations import (
    get_query_variations_generator
)
from evaluation.langsmith_eval.langsmith_evaluator import (
    LangSmithEvaluator
)
from evaluation.models import RAGEvaluationExample

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(RESULTS_DIR, "evaluation.log")),
        logging.StreamHandler()
    ]
)
from loguru import logger


class RAGEvaluator:
    """RAG 시스템 평가 클래스"""
    
    def __init__(
        self,
        docs_dir: Optional[Union[str, Path]] = None,
        datasets_dir: Optional[Union[str, Path]] = None,
        results_dir: Optional[Union[str, Path]] = None,
        use_langsmith: bool = True
    ):
        """
        RAG 평가 시스템 초기화
        
        Args:
            docs_dir (Optional[Union[str, Path]]): 문서 디렉토리 경로
            datasets_dir (Optional[Union[str, Path]]): 데이터셋 디렉토리 경로
            results_dir (Optional[Union[str, Path]]): 결과 저장 디렉토리 경로
            use_langsmith (bool): LangSmith 사용 여부
        """
        self.docs_dir = Path(docs_dir or DOCS_DIR)
        self.datasets_dir = Path(datasets_dir or DATASETS_DIR)
        self.results_dir = Path(results_dir or RESULTS_DIR)
        
        # 필요한 디렉토리 생성
        self.results_dir.mkdir(exist_ok=True, parents=True)
        self.datasets_dir.mkdir(exist_ok=True, parents=True)
        
        # 기본 LLM 설정
        #self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", temperature=0)

        # LangSmith 설정
        self.use_langsmith = use_langsmith and LANGSMITH_API_KEY
        if self.use_langsmith:
            self.langsmith_evaluator = LangSmithEvaluator(
                project_name="rag_evaluation",
                api_key=LANGSMITH_API_KEY,
                llm=self.llm
            )
        
        logger.info(f"RAG 평가 시스템 초기화 완료")
        logger.info(f"문서 디렉토리: {self.docs_dir}")
        logger.info(f"데이터셋 디렉토리: {self.datasets_dir}")
        logger.info(f"결과 디렉토리: {self.results_dir}")
        logger.info(f"LangSmith 사용: {self.use_langsmith}")
    
    def generate_datasets(self) -> List[str]:
        """
        평가 데이터셋을 생성합니다.
        
        Returns:
            List[str]: 생성된 데이터셋 경로 리스트
        """
        logger.info("평가 데이터셋 생성 시작")
        
        datasets = generate_predefined_datasets(llm=self.llm)
        
        dataset_paths = []
        for dataset in datasets:
            dataset_path = self.datasets_dir / f"{dataset.name}.json"
            dataset_paths.append(str(dataset_path))
            
            logger.info(f"데이터셋 생성: {dataset.name}, 쿼리 수: {len(dataset.queries)}")
        
        logger.info(f"데이터셋 생성 완료: {len(datasets)}개 데이터셋")
        
        return dataset_paths
    
    def prepare_langsmith_dataset(
        self,
        dataset_path: Union[str, Path],
        dataset_name: Optional[str] = None,
        api_key: Optional[str] = None,
        include_sources: bool = True,
        max_examples: Optional[int] = None
    ) -> str:
        """
        주어진 데이터셋을 LangSmith 데이터셋으로 준비합니다.
        
        Args:
            dataset_path (Union[str, Path]): 데이터셋 파일 경로
            dataset_name (Optional[str]): LangSmith에 생성할 데이터셋 이름 (기본값: 파일명)
            api_key (Optional[str]): LangSmith API 키
            include_sources (bool): RAG 검색 결과를 포함할지 여부
            max_examples (Optional[int]): 데이터셋에 포함할 최대 예제 수
        
        Returns:
            str: 생성된 LangSmith 데이터셋 ID
        """
        if not self.use_langsmith:
            logger.warning("LangSmith가 비활성화되어 있습니다.")
            return ""
        
        logger.info(f"LangSmith 데이터셋 준비: {dataset_path}")
        
        # 환경 설정
        if api_key:
            os.environ["LANGCHAIN_API_KEY"] = api_key
        
        # 데이터셋 로드
        dataset = load_dataset(dataset_path)
        
        # 기본 데이터셋 이름 설정
        if not dataset_name:
            dataset_name = os.path.splitext(os.path.basename(dataset_path))[0]
        
        # LangSmith 클라이언트 초기화
        client = Client()
        
        # 이미 존재하는 데이터셋 확인
        existing_datasets = client.list_datasets(dataset_name=dataset_name)
        existing_dataset = next(existing_datasets, None)
        
        if existing_dataset:
            logger.info(f"기존 데이터셋을 사용합니다: {dataset_name} (ID: {existing_dataset.id})")
            return existing_dataset.id
        
        # 관련 문서 검색 (데이터셋에 지정된 문서들)
        relevant_docs = {}
        source_id_to_path = {}  # 소스 ID와 파일 경로 간의 매핑
        
        if include_sources and dataset.documents:
            logger.info(f"관련 문서를 로드하는 중... (문서 수: {len(dataset.documents)})")
            for doc in dataset.documents:
                doc_id = doc.get("id")
                source = doc.get("metadata", {}).get("source")
                
                if doc_id and source and os.path.exists(source):
                    try:
                        with open(source, "r", encoding="utf-8") as f:
                            content = f.read()
                        relevant_docs[doc_id] = content
                        source_id_to_path[doc_id] = source  # 소스 ID와 경로 매핑 저장
                        logger.info(f"문서 로드 성공: {doc_id} -> {source}")
                    except Exception as e:
                        logger.error(f"문서 로드 실패: {doc_id} -> {source}, 오류: {e}")
        
        # LangSmith 데이터셋 예제 생성
        examples = []
        used_examples = 0
        
        logger.info("LangSmith 데이터셋 예제 생성 중...")
        for item in dataset.examples:
            query = item.get("query")
            ground_truth = item.get("ground_truth")
            retrieved_docs_ids = item.get("retrieved_documents", [])
            expected_sources = item.get("expected_sources", [])
            
            if not query or not ground_truth:
                continue
            
            # 관련 문서 내용 추출
            retrieved_documents = []
            for doc_id in retrieved_docs_ids:
                if doc_id in relevant_docs:
                    retrieved_documents.append(relevant_docs[doc_id])
            
            # 예제 생성
            example = RAGEvaluationExample(
                query=query,
                ground_truth=ground_truth,
                retrieved_documents=retrieved_documents,
                expected_sources=expected_sources,
                metadata={
                    "dataset_name": dataset_name,
                    "dataset_split": ["base"],
                    "source_id_to_path": source_id_to_path  # 매핑 정보 추가
                }
            )
            examples.append(example)
            
            used_examples += 1
            if max_examples and used_examples >= max_examples:
                break
        
        logger.info(f"데이터셋 예제 생성 완료: {len(examples)}개 예제")
        logger.info(f"소스 ID-경로 매핑: {source_id_to_path}")
        
        # LangSmith 데이터셋 생성
        dataset_id = client.create_dataset(
            dataset_name=dataset_name,
            description=f"RAG evaluation dataset created from {dataset_path}"
        )
        
        # 예제 추가
        for i, example in enumerate(examples):
            inputs = {"query": example.query}
            outputs = {
                "ground_truth": example.ground_truth,
                "retrieved_documents": example.retrieved_documents,
                "expected_sources": example.expected_sources
            }
            
            try:
                # 메타데이터에 소스 ID-경로 매핑 정보 추가
                example_metadata = example.metadata.copy() if example.metadata else {}
                example_metadata["source_id_to_path"] = source_id_to_path  # 매핑 정보 추가
                
                client.create_example(
                    inputs=inputs,
                    outputs=outputs,
                    dataset_id=dataset_id,
                    metadata=example_metadata
                )
                logger.info(f"예제 {i+1}/{len(examples)} 추가됨")
            except Exception as e:
                logger.error(f"예제 {i+1}/{len(examples)} 추가 실패: {e}")
        
        logger.info(f"LangSmith 데이터셋 생성 완료 - ID: {dataset_id}")
        return dataset_id
    
    def evaluate_embeddings(self, models: List[str] = None) -> Dict[str, Any]:
        """
        임베딩 모델을 평가합니다.
        
        Args:
            models (List[str]): 평가할 모델 이름 리스트
            
        Returns:
            Dict[str, Any]: 평가 결과
        """
        logger.info("임베딩 모델 평가 시작")
        
        if not models:
            models = list(EMBEDDING_MODELS.keys())
        
        embedding_models = {}
        for model_name in models:
            if model_name not in EMBEDDING_MODELS:
                logger.warning(f"알 수 없는 임베딩 모델: {model_name}")
                continue
                
            model_config = EMBEDDING_MODELS[model_name]
            model_type = model_config.get("type", "openai")
            
            logger.info(f"임베딩 모델 초기화: {model_name} ({model_type})")
            
            try:
                if model_type == "openai":
                    embedding_models[model_name] = OpenAIEmbeddings(
                        model=model_config.get("model_name", "text-embedding-3-small")
                    )
                elif model_type == "huggingface":
                    embedding_models[model_name] = HuggingFaceEmbeddings(
                        model_name=model_config.get("model_name", "all-MiniLM-L6-v2")
                    )
                elif model_type == "google":
                    project_id = os.getenv("GOOGLE_PROJECT_ID_VERTEXAI")
                    location = os.getenv("GOOGLE_LOCATION_VERTEXAI")
                    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_VERTEXAI")
                    embedding_models[model_name] = VertexAIEmbeddings(
                                                model=model_name,
                                                location=location,
                                                credentials=credentials_path)
                else:
                    logger.warning(f"지원되지 않는 임베딩 모델 유형: {model_type}")
                    continue
            except Exception as e:
                logger.error(f"임베딩 모델 초기화 중 오류 발생: {model_name}, 오류: {e}")
                continue
        
        # 임베딩 모델 평가
        results = evaluate_all_embedding_models(
            embedding_models=embedding_models,
            threshold_range=(0.5, 0.95, 0.05),
            results_dir=self.results_dir
        )
        
        logger.info(f"임베딩 모델 평가 완료: {len(embedding_models)}개 모델")
        
        return results
    
    def evaluate_retriever(
        self,
        retriever_name: str,
        retriever_fn,
        dataset_path: Union[str, Path],
        advanced: bool = True
    ) -> Dict[str, Any]:
        """
        검색기를 평가합니다.
        
        Args:
            retriever_name (str): 검색기 이름
            retriever_fn: 검색 함수
            dataset_path (Union[str, Path]): 데이터셋 파일 경로
            advanced (bool): 고급 평가 수행 여부
            
        Returns:
            Dict[str, Any]: 평가 결과
        """
        logger.info(f"검색기 평가 시작: {retriever_name}")
        
        # 데이터셋 로드
        dataset = load_dataset(dataset_path)
        
        # 쿼리 및 관련 문서 추출
        queries = [q["query"] for q in dataset.queries]
        relevant_docs = {q["query"]: q["relevant_doc_ids"] for q in dataset.queries}
        
        # 평가 실행
        if advanced:
            results = evaluate_retrieval_advanced(
                retriever=retriever_fn,
                queries=queries,
                relevant_docs=relevant_docs,
                k_values=[1, 3, 5, 10],
                diversity_methods=["content", "source"]
            )
        else:
            results = evaluate_retrieval_simple(
                retriever=retriever_fn,
                queries=queries,
                relevant_docs=relevant_docs,
                k_values=[1, 3, 5, 10]
            )
        
        # 결과 저장
        save_retrieval_evaluation_results(
            results=results,
            retriever_name=retriever_name,
            results_dir=self.results_dir
        )
        
        logger.info(f"검색기 평가 완료: {retriever_name}")
        
        # LangSmith 평가 (선택적)
        if self.use_langsmith:
            # 데이터셋 ID 가져오기 또는 새로 생성
            dataset_id = self.prepare_langsmith_dataset(dataset_path)
            
            if dataset_id:
                langsmith_results = self.langsmith_evaluator.evaluate_retrieval(
                    dataset_id=dataset_id,
                    retriever_name=retriever_name,
                    retriever_fn=lambda query: [
                        doc.page_content for doc in retriever_fn.get_relevant_documents(query)
                    ]
                )
                logger.info(f"LangSmith 검색기 평가 완료: {retriever_name}")
                
                # 두 결과 병합
                results["langsmith"] = langsmith_results
        
        return results
    
    def evaluate_retriever_robustness(
        self,
        retriever_name: str,
        retriever_fn,
        dataset_path: Union[str, Path],
        variation_types: List[str] = None
    ) -> Dict[str, Any]:
        """
        검색기의 견고성을 평가합니다.
        
        Args:
            retriever_name (str): 검색기 이름
            retriever_fn: 검색 함수
            dataset_path (Union[str, Path]): 데이터셋 파일 경로
            variation_types (List[str]): 쿼리 변형 유형 리스트
            
        Returns:
            Dict[str, Any]: 평가 결과
        """
        logger.info(f"검색기 견고성 평가 시작: {retriever_name}")
        
        # 데이터셋 로드
        dataset = load_dataset(dataset_path)
        
        # 쿼리 및 관련 문서 추출
        queries = [q["query"] for q in dataset.queries]
        relevant_docs = {q["query"]: q["relevant_doc_ids"] for q in dataset.queries}
        
        # 쿼리 변형 생성기 초기화
        query_variations_generator = get_query_variations_generator(
            variation_types=variation_types,
            llm=self.llm
        )
        
        # 각 쿼리 타입별 변형 생성
        modified_queries = {}
        for query in queries[:10]:  # 앞의 10개 쿼리만 사용
            variations = query_variations_generator(query)
            for i, variation in enumerate(variations):
                query_type = f"variation_{i+1}"
                if query_type not in modified_queries:
                    modified_queries[query_type] = []
                modified_queries[query_type].append(variation)
        
        # 추가 변형 유형
        if "typo" not in modified_queries:
            modified_queries["typo"] = []
        if "incomplete" not in modified_queries:
            modified_queries["incomplete"] = []
        if "ambiguous" not in modified_queries:
            modified_queries["ambiguous"] = []
        
        # 견고성 평가 실행
        results = evaluate_retrieval_robustness(
            retriever=retriever_fn,
            original_queries=queries[:10],
            modified_queries=modified_queries,
            relevant_docs=relevant_docs,
            k=5
        )
        
        # 결과 저장
        evaluation_results = {
            "retriever_name": retriever_name,
            "timestamp": datetime.now().isoformat(),
            "results": results
        }
        
        results_file = self.results_dir / f"{retriever_name}_robustness_evaluation.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(evaluation_results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"검색기 견고성 평가 완료: {retriever_name}")
        
        return results
    
    def evaluate_generator(
        self,
        generator_name: str,
        generator_fn,
        dataset_path: Union[str, Path],
        retriever_fn=None
    ) -> Dict[str, Any]:
        """
        생성 모델을 평가합니다.
        
        Args:
            generator_name (str): 생성 모델 이름
            generator_fn: 생성 함수
            dataset_path (Union[str, Path]): 데이터셋 파일 경로
            retriever_fn: 검색 함수 (E2E 평가용)
            
        Returns:
            Dict[str, Any]: 평가 결과
        """
        logger.info(f"생성 모델 평가 시작: {generator_name}")
        
        # 데이터셋 로드
        dataset = load_dataset(dataset_path)
        
        # 검색 + 생성 (E2E) 평가 여부 결정
        is_e2e = retriever_fn is not None
        eval_type = "e2e" if is_e2e else "generation"
        
        all_results = []
        
        # 각 쿼리에 대해 평가 수행
        for query_data in dataset.queries[:10]:  # 처음 10개만 사용
            query = query_data["query"]
            ground_truth = query_data["ground_truth"]
            
            # 관련 문서 찾기
            relevant_doc_ids = query_data.get("relevant_doc_ids", [])
            reference_texts = []
            
            for doc_id in relevant_doc_ids:
                for doc in dataset.documents:
                    if doc["id"] == doc_id:
                        reference_texts.append(doc["content"])
                        break
            
            try:
                if is_e2e:
                    # 검색 수행
                    retrieved_docs = retriever_fn.get_relevant_documents(query)
                    retrieved_texts = [doc.page_content for doc in retrieved_docs]
                    
                    # 생성 수행
                    response = generator_fn(query, retrieved_texts)
                else:
                    # 참조 문서로 생성 수행
                    response = generator_fn(query, reference_texts)
                
                # 평가
                result = evaluate_generation_comprehensive(
                    query=query,
                    response=response,
                    reference_texts=reference_texts,
                    llm=self.llm
                )
                
                # 평가 결과에 메타데이터 추가
                result["query"] = query
                result["ground_truth"] = ground_truth
                result["generated_response"] = response
                
                if is_e2e:
                    result["retrieved_texts"] = retrieved_texts
                
                all_results.append(result)
                
            except Exception as e:
                logger.error(f"생성 평가 중 오류 발생: {query}, 오류: {e}")
        
        # 종합 결과 계산
        summary = {
            "overall_score": sum(r["overall_score"] for r in all_results) / len(all_results) if all_results else 0,
        }
        
        # 세부 점수별 평균 계산
        metrics = ["factual_consistency", "coherence", "relevance", "helpfulness", "completeness"]
        for metric in metrics:
            values = [r["weighted_scores"][metric] for r in all_results]
            summary[f"avg_{metric}"] = sum(values) / len(values) if values else 0
        
        # 최종 결과 형식화
        evaluation_results = {
            "model_name": generator_name,
            "eval_type": eval_type,
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "detailed_results": all_results
        }
        
        # 결과 저장
        save_generation_evaluation_results(
            results=evaluation_results,
            model_name=f"{generator_name}_{eval_type}",
            results_dir=self.results_dir
        )
        
        logger.info(f"생성 모델 평가 완료: {generator_name}")
        
        # LangSmith 평가 (선택적)
        if self.use_langsmith:
            # 데이터셋 ID 가져오기 또는 새로 생성
            dataset_id = self.prepare_langsmith_dataset(dataset_path)
            
            if dataset_id:
                langsmith_results = self.langsmith_evaluator.evaluate_generation(
                    dataset_id=dataset_id,
                    generation_model_name=generator_name,
                    generation_fn=lambda query, docs: generator_fn(query, docs),
                    retriever_fn=None if not is_e2e else (
                        lambda query: [doc.page_content for doc in retriever_fn.get_relevant_documents(query)]
                    )
                )
                logger.info(f"LangSmith 생성 모델 평가 완료: {generator_name}")
                
                # 두 결과 병합
                evaluation_results["langsmith"] = langsmith_results
        
        return evaluation_results
    
    def evaluate_rag_system_robustness(
        self,
        retriever_name: str,
        generator_name: str,
        retriever_fn,
        generator_fn,
        dataset_path: Union[str, Path]
    ) -> Dict[str, Any]:
        """
        RAG 시스템의 견고성을 평가합니다.
        
        Args:
            retriever_name (str): 검색기 이름
            generator_name (str): 생성 모델 이름
            retriever_fn: 검색 함수
            generator_fn: 생성 함수
            dataset_path (Union[str, Path]): 데이터셋 파일 경로
            
        Returns:
            Dict[str, Any]: 평가 결과
        """
        logger.info(f"RAG 시스템 견고성 평가 시작: {retriever_name} + {generator_name}")
        
        if not self.use_langsmith:
            logger.warning("견고성 평가는 LangSmith를 사용해야 합니다.")
            return {}
        
        # 데이터셋 ID 가져오기 또는 새로 생성
        dataset_id = self.prepare_langsmith_dataset(dataset_path)
        
        if not dataset_id:
            logger.error("LangSmith 데이터셋 준비 실패")
            return {}
        
        # 쿼리 변형 생성기 초기화
        query_variations_generator = get_query_variations_generator(
            variation_types=["typo", "incomplete", "semantic"],
            llm=self.llm
        )
        
        # 견고성 평가 실행
        results = self.langsmith_evaluator.evaluate_robustness(
            dataset_id=dataset_id,
            retriever_name=retriever_name,
            generation_model_name=generator_name,
            retriever_fn=lambda query: [doc.page_content for doc in retriever_fn.get_relevant_documents(query)],
            generation_fn=generator_fn,
            query_variations_fn=query_variations_generator
        )
        
        logger.info(f"RAG 시스템 견고성 평가 완료: {retriever_name} + {generator_name}")
        
        return results
    
    def create_basic_rag_chain(
        self,
        retriever,
        llm=None,
        system_prompt=None
    ):
        """
        기본 RAG 체인을 생성합니다.
        
        Args:
            retriever: 검색기
            llm: 언어 모델
            system_prompt (str): 시스템 프롬프트
            
        Returns:
            Chain: RAG 체인
        """
        if llm is None:
            llm = self.llm
        
        if system_prompt is None:
            system_prompt = """
            당신은 유용하고 정확한 정보를 제공하는 AI 어시스턴트입니다.
            제공된 컨텍스트만을 기반으로 질문에 답변하세요.
            컨텍스트에 관련 정보가 없는 경우 모른다고 솔직히 인정하세요.
            """
        
        # 프롬프트 템플릿
        template = """
        <시스템>
        {system_prompt}
        </시스템>
        
        <컨텍스트>
        {context}
        </컨텍스트>
        
        <사용자>
        {query}
        </사용자>
        """
        
        # 프롬프트 생성
        prompt = PromptTemplate.from_template(template)
        
        # 컨텍스트 조합 함수
        def format_context(docs):
            return "\n\n".join([doc.page_content for doc in docs])
        
        # RAG 체인 생성
        chain = (
            {
                "context": retriever | format_context,
                "query": RunnablePassthrough(),
                "system_prompt": lambda _: system_prompt
            }
            | prompt
            | llm
            | StrOutputParser()
        )
        
        return chain
    
    def run_full_evaluation(self, rag_system_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        RAG 시스템에 대한 전체 평가를 실행합니다.
        
        Args:
            rag_system_config (Dict[str, Any]): RAG 시스템 설정
            
        Returns:
            Dict[str, Any]: 평가 결과
        """
        logger.info(f"RAG 시스템 전체 평가 시작: {rag_system_config['name']}")
        
        results = {
            "system_name": rag_system_config["name"],
            "timestamp": datetime.now().isoformat(),
            "embedding": {},
            "retrieval": {},
            "generation": {},
            "e2e": {},
            "robustness": {}
        }
        
        # 데이터셋 생성 또는 로드
        dataset_paths = []
        for dataset_name in rag_system_config.get("datasets", []):
            dataset_path = self.datasets_dir / f"{dataset_name}.json"
            
            if not dataset_path.exists():
                logger.info(f"데이터셋 파일 없음, 생성 시작: {dataset_name}")
                self.generate_datasets()
            
            if dataset_path.exists():
                dataset_paths.append(dataset_path)
        
        if not dataset_paths:
            logger.warning("평가할 데이터셋이 없습니다. 기본 데이터셋을 생성합니다.")
            dataset_paths = self.generate_datasets()
        
        # 임베딩 모델 평가
        if "embedding_models" in rag_system_config:
            embedding_models = rag_system_config["embedding_models"]
            results["embedding"] = self.evaluate_embeddings(models=embedding_models)
        
        # 검색기 평가
        if "retriever" in rag_system_config:
            retriever_config = rag_system_config["retriever"]
            retriever_name = retriever_config["name"]
            retriever = retriever_config["instance"]
            
            for dataset_path in dataset_paths:
                dataset_name = Path(dataset_path).stem
                
                # 기본 검색 성능 평가
                retrieval_results = self.evaluate_retriever(
                    retriever_name=f"{retriever_name}_{dataset_name}",
                    retriever_fn=retriever,
                    dataset_path=dataset_path,
                    advanced=True
                )
                results["retrieval"][dataset_name] = retrieval_results
                
                # 견고성 평가
                robustness_results = self.evaluate_retriever_robustness(
                    retriever_name=f"{retriever_name}_{dataset_name}",
                    retriever_fn=retriever,
                    dataset_path=dataset_path
                )
                results["robustness"][f"retrieval_{dataset_name}"] = robustness_results
        
        # 생성 모델 평가
        if "generator" in rag_system_config and "retriever" in rag_system_config:
            generator_config = rag_system_config["generator"]
            generator_name = generator_config["name"]
            llm = generator_config["instance"]
            
            retriever = rag_system_config["retriever"]["instance"]
            
            # RAG 체인 생성
            rag_chain = self.create_basic_rag_chain(
                retriever=retriever,
                llm=llm,
                system_prompt=generator_config.get("system_prompt")
            )
            
            for dataset_path in dataset_paths:
                dataset_name = Path(dataset_path).stem
                
                # 생성만 평가 (검색 결과 주어진 경우)
                generation_results = self.evaluate_generator(
                    generator_name=f"{generator_name}_{dataset_name}",
                    generator_fn=lambda query, docs: llm.invoke(
                        f"다음 컨텍스트를 바탕으로 질문에 답변하세요:\n\n컨텍스트: {' '.join(docs)}\n\n질문: {query}"
                    ),
                    dataset_path=dataset_path
                )
                results["generation"][dataset_name] = generation_results
                
                # 엔드투엔드 평가 (검색 + 생성)
                e2e_results = self.evaluate_generator(
                    generator_name=f"{generator_name}_{dataset_name}_e2e",
                    generator_fn=lambda query, docs: rag_chain.invoke(query),
                    dataset_path=dataset_path,
                    retriever_fn=retriever
                )
                results["e2e"][dataset_name] = e2e_results
                
                # 시스템 견고성 평가
                if self.use_langsmith:
                    robustness_results = self.evaluate_rag_system_robustness(
                        retriever_name=rag_system_config["retriever"]["name"],
                        generator_name=generator_name,
                        retriever_fn=retriever,
                        generator_fn=lambda query, docs: rag_chain.invoke(query),
                        dataset_path=dataset_path
                    )
                    results["robustness"][f"system_{dataset_name}"] = robustness_results
        
        # 전체 결과 저장
        system_name = rag_system_config["name"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.results_dir / f"{system_name}_full_evaluation_{timestamp}.json"
        
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"RAG 시스템 전체 평가 완료: {system_name}")
        logger.info(f"결과 저장됨: {results_file}")
        
        return results

def main():
    parser = argparse.ArgumentParser(description="RAG 시스템 평가 도구")
    parser.add_argument("--generate-datasets", action="store_true", help="평가 데이터셋 생성")
    parser.add_argument("--evaluate-embeddings", action="store_true", help="임베딩 모델 평가")
    parser.add_argument("--evaluate-retrieval", action="store_true", help="검색 성능 평가")
    parser.add_argument("--evaluate-generation", action="store_true", help="생성 성능 평가")
    parser.add_argument("--evaluate-robustness", action="store_true", help="견고성 평가")
    parser.add_argument("--full-evaluation", action="store_true", help="전체 평가 수행")
    parser.add_argument("--disable-langsmith", action="store_true", help="LangSmith 비활성화")
    
    args = parser.parse_args()
    
    # 평가기 초기화
    evaluator = RAGEvaluator(use_langsmith=not args.disable_langsmith)
    
    # 명령에 따라 평가 실행
    if args.generate_datasets:
        evaluator.generate_datasets()
    
    if args.evaluate_embeddings:
        evaluator.evaluate_embeddings()
    
    if args.evaluate_retrieval or args.evaluate_generation or args.evaluate_robustness or args.full_evaluation:
        logger.warning("이 기능을 사용하려면 구체적인 RAG 시스템 구현이 필요합니다.")
        logger.info("평가 클래스를 직접 사용하여 시스템 평가를 수행하세요.")
    
    # 아무 옵션도 선택하지 않은 경우 도움말 표시
    if not any(vars(args).values()):
        parser.print_help()

if __name__ == "__main__":
    main() 