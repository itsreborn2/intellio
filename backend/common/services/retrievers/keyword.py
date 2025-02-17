from typing import List, Dict, Optional
from .base import BaseRetriever, RetrieverConfig
from .models import Document, RetrievalResult
from pydantic import BaseModel

from loguru import logger

class KeywordRetrieverConfig(RetrieverConfig):
    """키워드 검색 설정"""
    min_score: float = 0.0  # 최소 매칭 점수
    use_bm25: bool = True   # BM25 알고리즘 사용 여부
    analyzer: str = "korean"  # 형태소 분석기 설정

class KeywordRetriever(BaseRetriever):
    """키워드 기반 검색 구현체"""
    
    def __init__(self, config: KeywordRetrieverConfig):
        super().__init__(config)
        self.config = config
        # TODO: 키워드 검색 엔진 초기화 (예: Elasticsearch, BM25 등)
        
    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict] = None
    ) -> RetrievalResult:
        """키워드 기반 검색 수행"""
        """키워드 기반 검색 수행"""
        try:
            logger.info(f"키워드 검색 시작 - 쿼리: {query}, top_k: {top_k}")

            # 쿼리 정규화
            normalized_query = self._normalize_query(query)
            logger.debug(f"정규화된 쿼리: {normalized_query}")

            # 키워드 추출
            keywords = self._extract_keywords(normalized_query)
            logger.debug(f"추출된 키워드: {keywords}")

            if not keywords:
                logger.warning("추출된 키워드가 없습니다.")
                return RetrievalResult(
                    documents=[],
                    query_analysis={"type": "keyword", "analyzer": self.config.analyzer}
                )

            # 키워드를 사용하여 문서 검색
            # 예시로 임베딩 기반 검색을 사용하며, 필요에 따라 조정 가능
            documents = await self.embedding_service.search_by_keywords(
                keywords=keywords,
                top_k=top_k or 10,
                filters=filters
            )

            logger.info(f"검색된 문서 수: {len(documents)}")

            # 쿼리 분석 정보 구성
            query_analysis = {
                "type": "keyword",
                "analyzer": self.config.analyzer,
                "keywords": keywords,
                "normalized_query": normalized_query
            }

            return RetrievalResult(
                documents=documents,
                query_analysis=query_analysis
            )

        except Exception as e:
            logger.error(f"키워드 검색 중 오류 발생: {str(e)}", exc_info=True)
            return RetrievalResult(
                documents=[],
                query_analysis={"type": "keyword", "analyzer": self.config.analyzer, "error": str(e)}
            )
    
    def _normalize_query(self, query: str) -> str:
        """쿼리 정규화 - rag.py의 정규화 로직 재사용"""
        import re

        # 1. 기본 정규화
        query = re.sub(r'\s+', ' ', query.strip())

        # 2. 날짜 표현 정규화
        query = re.sub(r'(\d{4})년도?', r'\1년', query)
        query = re.sub(r'(\d{1,2})월달?', r'\1월', query)
        query = re.sub(r'(\d{1,2})분기말?', r'\1분기', query)

        # 3. 한국어 특화 표현 통일
        replacements = {
            r'얼마(예요|인가요|인가|야|니|나요)': '얼마입니까',
            r'알려줘': '알려주세요',
            r'보여줘': '보여주세요',
            r'찾아줘': '찾아주세요',
            r'뭐야': '무엇입니까',
            r'뭐니': '무엇입니까',
            r'있니': '있습니까',
            r'없니': '없습니까'
        }

        for pattern, replacement in replacements.items():
            query = re.sub(pattern, replacement, query)

        return query

    def _extract_keywords(self, text: str) -> List[str]:
        """텍스트에서 키워드 추출 - rag.py의 추출 로직 재사용"""
        # 텍스트를 소문자로 변환하고 기본적인 전처리
        text = text.lower()

        # 불용어 정의
        stop_words = {'을', '를', '이', '가', '은', '는', '에', '의', '와', '과', '로', '으로'}

        # 텍스트를 단어로 분리
        words = text.split()

        # 불용어 제거 및 2글자 이상인 단어만 선택
        keywords = [word for word in words if word not in stop_words and len(word) >= 2]

        return keywords

    async def add_documents(self, documents: List[Document]) -> bool:
        """문서를 검색 인덱스에 추가"""
        # TODO: 문서 인덱싱 구현
        return True
        
    async def delete_documents(self, document_ids: List[str]) -> bool:
        """검색 인덱스에서 문서 삭제"""
        # TODO: 문서 삭제 구현
        return True
        
    async def update_documents(self, documents: List[Document]) -> bool:
        """검색 인덱스의 문서 업데이트"""
        # TODO: 문서 업데이트 구현
        return True 