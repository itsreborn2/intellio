import asyncio
from datetime import datetime
import os
import sys
from pathlib import Path

import numpy as np

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from common.utils.util import dict_to_formatted_str
from stockeasy.services.telegram.question_classifier import QuestionClassifierService
from common.app import LoadEnvGlobal
from common.services.llm_models import LLMModels
from sklearn.metrics.pairwise import cosine_similarity

import logging

# 환경 변수 로드
LoadEnvGlobal()


# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from common.services.embedding import EmbeddingService
from common.services.embedding_models import EmbeddingModelType
embedding_service = EmbeddingService()
#embedding_service.change_model(EmbeddingModelType.GOOGLE_EN)
embedding_service.change_model(EmbeddingModelType.BGE_M3)

async def test_compare_embedding():
    texts = [
    "안녕, 만나서 반가워.",
    "LangChain simplifies the process of building applications with large language models",
    "랭체인 한국어 튜토리얼은 LangChain의 공식 문서, cookbook 및 다양한 실용 예제를 바탕으로 하여 사용자가 LangChain을 더 쉽고 효과적으로 활용할 수 있도록 구성되어 있습니다. ",
    "LangChain은 초거대 언어모델로 애플리케이션을 구축하는 과정을 단순화합니다.",
    "Retrieval-Augmented Generation (RAG) is an effective technique for improving AI responses.",
]   
    _texts = [texts1]
    
    query = query1
    embedding_service.change_model(EmbeddingModelType.GOOGLE_MULTI_LANG)
    embedded_text = await embedding_service.create_embeddings_batch(_texts)
    if embedded_text == []:
        logger.error("임베딩 생성 중 오류 발생")
        return
    embedded_query = await embedding_service.create_single_embedding_async(query)
    
    # 질문(embedded_query): LangChain 에 대해서 알려주세요.
    similarity = np.array(embedded_query) @ np.array(embedded_text).T

    # 유사도 기준 내림차순 정렬
    sorted_idx = (np.array(embedded_query) @ np.array(embedded_text).T).argsort()[::-1]

    # 결과 출력
    print(f"[Query] {query}\n====================================")
    for i, idx in enumerate(sorted_idx):
        print(f"[{i}] 유사도: {similarity[idx]:.3f} | {_texts[idx]}")
        print()
    
async def test_compare_embedding2():

    texts = [
    "안녕, 만나서 반가워.",
    "LangChain simplifies the process of building applications with large language models",
    "랭체인 한국어 튜토리얼은 LangChain의 공식 문서, cookbook 및 다양한 실용 예제를 바탕으로 하여 사용자가 LangChain을 더 쉽고 효과적으로 활용할 수 있도록 구성되어 있습니다. ",
    "LangChain은 초거대 언어모델로 애플리케이션을 구축하는 과정을 단순화합니다.",
    "Retrieval-Augmented Generation (RAG) is an effective technique for improving AI responses.",
]   
    _texts = [texts1]
    embedding_service = EmbeddingService()
    embedding_service.change_model(EmbeddingModelType.GOOGLE_EN)
    query = "LangChain 에 대해서 알려주세요"
    embedded_text = await embedding_service.create_embeddings_batch(_texts)
    if embedded_text == []:
        logger.error("임베딩 생성 중 오류 발생")
        return
    embedded_query = await embedding_service.create_single_embedding_async(query)
    
    # 질문(embedded_query): LangChain 에 대해서 알려주세요.
    similarity = np.array(embedded_query) @ np.array(embedded_text).T

    # 유사도 기준 내림차순 정렬
    sorted_idx = (np.array(embedded_query) @ np.array(embedded_text).T).argsort()[::-1]

    # 결과 출력
    print(f"[Query] {query}\n====================================")
    for i, idx in enumerate(sorted_idx):
        print(f"[{i}] 유사도: {similarity[idx]:.3f} | {_texts[idx]}")
        print()

