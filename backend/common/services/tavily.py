"""Tavily API 직접 호출 서비스."""

import os
import aiohttp
import requests
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
        include_image_descriptions: Optional[bool] = False
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
        
        # 비동기 API 요청 및 응답 처리
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as response:
                response.raise_for_status()  # 오류 발생 시 예외 발생
                result = await response.json()
                
                return result
