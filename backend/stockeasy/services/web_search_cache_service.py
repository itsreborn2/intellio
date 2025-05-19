import csv
import os
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, func, desc, text, bindparam
from sqlalchemy.dialects.postgresql import array
from datetime import datetime
from loguru import logger
from sqlalchemy.sql.expression import cast
from sqlalchemy import String

from common.services.embedding import EmbeddingService
from common.services.embedding_models import EmbeddingModelType
from stockeasy.models.web_search_cache import WebSearchQueryCache, WebSearchResultCache

class WebSearchCacheService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.similarity_threshold = 0.89  # 코사인 유사도 임계값
        self.csv_log_lock = asyncio.Lock() # CSV 파일 접근 동기화를 위한 Lock
        
    async def _log_similarity_to_csv(self, timestamp: datetime, original_query: str, found_query: str, similarity_score: float):
        """유사도 검사 결과를 CSV 파일에 비동기적으로 기록합니다."""
        
        # 파일 I/O 작업을 별도 스레드에서 실행하기 위한 중첩 함수
        def write_similarity_data():
            try:
                csv_dir = Path("stockeasy") / "local_cache" / "web_search"
                os.makedirs(csv_dir, exist_ok=True)
                
                date_str = timestamp.strftime('%Y%m%d')
                csv_path = csv_dir / f'similarity_checks_{date_str}.csv'
                
                formatted_timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                data_row = [formatted_timestamp, original_query, found_query, f"{similarity_score:.4f}"]
                
                file_exists = csv_path.exists() and csv_path.stat().st_size > 0
                
                with open(csv_path, "a", newline="", encoding="utf-8-sig") as f: # utf-8-sig로 변경하여 Excel에서 한글 깨짐 방지
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(["일자", "원본쿼리", "찾은쿼리", "유사도값"])  # 헤더
                    writer.writerow(data_row)
                
                logger.debug(f"유사도 검사 결과 CSV 저장 완료: {csv_path}")
                return str(csv_path)
            except Exception as e_io:
                logger.error(f"CSV 로그 파일 쓰기 중 오류 발생: {str(e_io)}", exc_info=True)
                return None

        async with self.csv_log_lock:
            try:
                # 파일 I/O 작업을 별도 스레드에서 비동기적으로 실행
                csv_file_path = await asyncio.to_thread(write_similarity_data)
                if csv_file_path:
                    logger.info(f"💾 유사도 검사 결과가 CSV 파일에 기록되었습니다: {csv_file_path}")
                else:
                    logger.warning("유사도 검사 결과 CSV 파일 기록 실패.")
            except Exception as e_lock:
                # Lock 자체 또는 to_thread 호출 관련 예외 처리
                logger.error(f"CSV 로그 저장 중 Lock 또는 스레딩 오류 발생: {str(e_lock)}", exc_info=True)
        
    async def check_cache(self, queries: List[str], stock_code: Optional[str] = None, stock_name: Optional[str] = None) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        캐시에서 유사한 쿼리와 결과를 검색합니다.
        
        Args:
            queries: 검색할 쿼리 목록
            stock_code: 종목 코드
            stock_name: 종목 이름
            
        Returns:
            캐시 히트 결과와 캐시 미스 쿼리의 튜플
        """
        if not queries:
            return [], []
        from sqlalchemy import func, cast, Float
        from sqlalchemy.dialects.postgresql import ARRAY

        # 임베딩 서비스 초기화
        embedding_service = EmbeddingService(model_type=EmbeddingModelType.OPENAI_3_LARGE)
        try:
            cache_hits = []
            cache_misses = []
            
            for query in queries:
                try:
                    # 쿼리 임베딩 생성
                    query_embedding = await embedding_service.create_single_embedding_async(query)
                    # 임베딩을 pgvector 호환 문자열로 변환
                    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
                    
                    # 벡터 검색 쿼리 수행 (raw SQL 사용)
                    # 1 - (q.embedding <=> :embedding::vector) AS similarity,
                    # 1 - 재ㅔ거하고 해보자.

                    stmt = text("""
                        SELECT 
                            q.id, 
                            q.query, 
                            q.stock_code,
                            q.stock_name,
                            1 - (q.embedding <=> (:embedding)::vector) AS similarity,
                            q.hit_count,
                            q.created_at
                        FROM 
                            stockeasy.web_search_query_cache q
                        WHERE 
                            q.stock_code = :stock_code
                        ORDER BY 
                            similarity DESC
                        LIMIT 5
                    """)
                    # 또는 명시적 파라미터 바인딩 추가
                    stmt = stmt.bindparams(
                        bindparam('embedding', type_=String),  # 벡터 타입은 None으로 지정
                        bindparam('stock_code', type_=String)  # 명시적 String 타입
                    )
                    
                    # 쿼리 실행
                    result = await self.db.execute(
                        stmt,
                        {
                            "embedding": embedding_str,  # 문자열 변환된 임베딩
                            "stock_code": stock_code
                        }
                    )
                    similar_queries = result.fetchall()
                    
                    # 유사도 확인 및 최상위 결과 선택
                    cache_hit = False
                    for row in similar_queries:
                        similarity = row.similarity
                        logger.info(f"유사도 비교: 입력 쿼리 '{query}', DB 쿼리 '{row.query}', 유사도: {similarity:.4f}")
                        # CSV 로그 기록
                        await self._log_similarity_to_csv(datetime.utcnow(), query, row.query, similarity)
                        
                        if similarity >= self.similarity_threshold:  # 코사인 유사도는 
                            query_cache_id = row.id
                            
                            # 결과 조회
                            results_stmt = select(WebSearchResultCache).where(
                                WebSearchResultCache.query_cache_id == query_cache_id
                            )
                            results = await self.db.execute(results_stmt)
                            result_rows = results.scalars().all()
                            
                            if result_rows:
                                # 캐시 히트 업데이트
                                await self.update_hit_count(query_cache_id)
                                
                                # 결과 변환
                                for result_row in result_rows:
                                    cache_hits.append({
                                        "title": result_row.title,
                                        "content": result_row.content,
                                        "url": result_row.url,
                                        "search_query": query,
                                        "similarity_score": similarity
                                    })
                                
                                cache_hit = True
                                logger.info(f"캐시 히트: 쿼리 '{query}', 유사도: {similarity:.4f}")
                                break
                    
                    if not cache_hit:
                        cache_misses.append(query)
                        logger.info(f"캐시 미스: 쿼리 '{query}'")
                        
                except Exception as e:
                    logger.error(f"쿼리 '{query}' 캐시 확인 중 오류 발생: {str(e)}", exc_info=True)
                    cache_misses.append(query)
            
            return cache_hits, cache_misses
            
        finally:
            # 임베딩 서비스 정리
            await embedding_service.aclose()
        
    async def save_to_cache(self, query: str, results: List[Dict[str, Any]], stock_code: Optional[str] = None, stock_name: Optional[str] = None) -> None:
        """
        검색 쿼리와 결과를 캐시에 저장합니다.
        
        Args:
            query: 검색 쿼리
            results: 검색 결과 목록
            stock_code: 종목 코드
            stock_name: 종목 이름
        """
        if not query or not results:
            return
            
        try:
            # 임베딩 서비스 초기화
            embedding_service = EmbeddingService(model_type=EmbeddingModelType.OPENAI_3_LARGE)
            
            try:
                # 쿼리 임베딩 생성
                query_embedding = await embedding_service.create_single_embedding_async(query)
                
                # 쿼리 캐시 저장
                query_cache = WebSearchQueryCache(
                    query=query,
                    stock_code=stock_code,
                    stock_name=stock_name,
                    embedding=query_embedding,
                    created_at=datetime.utcnow(),
                    hit_count=0
                )
                
                self.db.add(query_cache)
                await self.db.flush()
                
                # 결과 캐시 저장
                for result in results:
                    result_cache = WebSearchResultCache(
                        query_cache_id=query_cache.id,
                        title=result.get("title"),
                        content=result.get("content"),
                        url=result.get("url"),
                        search_query=result.get("search_query", query),
                        search_date=datetime.utcnow()
                    )
                    self.db.add(result_cache)
                
                await self.db.commit()
                logger.info(f"쿼리 '{query}' 및 {len(results)} 개의 결과가 캐시에 저장됨")
                
            finally:
                # 임베딩 서비스 정리
                await embedding_service.aclose()
                
        except Exception as e:
            await self.db.rollback()
            logger.error(f"쿼리 '{query}' 캐시 저장 중 오류 발생: {str(e)}", exc_info=True)
        
    async def update_hit_count(self, query_cache_id: int) -> None:
        """
        캐시 히트 카운트를 증가시키고, 마지막 히트 시간을 업데이트합니다.
        
        Args:
            query_cache_id: 쿼리 캐시 ID
        """
        try:
            stmt = (
                update(WebSearchQueryCache)
                .where(WebSearchQueryCache.id == query_cache_id)
                .values(
                    hit_count=WebSearchQueryCache.hit_count + 1,
                    last_hit_at=datetime.utcnow()
                )
            )
            await self.db.execute(stmt)
            await self.db.commit()
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"캐시 히트 카운트 업데이트 중 오류 발생 (ID: {query_cache_id}): {str(e)}", exc_info=True)
        
    async def cleanup_old_cache(self, max_age_days: int = 15, exclude_min_hits: int = 5) -> int:
        """
        오래된 캐시 항목을 정리합니다.
        
        Args:
            max_age_days: 최대 보관 일수 (기본값: 15일)
            exclude_min_hits: 이 값 이상의 히트 카운트를 가진 항목은 보존
            
        Returns:
            삭제된 항목 수
        """
        try:
            # max_age_days일 전 날짜 계산
            cutoff_date = datetime.utcnow() - datetime.timedelta(days=max_age_days)
            
            # 삭제 대상 쿼리 ID 조회
            stmt = select(WebSearchQueryCache.id).where(
                WebSearchQueryCache.created_at < cutoff_date,
                WebSearchQueryCache.hit_count < exclude_min_hits
            )
            result = await self.db.execute(stmt)
            query_ids = [row[0] for row in result.fetchall()]
            
            if not query_ids:
                logger.info(f"삭제할 오래된 캐시 항목이 없습니다 (기준: {max_age_days}일 이상, 히트 {exclude_min_hits} 미만)")
                return 0
            
            # 삭제 쿼리 실행 (결과는 cascade로 자동 삭제)
            delete_stmt = (
                text("DELETE FROM stockeasy.web_search_query_cache WHERE id = ANY(:ids)")
                .bindparams(ids=query_ids)
            )
            result = await self.db.execute(delete_stmt)
            await self.db.commit()
            
            deleted_count = len(query_ids)
            logger.info(f"{deleted_count}개의 오래된 캐시 항목 삭제 완료 (기준: {max_age_days}일 이상, 히트 {exclude_min_hits} 미만)")
            return deleted_count
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"캐시 정리 중 오류 발생: {str(e)}", exc_info=True)
            return 0 