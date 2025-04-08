"""
멀티에이전트 시스템 테스트

이 모듈은 Stockeasy 멀티에이전트 시스템을 테스트하기 위한 스크립트를 제공합니다.
"""
import hashlib
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import re

from zoneinfo import ZoneInfo

from common.services.agent_llm import get_agent_llm

# 상위 디렉토리를 sys.path에 추가하여 모듈을 import할 수 있게 함


from uuid import UUID

from common.services.embedding_models import EmbeddingModelType
from common.models.token_usage import ProjectType
from common.services.retrievers.contextual_bm25 import ContextualBM25Config
from common.services.retrievers.hybrid import HybridRetriever, HybridRetrieverConfig
from common.services.retrievers.models import RetrievalResult
from common.services.retrievers.semantic import SemanticRetriever, SemanticRetrieverConfig
from common.services.vector_store_manager import VectorStoreManager

import asyncio
import json
from loguru import logger
from datetime import datetime, timedelta, timezone
import pytz
from typing import Dict, Any, List, Optional, Set, Union
from common.app import LoadEnvGlobal

LoadEnvGlobal()
# LangSmith 환경 변수 설정
#os.environ["LANGCHAIN_TRACING"] = "true"
#os.environ["LANGCHAIN_TRACING_V2"] = "true"
#os.environ["LANGCHAIN_PROJECT"] = "stockeasy_multiagent"
# LANGSMITH_API_KEY는 .env 파일에서 로드됨

from stockeasy.models.agent_io import QuestionAnalysisResult, RetrievedTelegramMessage
from common.core.config import settings
# 로그 시간을 한국 시간으로 설정
logger.remove()  # 기존 핸들러 제거

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

# 한국 시간으로 설정된 로거 추가 (간단한 형식으로 수정)
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} KST | {level: <8} | {name}:{line} - {message}",
    level="INFO",
    colorize=True,
)


# 로거 설정 이후에 모듈 임포트
from common.core.database import get_db_session
def _calculate_time_weight(created_at: datetime) -> float:
        """
        메시지 생성 시간 기반의 가중치를 계산합니다.
        
        Args:
            created_at: 메시지 생성 시간 (datetime 객체)
            
        Returns:
            시간 기반 가중치 (0.4 ~ 1.0)
        """
        try:
            seoul_tz = timezone(timedelta(hours=9), 'Asia/Seoul')
        
            # naive datetime인 경우 서버 로컬 시간(Asia/Seoul)으로 간주
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=ZoneInfo("Asia/Seoul"))
                
            # now도 timezone 정보를 포함하도록 수정
            now = datetime.now(seoul_tz)
            delta = now - created_at
            
            # 시간 차이에 따른 가중치 설정
            if delta.days < 1:  # 24시간 이내
                return 1.0
            elif delta.days < 7:  # 1주일 이내
                return 0.9
            elif delta.days < 14:  # 2주일 이내
                return 0.8
            elif delta.days < 30:  # 1개월 이내
                return 0.6
            else:  # 1개월 이상
                return 0.4
                
        except Exception as e:
            logger.warning(f"시간 가중치 계산 오류: {str(e)}")
            return 0.5  # 오류 시 중간값 반환
        
def _calculate_message_importance( message: str) -> float:
        """
        메시지의 중요도를 계산합니다.
        
        Args:
            message: 중요도를 계산할 메시지
            
        Returns:
            0~1 사이의 중요도 점수
        """
        importance_score = 0.0
        
        # 1. 금액/수치 정보 포함 여부 (40%)
        if re.search(r'[0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?%?원?', message):
            importance_score += 0.4
            
        # 2. 주요 키워드 포함 여부 (40%)
        important_keywords = [
            '실적', '공시', '매출', '영업이익', '순이익',
            '계약', '특허', '인수', '합병', 'M&A',
            '상한가', '하한가', '급등', '급락',
            '목표가', '투자의견', '리포트'
        ]
        keyword_count = sum(1 for keyword in important_keywords if keyword in message)
        if keyword_count > 0:
            importance_score += min(0.4, keyword_count * 0.2)  # 키워드당 0.2점, 최대 0.4점
        
        # 3. 메시지 길이 가중치 (20%)
        msg_length = len(message)
        if 50 <= msg_length <= 500:
            importance_score += 0.2
        elif 20 <= msg_length < 50 or 500 < msg_length <= 1000:
            importance_score += 0.1
            
        return importance_score

def _get_message_hash( content: str) -> str:
        """
        메시지 내용의 해시값을 생성합니다.
        
        Args:
            content: 메시지 내용
            
        Returns:
            메시지 해시값
        """
        # 메시지 전처리 (공백 제거, 소문자 변환)
        normalized_content = re.sub(r'\s+', ' ', content).strip().lower()
        
        # 너무 긴 메시지는 앞부분만 사용
        if len(normalized_content) > 200:
            normalized_content = normalized_content[:200]
            
        # SHA-256 해시 생성하여 반환
        return hashlib.sha256(normalized_content.encode('utf-8')).hexdigest() 

