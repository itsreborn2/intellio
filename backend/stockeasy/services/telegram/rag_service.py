"""멀티에이전트 기반 텔레그램 RAG 서비스

이 모듈은 텔레그램 메시지에 대한 검색과 요약, 기업 리포트 분석, 재무 데이터 분석, 
산업 동향 분석을 Langgraph 기반 멀티에이전트 시스템을 통해 제공합니다.
"""

import asyncio
from typing import Dict, List, Any, Optional
from loguru import logger
import time
from sqlalchemy.ext.asyncio import AsyncSession

from stockeasy.graph.agent_registry import get_graph
from stockeasy.services.telegram.question_classifier import QuestionClassification
from common.utils.util import async_retry
from common.core.config import settings
from common.core.database import get_db_session


class StockRAGService:
    """Langgraph 기반 주식 분석 RAG 서비스"""
    
    def __init__(self, db: Optional[AsyncSession] = None):
        """
        주식 분석 그래프 초기화
        
        Args:
            db: 데이터베이스 세션 객체 (선택적)
        """
        self.db = db or asyncio.run(get_db_session())
        self.graph = get_graph(self.db)
        logger.info("멀티에이전트 기반 주식 분석 RAG 서비스가 초기화되었습니다.")
    
    @async_retry(retries=2, delay=2.0, exceptions=(Exception,))
    async def analyze_stock(self, 
                           query: str, 
                           stock_code: Optional[str] = None,
                           stock_name: Optional[str] = None,
                           classification: Optional[QuestionClassification] = None) -> Dict[str, Any]:
        """
        주식 관련 쿼리 분석 및 응답 생성
        
        Args:
            query: 사용자 질문
            stock_code: 종목 코드 (선택적)
            stock_name: 종목명 (선택적)
            classification: 질문 분류 결과 (선택적)
            
        Returns:
            분석 결과 (요약, 검색된 메시지, 분류 정보 등)
        """
        try:
            start_time = time.time()
            logger.info(f"주식 분석 시작: {query}")
            
            # 이미 분류 결과가 있으면 해당 정보 사용
            initial_state = {
                "query": query,
                "stock_code": stock_code,
                "stock_name": stock_name,
            }
            
            if classification:
                initial_state["question_classification"] = classification.model_dump()

            # 세션 ID 생성 (필요 시 구현)
            # initial_state["session_id"] = self._generate_session_id()
            
            result = await self.graph.process_query(**initial_state)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # 처리 시간 로깅
            logger.info(f"주식 분석 완료: 처리 시간 = {processing_time:.2f}초")
            
            # 결과에 처리 시간 추가
            if result:
                if "processing_status" not in result:
                    result["processing_status"] = {}
                result["processing_status"]["total_time"] = processing_time
            
            return result
            
        except Exception as e:
            logger.error(f"주식 분석 중 오류 발생: {str(e)}", exc_info=True)
            return {
                "query": query,
                "errors": [{
                    "agent": "stock_rag_service",
                    "error": str(e),
                    "type": type(e).__name__
                }],
                "summary": "죄송합니다. 주식 분석 중 오류가 발생했습니다."
            }


class TelegramRAGLangraphService:
    """Langgraph 기반 텔레그램 RAG 서비스"""
    
    def __init__(self, db: Optional[AsyncSession] = None):
        """
        서비스 초기화
        
        Args:
            db: 데이터베이스 세션 객체 (선택적)
        """
        self.stock_rag_service = StockRAGService(db)
        logger.info("Langgraph 기반 텔레그램 RAG 서비스가 초기화되었습니다.")
    
    async def search_and_summarize(self, 
                                  query: str, 
                                  stock_code: Optional[str] = None, 
                                  stock_name: Optional[str] = None,
                                  classification: Optional[QuestionClassification] = None) -> Dict[str, Any]:
        """
        텔레그램 메시지 검색 및 요약
        
        최신 멀티에이전트 아키텍처를 사용하여 텔레그램 메시지와 다양한
        금융 데이터 소스에서 정보를 검색하고 요약합니다.
        
        Args:
            query: 검색 쿼리
            stock_code: 종목 코드 (선택적)
            stock_name: 종목명 (선택적)
            classification: 질문 분류 결과 (선택적)
            
        Returns:
            검색 및 요약 결과
        """
        try:
            logger.info(f"검색 및 요약 시작: {query}")
            
            # StockRAGService를 통해 멀티에이전트 분석 수행
            result = await self.stock_rag_service.analyze_stock(
                query=query,
                stock_code=stock_code,
                stock_name=stock_name,
                classification=classification
            )
            
            # 결과 구조화
            summary = result.get("summary", "")
            formatted_response = result.get("formatted_response", "")
            
            # 실제 사용할 최종 응답 선택 (formatted_response가 있으면 사용, 없으면 summary 사용)
            final_response = formatted_response or summary
            
            # 메트릭 수집
            processing_status = result.get("processing_status", {})
            
            return {
                "summary": final_response,
                "telegram_messages": result.get("retrieved_data", {}).get("telegram_messages", []),
                "question_classification": result.get("question_classification", {}),
                "processing_time": processing_status.get("total_time", 0)
            }
            
        except Exception as e:
            logger.error(f"검색 및 요약 중 오류 발생: {str(e)}", exc_info=True)
            return {
                "summary": f"죄송합니다. 검색 중 오류가 발생했습니다: {str(e)}",
                "telegram_messages": [],
                "question_classification": classification.model_dump() if classification else {},
                "processing_time": 0,
                "error": str(e)
            } 