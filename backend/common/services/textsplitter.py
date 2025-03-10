from llama_index.core.node_parser import SentenceWindowNodeParser, SemanticSplitterNodeParser
from llama_index.embeddings.openai import OpenAIEmbedding
from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter,
    TokenTextSplitter,
)
from common.core.config import settings
from typing import List, Optional
import os

from loguru import logger

# tiktoken 및 transformers 임포트 추가
import tiktoken
try:
    from transformers import AutoTokenizer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

# 로컬 kf-deberta 모델 경로 설정
LOCAL_KF_DEBERTA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "external", "kf-deberta")


class TextSplitter:


    """텍스트 분할을 처리하는 클래스
    
    환경 변수 TEXT_SPLITTER에 따라 적절한 text splitter를 선택하여 사용합니다.
    지원하는 splitter 타입:
    - recursive: RecursiveCharacterTextSplitter
    - recursive_tiktoken: tiktoken 토크나이저를 사용한 RecursiveCharacterTextSplitter
    - recursive_kf_deberta: 로컬 kf-deberta 토크나이저를 사용한 RecursiveCharacterTextSplitter
    - recursive_huggingface: HuggingFace 토크나이저를 사용한 RecursiveCharacterTextSplitter
    - character: CharacterTextSplitter
    - token: TokenTextSplitter
    - semantic: SemanticChunker (의미 기반 분할)
    - sentence: SentenceWindowNodeParser (문장 윈도우 기반 분할)
    """
    
    def __init__(self, splitter_type:Optional[str]=None, chunk_size:Optional[int]=None, chunk_overlap:Optional[int]=None, 
                 tokenizer_name:Optional[str]=None):
        
        # 환경변수에서 기본값 로드
        default_splitter = settings.TEXT_SPLITTER
        default_chunk_size = settings.CHUNK_SIZE
        default_chunk_overlap = settings.CHUNK_OVERLAP
        
        # 파라미터로 전달된 값이 있으면 사용하고, 없으면 환경변수 값 사용
        self.splitter_type = splitter_type.lower() if splitter_type else default_splitter
        self.chunk_size = chunk_size if chunk_size else default_chunk_size
        self.chunk_overlap = chunk_overlap if chunk_overlap else default_chunk_overlap
        self.tokenizer_name = tokenizer_name
        
        # 디버그를 위한 상세 로깅 추가
        logger.info(f"초기화 값 타입 확인:")
        logger.info(f"chunk_size type: {type(self.chunk_size)}, value: {self.chunk_size}")
        logger.info(f"chunk_overlap type: {type(self.chunk_overlap)}, value: {self.chunk_overlap}")
        
        logger.info(f"TEXT_SPLITTER : {self.splitter_type}, CHUNK_SIZE : {self.chunk_size}, CHUNK_OVERLAP : {self.chunk_overlap}, [ProcessID: {os.getpid()}]")

        # splitter 초기화 전에 값 검증 추가
        if not isinstance(self.chunk_size, int) or not isinstance(self.chunk_overlap, int):
            logger.error(f"Invalid type - chunk_size: {type(self.chunk_size)}, chunk_overlap: {type(self.chunk_overlap)}")
            self.chunk_size = int(self.chunk_size) if isinstance(self.chunk_size, str) else self.chunk_size
            self.chunk_overlap = int(self.chunk_overlap) if isinstance(self.chunk_overlap, str) else self.chunk_overlap
        
        # splitter 초기화
        if self.splitter_type == "recursive":
            self.splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=["\n\n", "\n", ".", "。", "!", "?", "！", "？", ",", "，", ";", "；", ":", "：", ")", "）", "]", "』", "》", "」", "}", "、", " ", ""],
                keep_separator=True,
                is_separator_regex=False
            )
        elif self.splitter_type == "recursive_tiktoken":
            # tiktoken 토크나이저를 사용한 RecursiveCharacterTextSplitter
            encoding_name = self.tokenizer_name or "cl100k_base"  # 기본값으로 GPT-4 토크나이저 사용
            
            try:
                # tiktoken 인코딩 객체 생성
                tiktoken.get_encoding(encoding_name)
                
                self.splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                    encoding_name=encoding_name,
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    separators=["\n\n", "\n", ".", "。", "!", "?", "！", "？", ",", "，", ";", "；", ":", "：", ")", "）", "]", "』", "》", "」", "}", "、", " ", ""],
                    keep_separator=True,
                    is_separator_regex=False
                )
                logger.info(f"tiktoken 토크나이저 초기화 성공: {encoding_name}")
            except Exception as e:
                logger.error(f"tiktoken 토크나이저 초기화 실패: {str(e)}")
                # 실패 시 기본 RecursiveCharacterTextSplitter로 폴백
                self.splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    separators=["\n\n", "\n", ".", "。", "!", "?", "！", "？", ",", "，", ";", "；", ":", "：", ")", "）", "]", "』", "》", "」", "}", "、", " ", ""],
                    keep_separator=True,
                    is_separator_regex=False
                )
        elif self.splitter_type == "recursive_kf_deberta":
            # 로컬 kf-deberta 토크나이저를 사용한 RecursiveCharacterTextSplitter
            if not TRANSFORMERS_AVAILABLE:
                logger.error("transformers 패키지가 설치되어 있지 않습니다. 기본 RecursiveCharacterTextSplitter를 사용합니다.")
                self.splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    separators=["\n\n", "\n", ".", "。", "!", "?", "！", "？", ",", "，", ";", "；", ":", "：", ")", "）", "]", "』", "》", "」", "}", "、", " ", ""],
                    keep_separator=True,
                    is_separator_regex=False
                )
            else:
                try:
                    # 로컬 kf-deberta 토크나이저 초기화
                    logger.info(f"로컬 kf-deberta 토크나이저 초기화 시작: {LOCAL_KF_DEBERTA_PATH}")
                    
                    # 로컬 경로 존재 확인
                    if not os.path.exists(LOCAL_KF_DEBERTA_PATH):
                        logger.error(f"로컬 kf-deberta 경로가 존재하지 않습니다: {LOCAL_KF_DEBERTA_PATH}")
                        raise FileNotFoundError(f"로컬 kf-deberta 경로가 존재하지 않습니다: {LOCAL_KF_DEBERTA_PATH}")
                    
                    # 로컬 모델 로드
                    tokenizer = AutoTokenizer.from_pretrained(LOCAL_KF_DEBERTA_PATH)
                    
                    # HuggingFace 토크나이저를 사용한 RecursiveCharacterTextSplitter 생성
                    self.splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
                        tokenizer=tokenizer,
                        chunk_size=self.chunk_size,
                        chunk_overlap=self.chunk_overlap,
                        separators=["\n\n", "\n", ".", "。", "!", "?", "！", "？", ",", "，", ";", "；", ":", "：", ")", "）", "]", "』", "》", "」", "}", "、", " ", ""],
                        keep_separator=True,
                        is_separator_regex=False
                    )
                    logger.info(f"로컬 kf-deberta 토크나이저 초기화 성공")
                except Exception as e:
                    logger.error(f"로컬 kf-deberta 토크나이저 초기화 실패: {str(e)}")
                    logger.error(f"기본 RecursiveCharacterTextSplitter로 폴백합니다.")
                    # 실패 시 기본 RecursiveCharacterTextSplitter로 폴백
                    self.splitter = RecursiveCharacterTextSplitter(
                        chunk_size=self.chunk_size,
                        chunk_overlap=self.chunk_overlap,
                        separators=["\n\n", "\n", ".", "。", "!", "?", "！", "？", ",", "，", ";", "；", ":", "：", ")", "）", "]", "』", "》", "」", "}", "、", " ", ""],
                        keep_separator=True,
                        is_separator_regex=False
                    )
        elif self.splitter_type == "recursive_huggingface":
            # HuggingFace 토크나이저를 사용한 RecursiveCharacterTextSplitter
            if not TRANSFORMERS_AVAILABLE:
                logger.error("transformers 패키지가 설치되어 있지 않습니다. 기본 RecursiveCharacterTextSplitter를 사용합니다.")
                self.splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    separators=["\n\n", "\n", ".", "。", "!", "?", "！", "？", ",", "，", ";", "；", ":", "：", ")", "）", "]", "』", "》", "」", "}", "、", " ", ""],
                    keep_separator=True
                )
            else:
                # 한국어에 특화된 토크나이저 모델 (기본값)
                # 지원되는 한국어 특화 모델:
                # - "klue/roberta-base": KLUE 프로젝트의 한국어 RoBERTa 모델
                # - "klue/bert-base": KLUE 프로젝트의 한국어 BERT 모델
                # - "beomi/KcELECTRA-base": 한국어에 최적화된 ELECTRA 모델
                # - "kykim/bert-kor-base": 한국어 BERT 모델
                # - "kykim/electra-kor-base": 한국어 ELECTRA 모델
                # - "monologg/koelectra-base-v3-discriminator": 한국어 ELECTRA v3 모델
                # - "jinmang2/kpfbert": 한국어 뉴스 도메인 BERT 모델
                # - "snunlp/KR-ELECTRA-discriminator": 한국어 ELECTRA 모델
                # - "tunib/electra-ko-base": 한국어 ELECTRA 모델
                # - "lassl/kf-deberta-base": 한국어에 최적화된 DeBERTa 모델
                model_name = self.tokenizer_name or "lassl/kf-deberta-base"  # 기본값을 kf-deberta로 변경
                
                try:
                    # HuggingFace 토크나이저 초기화
                    logger.info(f"HuggingFace 토크나이저 초기화 시작: {model_name}")
                    tokenizer = AutoTokenizer.from_pretrained(model_name)
                    
                    # HuggingFace 토크나이저를 사용한 RecursiveCharacterTextSplitter 생성
                    self.splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
                        tokenizer=tokenizer,
                        chunk_size=self.chunk_size,
                        chunk_overlap=self.chunk_overlap,
                        separators=["\n\n", "\n", ".", "。", "!", "?", "！", "？", ",", "，", ";", "；", ":", "：", ")", "）", "]", "』", "》", "」", "}", "、", " ", ""],
                        keep_separator=True,
                        is_separator_regex=False
                    )
                    logger.info(f"HuggingFace 토크나이저 초기화 성공: {model_name}")
                except Exception as e:
                    logger.error(f"HuggingFace 토크나이저 초기화 실패: {str(e)}")
                    logger.error(f"기본 RecursiveCharacterTextSplitter로 폴백합니다.")
                    # 실패 시 기본 RecursiveCharacterTextSplitter로 폴백
                    self.splitter = RecursiveCharacterTextSplitter(
                        chunk_size=self.chunk_size,
                        chunk_overlap=self.chunk_overlap,
                        separators=["\n\n", "\n", ".", "。", "!", "?", "！", "？", ",", "，", ";", "；", ":", "：", ")", "）", "]", "』", "》", "」", "}", "、", " ", ""],
                        keep_separator=True
                    )
        elif self.splitter_type == "character":
            self.splitter = CharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separator="\n"
            )
        elif self.splitter_type == "token":
            self.splitter = TokenTextSplitter(
                encoding_name="cl100k_base", #필수.
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                disallowed_special=()
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
        if self.splitter_type == "sentencewindow":
            # SentenceWindowNodeParser는 다른 인터페이스를 사용하므로 별도 처리
            from llama_index.core import Document
            doc = Document(text=text)
            nodes = self.splitter.get_nodes_from_documents([doc])
            return [node.get_content() for node in nodes]
        elif self.splitter_type == "semantic_llama":
            # SemanticSplitterNodeParser는 Document 객체를 입력으로 받음
            from llama_index.core import Document
            doc = Document(text=text)
            nodes = self.splitter.get_nodes_from_documents([doc])
            return [node.get_content() for node in nodes]
        
        # 그외 다른 text splitter는 LangChain 기본 인터페이스를 사용하므로 별도 처리 안함.
        return self.splitter.split_text(text)