def _is_duplicate(message: str, seen_messages: Set[str]) -> bool:
        """
        메시지가 이미 처리된 메시지 중 중복인지 확인합니다.
        
        Args:
            message: 검사할 메시지
            seen_messages: 이미 처리된 메시지 해시 집합
            
        Returns:
            중복 여부
        """
        # 메시지 해시 생성
        message_hash = _get_message_hash(message)
        
        # 중복 확인
        if message_hash in seen_messages:
            return True
            
        return False

async def _search_messages(search_query: str, k: int, threshold: float, user_id: Optional[Union[str, UUID]] = None, search_type:str = "hybrid") -> List[RetrievedTelegramMessage]:
        """
        텔레그램 메시지 검색을 수행합니다.
        
        Args:
            search_query: 검색 쿼리
            k: 검색할 메시지 수
            threshold: 유사도 임계값
            user_id: 사용자 ID (문자열 또는 UUID 객체)
            
        Returns:
            검색된 텔레그램 메시지 목록
        """
        try:
            logger.info(f"Generated search query: {search_query}")
            
            # 임베딩 모델을 사용하여 쿼리 벡터 생성
            
            # 초기 검색은 더 많은 결과를 가져온 후 필터링
            initial_k = min(k * 3, 30)  # 적어도 원하는 k의 3배, 최대 30개까지
            
            # Pinecone 벡터 스토어 연결
            vs_manager = VectorStoreManager(
                embedding_model_type=EmbeddingModelType.OPENAI_3_LARGE,
                project_name="stockeasy",
                namespace=settings.PINECONE_NAMESPACE_STOCKEASY_TELEGRAM
            )

            # UUID 변환 로직: 문자열이면 UUID로 변환, UUID 객체면 그대로 사용, None이면 None
            if user_id != "test_user":
                parsed_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
            else:
                parsed_user_id = None

            semantic_retriever_config = SemanticRetrieverConfig(min_score=threshold,
                                               user_id=parsed_user_id,
                                               project_type=ProjectType.STOCKEASY    )
            # 시맨틱 검색 설정
            semantic_retriever = SemanticRetriever(
                config=semantic_retriever_config,
                vs_manager=vs_manager
            )
            
            if search_type == "hybrid":
                hybrid_retriever = HybridRetriever(
                    config=HybridRetrieverConfig(
                        semantic_config=semantic_retriever_config,
                        contextual_bm25_config=ContextualBM25Config(
                                            min_score=0.1,
                                            bm25_weight=0.6,
                                            context_weight=0.4,
                                            context_window_size=3
                                        ),
                        semantic_weight=0.6,
                        contextual_bm25_weight=0.4,
                        vector_multiplier=2
                    ),
                    vs_manager=vs_manager
                )
                #result:RetrievalResult = await hybrid_retriever.retrieve_vector_then_bm25(
                result:RetrievalResult = await hybrid_retriever.retrieve_vector_then_rerank(
                        query=search_query, 
                        top_k=initial_k
                    )
            else:     
                result:RetrievalResult = await semantic_retriever.retrieve(
                    query=search_query, 
                    top_k=initial_k,#k * 2,
                )
            
            # 검색 수행
            # result: RetrievalResult = await semantic_retriever.retrieve(
            #     query=search_query, 
            #     top_k=initial_k,#k * 2,
            # )
            
            if len(result.documents) == 0:
                logger.warning(f"No telegram messages found for query: {search_query}")
                return []
                
            logger.info(f"Found {len(result.documents)} telegram messages")
            
            # 중복 메시지 필터링 및 점수 계산
            processed_messages = []
            seen_messages = set()  # 중복 확인용
            temp_docs = []
            
            for doc in result.documents:
                doc_metadata = doc.metadata
                content = doc.page_content# doc_metadata.get("text", "")
                
                # 내용이 없거나 너무 짧은 메시지 제외
                if not content or len(content) < 20:
                    continue
                
                normalized_content = re.sub(r'\s+', ' ', content).strip().lower()
                # 중복 메시지 확인
                if _is_duplicate(normalized_content, seen_messages):
                    logger.info(f"중복 메시지 제외: {normalized_content[:50]}")
                    continue
                    
                seen_messages.add(_get_message_hash(normalized_content))
                temp_docs.append(doc)
            # 중복 제거된 청크로. 리랭킹 수행

            # 종복 제거된 것으로
            for doc in temp_docs:
                doc_metadata = doc.metadata
                content = doc.page_content
                # 메시지 중요도 계산
                importance_score = _calculate_message_importance(content)
                
                # 시간 기반 가중치 계산
                message_created_at_data = doc.metadata["message_created_at"]
                message_created_at = None
                
                # message_created_at을 datetime 객체로 변환 (다양한 형식 지원)
                if isinstance(message_created_at_data, str):
                    # ISO 형식 문자열인 경우
                    try:
                        message_created_at = datetime.fromisoformat(message_created_at_data)
                    except (ValueError, TypeError):
                        # ISO 형식이 아닌 경우 다른 형식 시도
                        print(f"ISO 형식이 아닌 문자열: {message_created_at_data}, 다른 형식 시도")
                        try:
                            # 유닉스 타임스탬프 문자열인지 확인
                            message_created_at = datetime.fromtimestamp(float(message_created_at_data))
                        except (ValueError, TypeError):
                            # 기본값으로 현재 시간 사용
                            print(f"시간 형식 변환 실패: {message_created_at_data}, 현재 시간 사용")
                            message_created_at = datetime.now()
                elif isinstance(message_created_at_data, (int, float)):
                    # 유닉스 타임스탬프인 경우
                    try:
                        message_created_at = datetime.fromtimestamp(float(message_created_at_data))
                    except (ValueError, TypeError):
                        # 변환 실패 시 현재 시간 사용
                        print(f"타임스탬프 변환 실패: {message_created_at_data}, 현재 시간 사용")
                        message_created_at = datetime.now()
                else:
                    # 지원되지 않는 형식인 경우 현재 시간 사용
                    print(f"지원되지 않는 시간 형식: {type(message_created_at_data)}, 현재 시간 사용")
                    message_created_at = datetime.now()
                
                time_weight = _calculate_time_weight(message_created_at)
                
                # 최종 점수 = 유사도 * 중요도 * 시간 가중치
                #final_score = doc.score * importance_score * time_weight
                final_score = (doc.score * 0.5) + (importance_score * 0.3) + (time_weight * 0.2)
                # 메시지 데이터 구성
                message:RetrievedTelegramMessage = {
                    "content": content,
                    #"channel_name": doc_metadata.get("channel_title", "알 수 없음"), # 그러나 숨겨야함
                    "message_created_at": message_created_at,
                    "final_score": final_score,
                    "metadata": doc_metadata
                }
                
                processed_messages.append(message)
            
            # 최종 점수 기준으로 정렬하고 상위 k개 선택
            processed_messages.sort(key=lambda x: x["final_score"], reverse=True)
            logger.info(f"최종 점수 기준으로 정렬된 메시지 수: {len(processed_messages)}")
            result_messages = processed_messages[:k]
            
            # 점수 분포 정규화
            if result_messages:
                max_score = max(msg["final_score"] for msg in result_messages)
                min_score = min(msg["final_score"] for msg in result_messages)
                score_range = max_score - min_score if max_score > min_score else 1.0
                
                for msg in result_messages:
                    msg["normalized_score"] = (msg["final_score"] - min_score) / score_range
            
            return result_messages
            
        except Exception as e:
            logger.exception(f"Error searching telegram messages: {str(e)}")
            raise 

