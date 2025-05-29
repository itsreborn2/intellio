"""Tavily API 직접 호출 서비스."""

import os
import aiohttp
import asyncio
import requests
import csv
import json
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from common.core.config import settings

class TavilyService:
    """Tavily API 직접 호출 서비스."""

    def __init__(self, tavily_api_key: Optional[str] = None):
        """Tavily API 서비스 초기화.

        Args:
            tavily_api_key: Tavily API 키. None인 경우 환경 변수에서 가져옵니다.
        """
        self.tavily_api_key = tavily_api_key or settings.TAVILY_API_KEY
        if not self.tavily_api_key:
            raise ValueError("Tavily API 키가 필요합니다. 환경 변수 TAVILY_API_KEY를 설정하거나 초기화할 때 전달하세요.")
        
        self.base_url = "https://api.tavily.com"
        self.search_endpoint = "/search"

    def search(
        self,
        query: str,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        search_depth: Optional[Literal["basic", "advanced"]] = "basic",
        include_images: Optional[bool] = False,
        time_range: Optional[Literal["day", "week", "month", "year"]] = None,
        topic: Optional[Literal["general", "news", "finance"]] = "general",
        max_results: Optional[int] = 5,
        include_answer: Optional[Union[bool, Literal["basic", "advanced"]]] = False,
        include_raw_content: Optional[bool] = False,
        include_image_descriptions: Optional[bool] = False
    ) -> Dict[str, Any]:
        """Tavily 검색 API를 직접 호출하여 결과를 가져옵니다.

        Args:
            query: 검색 쿼리
            include_domains: 검색 결과에 포함할 도메인 목록
            exclude_domains: 검색 결과에서 제외할 도메인 목록
            search_depth: 검색 깊이 ('basic' 또는 'advanced')
            include_images: 이미지 포함 여부
            time_range: 검색 기간 ('day', 'week', 'month', 'year')
            topic: 검색 주제 ('general', 'news', 'finance')
            max_results: 최대 검색 결과 수
            include_answer: 쿼리에 대한 답변 포함 여부
            include_raw_content: 원본 콘텐츠 포함 여부
            include_image_descriptions: 이미지 설명 포함 여부

        Returns:
            Dict[str, Any]: 검색 결과
        """
        url = f"{self.base_url}{self.search_endpoint}"
        
        # API 요청 데이터 구성
        data = {
            "query": query,
        }
        
        # 선택적 파라미터 추가
        if include_domains:
            data["include_domains"] = include_domains
        if exclude_domains:
            data["exclude_domains"] = exclude_domains
        if search_depth:
            data["search_depth"] = search_depth
        if include_images is not None:
            data["include_images"] = include_images
        if time_range:
            data["time_range"] = time_range
        if topic:
            data["topic"] = topic
        if max_results:
            data["max_results"] = max_results
        if include_answer is not None:
            data["include_answer"] = include_answer
        if include_raw_content is not None:
            data["include_raw_content"] = include_raw_content
        if include_image_descriptions is not None:
            data["include_image_descriptions"] = include_image_descriptions
        
        # API 요청 헤더
        headers = {
            "Authorization": f"Bearer {self.tavily_api_key}",
            "Content-Type": "application/json"
        }
        
        # API 요청 및 응답 처리
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()  # 오류 발생 시 예외 발생
        
        return response.json()

    async def search_async(
        self,
        query: str,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        search_depth: Optional[Literal["basic", "advanced"]] = "basic",
        include_images: Optional[bool] = False,
        time_range: Optional[Literal["day", "week", "month", "year"]] = None,
        topic: Optional[Literal["general", "news", "finance"]] = "general",
        max_results: Optional[int] = 5,
        include_answer: Optional[Union[bool, Literal["basic", "advanced"]]] = False,
        include_raw_content: Optional[bool] = False,
        include_image_descriptions: Optional[bool] = False,
        session: Optional[aiohttp.ClientSession] = None
    ) -> Dict[str, Any]:
        """Tavily 검색 API를 비동기적으로 호출하여 결과를 가져옵니다.

        Args:
            query: 검색 쿼리
            include_domains: 검색 결과에 포함할 도메인 목록
            exclude_domains: 검색 결과에서 제외할 도메인 목록
            search_depth: 검색 깊이 ('basic' 또는 'advanced')
            include_images: 이미지 포함 여부
            time_range: 검색 기간 ('day', 'week', 'month', 'year')
            topic: 검색 주제 ('general', 'news', 'finance')
            max_results: 최대 검색 결과 수
            include_answer: 쿼리에 대한 답변 포함 여부
            include_raw_content: 원본 콘텐츠 포함 여부
            include_image_descriptions: 이미지 설명 포함 여부
            session: 기존 aiohttp 세션 (선택적)

        Returns:
            Dict[str, Any]: 검색 결과
        """
        url = f"{self.base_url}{self.search_endpoint}"
        
        # API 요청 데이터 구성
        data = {
            "query": query,
        }
        
        # 선택적 파라미터 추가
        if include_domains:
            data["include_domains"] = include_domains
        if exclude_domains:
            data["exclude_domains"] = exclude_domains
        if search_depth:
            data["search_depth"] = search_depth
        if include_images is not None:
            data["include_images"] = include_images
        if time_range:
            data["time_range"] = time_range
        if topic:
            data["topic"] = topic
        if max_results:
            data["max_results"] = max_results
        if include_answer is not None:
            data["include_answer"] = include_answer
        if include_raw_content is not None:
            data["include_raw_content"] = include_raw_content
        if include_image_descriptions is not None:
            data["include_image_descriptions"] = include_image_descriptions
        
        # API 요청 헤더
        headers = {
            "Authorization": f"Bearer {self.tavily_api_key}",
            "Content-Type": "application/json"
        }
        
        # 세션 관리
        should_close_session = False
        if session is None:
            # 고성능 커넥터 설정
            connector = aiohttp.TCPConnector(
                limit=300,              # 전체 최대 연결 수 (기본: 100)
                limit_per_host=60,      # 호스트당 최대 연결 수 (기본: 30)
                ttl_dns_cache=300,      # DNS 캐시 TTL (5분)
                use_dns_cache=True,     # DNS 캐시 사용
                enable_cleanup_closed=True,  # 닫힌 연결 자동 정리
                force_close=False,      # keep-alive 연결 유지
                keepalive_timeout=30    # keep-alive 타임아웃 (30초)
            )
            session = aiohttp.ClientSession(connector=connector)
            should_close_session = True
        
        try:
            # 비동기 API 요청 및 응답 처리
            async with session.post(url, json=data, headers=headers) as response:
                response.raise_for_status()  # 오류 발생 시 예외 발생
                result = await response.json()
                
                # API 사용량 기록
                await self._log_tavily_usage(
                    query=query,
                    result=result,
                    include_domains=include_domains,
                    exclude_domains=exclude_domains,
                    search_depth=search_depth,
                    include_images=include_images,
                    time_range=time_range,
                    topic=topic,
                    max_results=max_results,
                    include_answer=include_answer,
                    include_raw_content=include_raw_content,
                    include_image_descriptions=include_image_descriptions
                )
                
                return result
        finally:
            # 세션을 이 메서드에서 생성한 경우에만 닫습니다
            if should_close_session:
                await session.close()

    async def _log_tavily_usage(
        self,
        query: str,
        result: Dict[str, Any],
        **kwargs
    ) -> None:
        """Tavily API 사용량을 CSV 파일로 기록합니다.
        
        Args:
            query: 검색 쿼리
            result: API 응답 결과
            **kwargs: 요청에 사용된 기타 파라미터들
        """
        try:
            # 파일 I/O 작업을 별도 스레드에서 실행하기 위한 함수 정의
            def write_to_csv() -> str:
                # CSV 파일 경로 설정
                csv_dir = os.path.join('stockeasy', 'local_cache', 'web_search')
                os.makedirs(csv_dir, exist_ok=True)
                
                date_str = datetime.now().strftime('%Y%m%d')
                csv_path = os.path.join(csv_dir, f'tavily_usage_{date_str}.csv')
                
                # 현재 날짜와 시간
                current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # 파라미터 정보를 문자열로 변환
                params_str = json.dumps(kwargs, ensure_ascii=False)
                response_str = json.dumps(result, ensure_ascii=False)
                
                # CSV 파일 존재 여부 확인 및 헤더 작성
                file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
                
                with open(csv_path, 'a', encoding='utf-8-sig', newline='') as csv_file:
                    fieldnames = ['datetime', 'query', 'parameters', 'response']
                    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                    
                    # 파일이 새로 생성되는 경우 헤더 작성
                    if not file_exists:
                        writer.writeheader()
                    
                    # 데이터 기록
                    writer.writerow({
                        'datetime': current_datetime,
                        'query': query,
                        'parameters': params_str,
                        'response': response_str[:500]
                    })
                
                return csv_path
            
            # 파일 I/O 작업을 별도 스레드에서 비동기적으로 실행
            csv_path = await asyncio.to_thread(write_to_csv)
            
            print(f"  💾 Tavily API 사용량이 CSV 파일에 기록되었습니다: {csv_path}")
            
        except Exception as e:
            print(f"  ⚠️ Tavily API 사용량 기록 중 오류 발생: {str(e)}")

    async def batch_search_async(
        self,
        queries: List[str],
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        search_depth: Optional[Literal["basic", "advanced"]] = "basic",
        include_images: Optional[bool] = False,
        time_range: Optional[Literal["day", "week", "month", "year"]] = None,
        topic: Optional[Literal["general", "news", "finance"]] = "general",
        max_results: Optional[int] = 5,
        include_answer: Optional[Union[bool, Literal["basic", "advanced"]]] = False,
        include_raw_content: Optional[bool] = False,
        include_image_descriptions: Optional[bool] = False
    ) -> List[Dict[str, Any]]:
        """여러 쿼리에 대해 Tavily 검색 API를 단일 비동기 세션에서 병렬로 호출합니다.
        
        Args:
            queries: 검색 쿼리 목록
            include_domains: 검색 결과에 포함할 도메인 목록
            exclude_domains: 검색 결과에서 제외할 도메인 목록
            search_depth: 검색 깊이 ('basic' 또는 'advanced')
            include_images: 이미지 포함 여부
            time_range: 검색 기간 ('day', 'week', 'month', 'year')
            topic: 검색 주제 ('general', 'news', 'finance')
            max_results: 최대 검색 결과 수
            include_answer: 쿼리에 대한 답변 포함 여부
            include_raw_content: 원본 콘텐츠 포함 여부
            include_image_descriptions: 이미지 설명 포함 여부
            
        Returns:
            List[Dict[str, Any]]: 각 쿼리별 검색 결과와 쿼리 정보가 포함된 결과 목록
        """
        # 고성능 커넥터 설정
        connector = aiohttp.TCPConnector(
            limit=300,              # 전체 최대 연결 수 (기본: 100)
            limit_per_host=60,      # 호스트당 최대 연결 수 (기본: 30)
            ttl_dns_cache=300,      # DNS 캐시 TTL (5분)
            use_dns_cache=True,     # DNS 캐시 사용
            enable_cleanup_closed=True,  # 닫힌 연결 자동 정리
            force_close=False,      # keep-alive 연결 유지
            keepalive_timeout=30    # keep-alive 타임아웃 (30초)
        )
        
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = []
            
            for query in queries:
                task = self.search_async(
                    query=query,
                    include_domains=include_domains,
                    exclude_domains=exclude_domains,
                    search_depth=search_depth,
                    include_images=include_images,
                    time_range=time_range,
                    topic=topic,
                    max_results=max_results,
                    include_answer=include_answer,
                    include_raw_content=include_raw_content,
                    include_image_descriptions=include_image_descriptions,
                    session=session  # 동일한 세션 재사용
                )
                tasks.append(task)
            
            # 모든 태스크 동시 실행
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 처리 및 형식 지정
            processed_results = []
            for i, (query, result) in enumerate(zip(queries, results)):
                if isinstance(result, Exception):
                    # 오류 발생 시 빈 결과 반환
                    continue
                    
                # 각 결과에 검색 쿼리 정보 추가
                for item in result.get('results', []):
                    processed_item = {
                        "title": item.get("title", "제목 없음"),
                        "content": item.get("content", "내용 없음"), 
                        "url": item.get("url", "링크 없음"),
                        "search_query": query,
                    }
                    processed_results.append(processed_item)
            
            return processed_results
