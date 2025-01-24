
#from llama_index.node_parser.text import SentenceWindowNodeParser
#import llama_index.core.node_parser
from llama_index.core.node_parser import SentenceWindowNodeParser, SemanticSplitterNodeParser
from llama_index.embeddings.openai import OpenAIEmbedding
from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter,
    TokenTextSplitter,
    SentenceTransformersTokenTextSplitter
)
#from langchain_text_splitters import SemanticChunker
from typing import List, Optional
import os

from dotenv import load_dotenv

class TextSplitter:
    """텍스트 분할을 처리하는 클래스
    
    환경 변수 TEXT_SPLITTER에 따라 적절한 text splitter를 선택하여 사용합니다.
    지원하는 splitter 타입:
    - recursive: RecursiveCharacterTextSplitter
    - character: CharacterTextSplitter
    - token: TokenTextSplitter
    - semantic: SemanticChunker (의미 기반 분할)
    - sentence: SentenceWindowNodeParser (문장 윈도우 기반 분할)
    """
    
    def __init__(self, splitter_type:Optional[str]=None, chunk_size:Optional[int]=1000, chunk_overlap:Optional[int]=200):
        load_dotenv()
        if splitter_type is None:
            self.splitter_type = os.getenv("TEXT_SPLITTER", "recursive").lower()
            self.chunk_size = int(os.getenv("CHUNK_SIZE", "1000"))
            self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "200"))
        else:
            self.splitter_type = splitter_type.lower()
            self.chunk_size = chunk_size
            self.chunk_overlap = chunk_overlap
        
        
        # splitter 초기화
        if self.splitter_type == "recursive":
            self.splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap
            )
        elif self.splitter_type == "character":
            self.splitter = CharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap
            )
        elif self.splitter_type == "token":
            self.splitter = TokenTextSplitter(
                encoding_name="cl100k_base", #필수.
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap
            )
        elif self.splitter_type == "semantic_llama":
            # 임베딩 모델 초기화
            embed_model = OpenAIEmbedding(model="text-embedding-ada-002")

            # SemanticSplitter 초기화
            self.splitter = SemanticSplitterNodeParser(
                buffer_size=1,  # 문장 그룹화 크기
                breakpoint_percentile_threshold=95,  # 분할 임계값
                embed_model=embed_model
            )
        elif self.splitter_type == "sentencewindow":
            self.splitter = SentenceWindowNodeParser.from_defaults(
                window_size=3, #각 문장을 중심으로 포함할 이전 및 이후 문장의 개수, 기본값3
                window_metadata_key="window",
                original_text_metadata_key="original_text",
                #sentence_splitter=split_by_sentence_tokenizer #문서를 문장 단위로 분리하는 함수 또는 객체를 지정
            )
            
        else:
            raise ValueError(f"Unsupported text splitter type: {self.splitter_type}")
    
    def split_text(self, text: str) -> List[str]:
        """텍스트를 청크로 분할합니다.

        Args:
            text (str): 분할할 텍스트

        Returns:
            List[str]: 분할된 텍스트 청크 리스트
        """
        if self.splitter_type == "sentence":
            # SentenceWindowNodeParser는 다른 인터페이스를 사용하므로 별도 처리
            nodes = self.splitter.get_nodes_from_documents([text])
            return [node.get_content() for node in nodes]
        elif self.splitter_type == "semantic_llama":
            # SemanticSplitterNodeParser는 Document 객체를 입력으로 받음
            from llama_index.core import Document
            doc = Document(text=text)
            nodes = self.splitter.get_nodes_from_documents([doc])
            return [node.get_content() for node in nodes]
        
        # 그외 다른 text splitter는 LangChain 기본 인터페이스를 사용하므로 별도 처리 안함.
        return self.splitter.split_text(text)
