"""
리랭커 테스트 예제
"""

import asyncio
import os
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from loguru import logger
from dotenv import load_dotenv
from common.core.config import settings
from common.services.retrievers.models import DocumentWithScore
from common.services.reranker import (
    Reranker, 
    RerankerConfig, 
    RerankerType, 
    PineconeRerankerConfig
)

# 환경 변수 로드
load_dotenv()

async def test_pinecone_reranker():
    """Pinecone 리랭커 테스트"""
    
    # 테스트 문서
    documents = [
        DocumentWithScore(
            page_content="삼성전자는 2024년 1분기에 반도체 사업에서 흑자 전환에 성공했습니다.",
            metadata={"id": "1", "type": "company_news"},
            score=0.85
        ),
        DocumentWithScore(
            page_content="삼성전자 주가가 상승세를 보이고 있으며, 반도체 시장 회복에 따른 실적 개선이 기대됩니다.",
            metadata={"id": "2", "type": "stock_analysis"},
            score=0.75
        ),
        DocumentWithScore(
            page_content="반도체 시장은 AI 수요 증가로 인해 2024년에 큰 성장이 예상됩니다.",
            metadata={"id": "3", "type": "market_trend"},
            score=0.65
        ),
        DocumentWithScore(
            page_content="삼성전자는 GAA 공정을 도입하여 파운드리 경쟁력을 강화하고 있습니다.",
            metadata={"id": "4", "type": "technology"},
            score=0.60
        ),
        DocumentWithScore(
            page_content="스마트폰 시장은 2024년에 완만한 성장이 예상되며, 삼성전자는 폴더블 제품으로 시장 주도권을 유지할 전망입니다.",
            metadata={"id": "5", "type": "market_forecast"},
            score=0.55
        ),
    ]
    
    # 리랭커 설정
    config = RerankerConfig(
        reranker_type=RerankerType.PINECONE,
        pinecone_config=PineconeRerankerConfig(
            api_key=settings.PINECONE_API_KEY_STOCKEASY,
            model_name="bge-reranker-v2-m3",
            min_score=0.1
        )
    )
    
    # 리랭커 초기화
    reranker = Reranker(config)
    
    # 쿼리 정의
    query = "삼성전자 반도체 사업 전망"
    
    # 리랭킹 수행
    results = await reranker.rerank(
        query=query,
        documents=documents,
        top_k=3
    )
    
    # 결과 출력
    print("\n" + "="*80)
    print(f"[쿼리] {query}")
    print("="*80)
    
    print(f"\n[원본 문서 순서]")
    for i, doc in enumerate(documents):
        print(f"{i+1}. 점수: {doc.score:.3f}, 내용: {doc.page_content}")
    
    print(f"\n[리랭킹 결과] - {len(results.documents)} 문서")
    for i, doc in enumerate(results.documents):
        rerank_score = doc.metadata.get("rerank_score", 0.0)
        print(f"{i+1}. 점수: {doc.score:.3f} (리랭킹 점수: {rerank_score:.3f})")
        print(f"   내용: {doc.page_content}")
        print(f"   메타데이터: {doc.metadata}")
        print("-" * 40)
    
    print("\n" + "="*80)
    
    return results

if __name__ == "__main__":
    asyncio.run(test_pinecone_reranker()) 