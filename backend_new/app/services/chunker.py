from typing import List, Callable
from langchain.text_splitter import RecursiveCharacterTextSplitter

class DocumentChunker:
    """문서 텍스트를 청크로 분할하는 클래스"""
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100,
        max_chunk_size: int = 2000,
        adaptive_size: bool = True,
        separators: List[str] = ["\n\n", "\n", ".", " ", ""]
    ):
        """
        Args:
            chunk_size (int): 각 청크의 기본 크기 (문자 수)
            chunk_overlap (int): 청크 간 중복되는 문자 수
            min_chunk_size (int): 최소 청크 크기
            max_chunk_size (int): 최대 청크 크기
            adaptive_size (bool): 문서 특성에 따른 청크 크기 자동 조정 여부
            separators (List[str]): 텍스트 분할에 사용할 구분자 목록
        """
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.adaptive_size = adaptive_size
        self.base_chunk_size = chunk_size
        
        # 문서 특성에 따른 청크 크기 조정
        if adaptive_size:
            self.text_splitter = self._create_adaptive_splitter(chunk_size, chunk_overlap, separators)
        else:
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=separators,
                length_function=len,
                is_separator_regex=False
            )
    
    def _create_adaptive_splitter(self, chunk_size: int, chunk_overlap: int, separators: List[str]):
        """문서 특성에 따라 적응형 청크 분할기 생성"""
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len,
            is_separator_regex=False,
            chunk_size_function=self._adaptive_chunk_size
        )
    
    def _adaptive_chunk_size(self, text: str) -> int:
        """문서 특성에 따라 청크 크기 동적 조정"""
        # 문장 길이 분석
        sentences = text.split('.')
        avg_sentence_length = sum(len(s.strip()) for s in sentences) / max(len(sentences), 1)
        
        # 문단 분석
        paragraphs = text.split('\n\n')
        avg_paragraph_length = sum(len(p.strip()) for p in paragraphs) / max(len(paragraphs), 1)
        
        # 청크 크기 조정
        if avg_sentence_length > 100:  # 긴 문장이 많은 경우
            chunk_size = min(self.max_chunk_size, self.base_chunk_size * 1.5)
        elif avg_paragraph_length < 200:  # 짧은 문단이 많은 경우
            chunk_size = max(self.min_chunk_size, self.base_chunk_size * 0.7)
        else:
            chunk_size = self.base_chunk_size
            
        return int(chunk_size)
    
    def create_chunks(self, text: str, title: str = None) -> List[dict]:
        """
        텍스트를 청크로 분할
        
        Args:
            text (str): 분할할 텍스트
            title (str, optional): 문서 제목
            
        Returns:
            List[dict]: 분할된 텍스트 청크와 메타데이터 목록
        """
        if not text:
            return []
            
        # 텍스트 전처리
        text = self._preprocess_text(text)
        
        # 청크 생성
        chunks = self.text_splitter.split_text(text)
        
        # 청크 후처리
        chunks = [self._postprocess_chunk(chunk) for chunk in chunks]
        chunks = [chunk for chunk in chunks if chunk]  # 빈 청크 제거
        
        # 메타데이터 추가
        result = []
        for i, chunk in enumerate(chunks):
            chunk_data = {
                "content": chunk,
                "metadata": {
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "title": title  # 제목을 메타데이터에 포함
                }
            }
            result.append(chunk_data)
        
        return result
    
    def _preprocess_text(self, text: str) -> str:
        """텍스트 전처리
        
        Args:
            text (str): 전처리할 텍스트
            
        Returns:
            str: 전처리된 텍스트
        """
        if not text:
            return ""
            
        # 1. 특수문자 정규화
        text = self._normalize_special_chars(text)
        
        # 2. 문장 경계 보존
        text = self._preserve_sentence_boundaries(text)
        
        # 3. 표 구조 보존
        text = self._preserve_table_structure(text)
        
        # 4. 숫자/날짜 포맷 통일
        text = self._normalize_numbers_dates(text)
        
        return text.strip()
        
    def _normalize_special_chars(self, text: str) -> str:
        """특수문자 정규화"""
        import re
        
        # 1. HTML 태그 제거
        text = re.sub(r'<[^>]+>', '', text)
        
        # 2. 이모지 및 특수 유니코드 제거
        text = text.encode('ascii', 'ignore').decode('ascii')
        
        # 3. 연속된 공백 정규화
        text = ' '.join(text.split())
        
        # 4. 기본 특수문자 변환
        replacements = {
            '\t': ' ',    # 탭을 공백으로
            '\r': '\n',   # 캐리지 리턴을 개행으로
            '…': '...',   # 말줄임표 통일
            '․': '.',     # 가운뎃점을 마침표로
            '·': '.',     # 가운뎃점을 마침표로
            '˙': '.',     # 가운뎃점을 마침표로
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
            
        return text
        
    def _preserve_sentence_boundaries(self, text: str) -> str:
        """문장 경계 보존"""
        import re
        
        # 1. 문장 끝 공백 정리
        text = re.sub(r'\s*\.\s*', '. ', text)
        
        # 2. 문장 시작 공백 정리
        text = re.sub(r'\s+([가-힣A-Za-z])', r' \1', text)
        
        # 3. 연속된 마침표 정리
        text = re.sub(r'\.{2,}', '...', text)
        
        # 4. 문장 끝 표기 통일
        text = re.sub(r'[\!?]+', '.', text)
        
        return text
        
    def _preserve_table_structure(self, text: str) -> str:
        """표 구조 보존"""
        import re
        
        # 1. 표 구분자 보존
        text = text.replace('|', ' | ')
        
        # 2. 표 헤더 구분선 처리
        text = re.sub(r'\-{3,}', '---', text)
        
        # 3. 표 셀 내부 공백 정리
        text = re.sub(r'\|\s+', '| ', text)
        text = re.sub(r'\s+\|', ' |', text)
        
        return text
        
    def _normalize_numbers_dates(self, text: str) -> str:
        """숫자와 날짜 포맷 통일"""
        import re
        
        # 1. 숫자 포맷 통일 (천단위 구분자)
        text = re.sub(r'(\d),(\d)', r'\1\2', text)  # 1,234 -> 1234
        
        # 2. 날짜 포맷 통일
        # YYYY.MM.DD, YYYY-MM-DD, YYYY/MM/DD -> YYYY-MM-DD
        text = re.sub(r'(\d{4})[./년](\d{1,2})[./월](\d{1,2})[일]?', r'\1-\2-\3', text)
        
        # 3. 시간 포맷 통일
        text = re.sub(r'(\d{1,2}):(\d{2}):(\d{2})', r'\1:\2:\3', text)
        text = re.sub(r'(\d{1,2}):(\d{2})', r'\1:\2', text)
        
        return text
        
    def _postprocess_chunk(self, chunk: str) -> str:
        """청크 후처리"""
        if not chunk:
            return ""
            
        # 앞뒤 공백 제거
        chunk = chunk.strip()
        
        # 최소 길이 확인 (너무 짧은 청크 제거)
        if len(chunk) < self.min_chunk_size:
            return ""
            
        return chunk