###############################################################
async def test_evaluate_embeddings():
    # 테스트 데이터 정의
    texts = [
        "인공지능(AI)은 인간의 학습, 추론, 인식 등의 지능을 컴퓨터 시스템으로 구현하는 기술입니다. 머신러닝, 딥러닝, 자연어 처리 등 다양한 분야로 나뉘며, 최근에는 생성형 AI가 큰 주목을 받고 있습니다. 인공지능은 의료, 금융, 교육 등 다양한 산업에 혁신을 가져오고 있으며, 미래 사회의 핵심 기술로 자리잡고 있습니다.",
        "React는 사용자 인터페이스를 구축하기 위한 JavaScript 라이브러리입니다. 컴포넌트 기반 아키텍처를 사용하여 재사용 가능한 UI 요소를 만들 수 있으며, 가상 DOM을 통해 효율적인 렌더링을 제공합니다. React Hooks는 함수형 컴포넌트에서 상태 관리와 생명주기 기능을 사용할 수 있게 해주는 기능으로, useState와 useEffect가 가장 많이 사용됩니다.",
        "Climate change is one of the most pressing challenges facing our planet today. Rising global temperatures, extreme weather events, and melting ice caps are all signs of a changing climate. To address this issue, countries around the world are working to reduce greenhouse gas emissions, transition to renewable energy sources, and implement sustainable practices in various industries.",
        "당뇨병은 혈액 내 포도당 수치가 높아지는 만성 대사 질환입니다. 제1형 당뇨병은 췌장이 인슐린을 거의 또는 전혀 생산하지 못하는 자가면역 질환이며, 제2형 당뇨병은 신체가 인슐린에 저항성을 갖게 되는 상태입니다. 당뇨병의 주요 증상으로는 갈증 증가, 빈뇨, 체중 감소, 피로감 등이 있습니다.",
        "블록체인은 분산 데이터베이스의 한 형태로, 여러 참여자가 공유하는 디지털 원장입니다. 각 거래는 '블록'이라 불리는 데이터 단위에 기록되며, 이 블록들은 시간 순서대로 연결되어 '체인'을 형성합니다. 블록체인의 핵심 특징은 탈중앙화, 투명성, 불변성입니다.",
        "Blockchain is a form of distributed database, a digital ledger shared by multiple participants. Each transaction is recorded in a data unit called a 'block', and these blocks are connected in chronological order to form a 'chain'. The core characteristics of blockchain are decentralization, transparency, and immutability."
    ]

    related_queries = [
        ["인공지능의 정의는 무엇인가요?", "AI의 주요 응용 분야는 어디인가요?", "생성형 AI란 무엇인가요?"],
        ["React의 주요 특징은 무엇인가요?", "React Hooks의 용도는 무엇인가요?", "가상 DOM이란 무엇인가요?"],
        ["기후 변화의 주요 징후는 무엇인가요?", "온실가스 배출을 줄이기 위한 방법은?", "재생 에너지의 중요성은 무엇인가요?"],
        ["제1형과 제2형 당뇨병의 차이점은 무엇인가요?", "당뇨병의 주요 증상은 무엇인가요?"],
        ["블록체인의 주요 특징은 무엇인가요?", "블록체인 기술의 응용 분야는 어디인가요?"],
        ["What are the key features of the blockchain?", "What are the applications of blockchain technology?"]

    ]

    unrelated_queries = [
        ["태양계의 행성들은 무엇이 있나요?", "세계 2차 대전의 원인은 무엇인가요?"],
        ["Python에서 리스트를 정렬하는 방법은?", "SQL 조인의 종류는 무엇인가요?"],
        ["인기있는 여행지 추천해주세요", "건강한 식단을 위한 조언이 필요합니다"],
        ["암 치료의 최신 방법은 무엇인가요?", "알레르기 반응의 원인은 무엇인가요?"],
        ["클라우드 컴퓨팅의 장점은 무엇인가요?", "빅데이터 분석 방법에는 어떤 것들이 있나요?"],
        ["What are the benefits of cloud computing?", "What are some big data analysis methods?"]
    ]
    results = await evaluate_embeddings(texts, related_queries, unrelated_queries)
    #print( dict_to_formatted_str(result))
    # 결과 출력
    for result in results:
        print(f"텍스트 {result['text_id']}: {result['text']}")
        print(f"  관련 쿼리 평균 유사도: {result['avg_related_similarity']:.4f}")
        print(f"  비관련 쿼리 평균 유사도: {result['avg_unrelated_similarity']:.4f}")
        print(f"  차이: {result['difference']:.4f}")
        print(f"  성공 여부: {'성공' if result['success'] else '실패'}")
        print()

async def get_embedding_text(text):
    embeddings = await embedding_service.create_embeddings_batch([text])
    return embeddings[0]

async def get_embedding_query(query):
    embeddings = await embedding_service.create_single_embedding_async(query)
    return embeddings

async def evaluate_embeddings(texts, related_queries, unrelated_queries):
    results = []
    
    for i, text in enumerate(texts):
        text_embedding = await get_embedding_text(text)
        
        # 관련 쿼리 유사도 계산
        related_similarities = []
        for query in related_queries[i]:
            query_embedding = await get_embedding_query(query)
            similarity = cosine_similarity([text_embedding], [query_embedding])[0][0]
            related_similarities.append(similarity)
        
        # 비관련 쿼리 유사도 계산
        unrelated_similarities = []
        for query in unrelated_queries[i]:
            query_embedding = await get_embedding_query(query)
            similarity = cosine_similarity([text_embedding], [query_embedding])[0][0]
            unrelated_similarities.append(similarity)
        
        avg_related = np.mean(related_similarities)
        avg_unrelated = np.mean(unrelated_similarities)
        
        results.append({
            "text_id": i,
            "text": text[:50] + "...",  # 텍스트 미리보기
            "avg_related_similarity": avg_related,
            "avg_unrelated_similarity": avg_unrelated,
            "difference": avg_related - avg_unrelated,
            "success": avg_related > avg_unrelated
        })
    
    return results
if __name__ == "__main__":
    #test_question_classifier()
    #test_question_classifier3()
    #asyncio.run(test_func_aync())
    #asyncio.run(test_compare_embedding())
    #asyncio.run(test_compare_embedding2())
    asyncio.run(test_evaluate_embeddings())
