from typing import List
from langchain.text_splitter import RecursiveCharacterTextSplitter

class DocumentChunker:
    """문서 텍스트를 청크로 분할하는 클래스"""
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: List[str] = ["\n\n", "\n", " ", ""]
    ):
        """
        Args:
            chunk_size (int): 각 청크의 최대 크기 (문자 수)
            chunk_overlap (int): 청크 간 중복되는 문자 수
            separators (List[str]): 텍스트 분할에 사용할 구분자 목록
        """
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len,
            is_separator_regex=False
        )
    
    def create_chunks(self, text: str) -> List[str]:
        """
        텍스트를 청크로 분할
        
        Args:
            text (str): 분할할 텍스트
            
        Returns:
            List[str]: 분할된 텍스트 청크 목록
        """
        if not text:
            return []
            
        # 텍스트 전처리
        text = self._preprocess_text(text)
        
        # 청크 생성
        chunks = self.text_splitter.split_text(text)
        
        # 청크 후처리
        chunks = [self._postprocess_chunk(chunk) for chunk in chunks]
        
        return [chunk for chunk in chunks if chunk]  # 빈 청크 제거
    
    def _preprocess_text(self, text: str) -> str:
        """텍스트 전처리"""
        if not text:
            return ""
            
        # 연속된 공백 제거
        text = " ".join(text.split())
        
        # 불필요한 특수문자 제거 또는 변환
        text = text.replace("\t", " ")
        text = text.replace("\r", "\n")
        
        # 연속된 줄바꿈 정리
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")
            
        return text.strip()
    
    def _postprocess_chunk(self, chunk: str) -> str:
        """청크 후처리"""
        if not chunk:
            return ""
            
        # 앞뒤 공백 제거
        chunk = chunk.strip()
        
        # 최소 길이 확인 (너무 짧은 청크 제거)
        if len(chunk) < 10:  # 최소 10자
            return ""
            
        return chunk
