import asyncio
from datetime import datetime
import os
import sys
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)


from common.utils.util import dict_to_formatted_str
from stockeasy.services.telegram.question_classifier import QuestionClassifierService
from common.app import LoadEnvGlobal
from common.services.llm_models import LLMModels
import vertexai
from vertexai.language_models import TextEmbeddingModel
from loguru import logger

from google.oauth2 import service_account

from openai import OpenAI
from common.core.config import settings

from langchain_openai import OpenAIEmbeddings

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_vertexai.embeddings import VertexAIEmbeddings

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from rich.console import Console


# 환경 변수 로드
LoadEnvGlobal()


# 로깅 설정
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

    
async def test_stockeasy_rag():
    #print(f"ENV : {settings.ENV}")
    from common.services.vector_store_manager import VectorStoreManager
    from common.services.embedding_models import EmbeddingModelType
    from stockeasy.services.rag import StockeasyRAGService

    rag_service = StockeasyRAGService()

    while True:
        question = input("질문을 입력하세요: ")
        if question == "q" or question == "ㅂ":
            break
        messages = await rag_service.user_question(question)
        #summary = await rag_service.summarize(messages)
        #summary= await rag_service.test_func()
        print(f"답변: {messages}")
def test_question_classifier():
    from stockeasy.services.telegram.question_classifier import QuestionClassifierService
    question_classifier = QuestionClassifierService()
    # 사용자의 입력을 반복적으로 처리하자
    # 터미널로 입력받고, q 입력시 반복 종료
    while True:
        question = input("질문을 입력하세요: ")
        if question == "q" or question == "ㅂ":
            break
        #result = question_classifier.classify_question(question)
        result = question_classifier.classify_question_with_deberta(question)
        print(result)
        print(f"질문주제: {result['질문주제']}")
        print(f"답변수준: {result['답변수준']}")
        print(f"추가옵션: {result['추가옵션']}")
        print(f"종목코드: {result['종목코드']}")
        print(f"종목명: {result['종목명']}")

def test_question_classifier2():
    # 질문 분류기 초기화
    classifier = QuestionClassifierService()
    
    # 테스트 질문
    test_questions = [
        # 종목 기본 정보 관련 질문 (배당, 재무, 주가 등)
        "삼전의 배당률이 어떻게 되나요?",
        "네이버의 현재 주가가 얼마인가요?",
        "카카오의 PER은 얼마인가요?",
        "현대차의 최근 분기 매출액은 얼마인가요?",
        "엘지화학의 부채비율은 어떻게 되나요?",
        "하이닉스의 영업이익률 추이가 어떻게 되나요?",
        "셀트리온의 시가총액은 얼마인가요?",
        "포스코의 ROE는 어떻게 되나요?",
        
        # 전망 관련 질문 (미래 전망, 투자 의견, 시장 분석 등)
        "삼성전자의 반도체 사업 전망이 어떻게 될까요?",
        "현대차의 전기차 시장 점유율이 앞으로 어떻게 변할까요?",
        "네이버의 AI 사업 전략은 어떻게 평가되나요?",
        "삼전 사요?",
        "lg엔솔 망하나?",
        "한화에어로 내년에 좋으려나?",
        "ls일렉은 미국수혜 보나?",
        
        # 기타 금융/주식 관련 질문
        "2차전지 언제 돌릴까?",
        "도지 코인 어떠냐? 풀베팅?",
        "코스피 지수가 올해 어떻게 변할까요?",
        "미국 금리 인상이 한국 주식 시장에 미치는 영향은 무엇인가요?",
        "인플레이션이 주식 시장에 미치는 영향은 어떤가요?",
        "ETF와 개별 주식 중 어떤 투자가 더 좋을까요?",
        "장기 투자와 단기 투자의 차이점은 무엇인가요?"
    ]
    
    # 결과를 저장할 파일 경로
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = f"question_classification_results_{timestamp}.txt"

# 파일에 결과 저장
    with open(result_file, "w", encoding="utf-8") as f:
        f.write(f"질문 분류 테스트 결과\n")
        f.write("="*80 + "\n\n")
        # 각 질문에 대해 분류 결과 출력
        # 각 질문에 대해 분류 결과 출력 및 저장
        for i, question in enumerate(test_questions, 1):
            f.write(f"[질문 {i}] {question}\n")
            print(f"\n[질문 {i}] {question}")

            result = classifier.classify_question(question)
                
            # 콘솔에 출력
            result_str = dict_to_formatted_str(result.to_dict_with_labels(), sort_keys=True)
            print(f"분류 결과: {result_str}")
            
            # 파일에 저장 (여러 형식으로)
            f.write("분류 결과:\n")
            f.write(result_str)
            f.write("\n\n" + "-"*50 + "\n\n")
        
            # try:
            #     result = classifier.classify_question(question)
            #     #print(f"분류 결과: {result.model_dump_json(indent=2)}")
            #     print(f"분류 결과: {dict_to_formatted_str(result.to_dict_with_labels(), sort_keys=True)}")
                
            # except Exception as e:
            #     print(f"오류 발생: {str(e)}")



def test_question_classifier3():
    from stockeasy.services.telegram.question_classifier import QuestionClassifierService
    question_classifier = QuestionClassifierService()
    # 사용자의 입력을 반복적으로 처리하자
    # 터미널로 입력받고, q 입력시 반복 종료
    while True:
        question = input("질문을 입력하세요: ")
        if question == "q" or question == "ㅂ":
            break
        #result = question_classifier.classify_question(question)
        result = question_classifier.classify_question_with_structured_output(question)
        result_str = dict_to_formatted_str(result.to_dict_with_labels(), sort_keys=True)
        print(f"분류 결과: {result_str}")
        print('-'*80)
        #result = question_classifier.classify_question(question)
                
        # # 콘솔에 출력
        # result_str = dict_to_formatted_str(result.to_dict_with_labels(), sort_keys=True)
        # print(f"분류 결과: {result_str}")
        
    
    
    
    
if __name__ == "__main__":
    #test_question_classifier()
    #test_question_classifier3()
    #asyncio.run(test_func_aync())
    asyncio.run(test_stockeasy_rag())