async def main():
#     _search_query = """사용자 질문: 메모리 가격 전망과 앞으로 실적은?
# 종목명: 삼성전자
# 종목코드: 005930
# """
    #_search_query = "게임 인조이에 관해서 설명해줘. 최근 출시했는데 반응이 어떤 편이지?"
    _search_query = "게임 인조이의 반응에 관해서 알려주고, 접속자 추이를 정리해봐"
    #_search_query = "dram 커미디티 가격이 상승세인데, 그 원인과 삼성전자의 주가의 관계는?"
    #_search_query = "마이크로컨텍솔 실적과 올해 전망은?"
    _k = 15
    _threshold = 0.22
    #_user_id = "blueslame@gmail.com"

    result:List[RetrievedTelegramMessage] = await _search_messages(search_query=_search_query, 
                                                                   k=_k, threshold=_threshold, 
                                                                   #search_type="semantic"
                                                                   )
    # 결과 예쁘게 출력
    print("\n" + "="*80)
    print(f"🔍 검색 쿼리: '{_search_query}' (임계값: {_threshold}, 결과 수: {len(result)})")
    print("="*80)
    docs = []
    for idx, item in enumerate(result[:4]):
        rerank_score = item.get("metadata", {}).get("rerank_score", 0.0)
        print(f"\n📝 결과 #{idx} [유사도: {item.get('final_score', 0):.4f}, 리랭킹 점수: {rerank_score:.4f}]")
        print(f"📅 날짜: {item.get('message_created_at')}")
        print("-"*60)
        print(f"{item.get('content', '내용 없음')[:200]}...")
        print("-"*60)
        text = f"날짜: {item.get('message_created_at')}\n내용: {item.get('content', '내용 없음')}"
        text += "------------------"
        docs.append(text)
    
    print("\n" + "="*80)
    print(f"검색 완료: 총 {len(result)}개 결과")
    print("="*80)

    # f-string에서 백슬래시 문제 해결
    prompt = (
        f"정해진 문서의 내용 안에서만 답해주세요. 없는 내용이라면 모른다고 답해주세요.\n\n"
        f"질문: {_search_query}\n\n"
        f"내용 : {chr(10).join(docs)}"
    )
    llm = get_agent_llm("test_agent")
    response = await llm.ainvoke_with_fallback(prompt)
    print("-"*80)
    print(f"## 질문 : {_search_query}")
    print("-"*80)
    print(f"##답변 : \n{response.content}")

if __name__ == "__main__":
    # 테스트 실행
    asyncio.run(main()) 