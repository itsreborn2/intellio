from typing import List, Dict, Optional
from dataclasses import dataclass
import re
import nltk
from loguru import logger
from app.services.llm import LLMService

@dataclass
class ChunkMetadata:
    """청크 메타데이터"""
    doc_type: str                  # 문서 타입 (earnings_call, technical_doc 등)
    section_type: str              # 섹션 타입 (introduction, qa, summary 등)
    importance: int                # 중요도 (1-10)
    key_terms: List[str]          # 핵심 키워드
    entities: Dict[str, List[str]] # 발견된 엔티티 (사람, 조직 등)
    context_needed: bool          # 인접 청크 문맥 필요 여부
    info_density: int             # 정보 밀도 (1-10)
    position: Dict[str, int]      # 문서 내 위치 정보

@dataclass
class Chunk:
    """청크 데이터"""
    content: str
    metadata: ChunkMetadata
    original_text: str            # 최적화 전 원본 텍스트

class RAGOptimizedChunker:
    def __init__(
        self,
        llm_service: LLMService,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        min_chunk_size: int = 100
    ):
        self.llm_service = llm_service
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = chunk_size
        
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')

    async def _analyze_document_structure(self, text: str) -> Dict:
        """문서 구조 분석"""
        sections = []
        lines = text.split('\n')
        current_section = None
        current_section_start = 0
        
        # 섹션 패턴 정의
        section_patterns = {
            'header': r'.*Corporation.*Earnings Call.*\d{4}',
            'summary': r'.*회계연도.*분기.*실적.*요약',
            'qa_start': r'Q&A|질의.*응답|Question.*Answer',
            'qa_question': r'^Q:|질문:|Question:',
            'qa_answer': r'^A:|답변:|Answer:'
        }
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # 헤더 섹션 확인
            if re.match(section_patterns['header'], line):
                if current_section:
                    sections.append({
                        'type': current_section,
                        'start': current_section_start,
                        'end': i,
                        'importance': 8 if current_section == 'qa' else 5
                    })
                current_section = 'header'
                current_section_start = i
                continue
                
            # 요약 섹션 확인
            if re.match(section_patterns['summary'], line):
                if current_section:
                    sections.append({
                        'type': current_section,
                        'start': current_section_start,
                        'end': i,
                        'importance': 8 if current_section == 'qa' else 5
                    })
                current_section = 'summary'
                current_section_start = i
                continue
                
            # Q&A 섹션 시작 확인
            if re.match(section_patterns['qa_start'], line):
                if current_section:
                    sections.append({
                        'type': current_section,
                        'start': current_section_start,
                        'end': i,
                        'importance': 8 if current_section == 'qa' else 5
                    })
                current_section = 'qa'
                current_section_start = i
                continue
                
            # Q&A 내의 질문/답변 구분
            if current_section == 'qa':
                if re.match(section_patterns['qa_question'], line):
                    if i > current_section_start + 1:  # 이전 Q&A 쌍이 있으면 저장
                        sections.append({
                            'type': 'qa',
                            'start': current_section_start,
                            'end': i,
                            'importance': 8
                        })
                    current_section_start = i
                
            # 아직 섹션이 없으면 본문으로 시작
            if not current_section:
                current_section = 'content'
                current_section_start = i
        
        # 마지막 섹션 추가
        if current_section:
            sections.append({
                'type': current_section,
                'start': current_section_start,
                'end': len(lines),
                'importance': 8 if current_section == 'qa' else 5
            })
        
        # 문서 타입 결정
        doc_type = 'earnings_call'  # 현재는 earnings_call만 처리
        
        # 엔티티 추출 (실제로는 더 정교한 분석 필요)
        entities = {
            'people': [],
            'organizations': ['NVIDIA', 'NVIDIA Corporation'],
            'topics': ['실적', 'AI', '데이터센터', '게임']
        }
        
        # 청킹 전략 설정
        chunking_strategy = {
            'size': self.chunk_size,
            'preserve': ['qa', 'header', 'summary']  # 이 섹션들은 분할하지 않음
        }
        
        return {
            'doc_type': doc_type,
            'sections': sections,
            'entities': entities,
            'chunking_strategy': chunking_strategy
        }

    def _create_base_chunks(self, text: str, doc_structure: Dict) -> List[Chunk]:
        """기본 청크 생성
        
        Args:
            text (str): 원본 문서 텍스트
            doc_structure (Dict): 문서 구조 분석 결과
            
        Returns:
            List[Chunk]: 생성된 기본 청크 리스트
        """
        chunks = []
        lines = text.split('\n')
        current_pos = 0
        
        # 문서 구조에 따라 청크 생성
        for section in doc_structure["sections"]:
            section_start = section["start"]
            section_end = section["end"]
            section_text = '\n'.join(lines[section_start:section_end]).strip()
            
            if not section_text:
                continue
                
            # 섹션 타입에 따른 청크 크기 조정
            if section["type"] in doc_structure["chunking_strategy"]["preserve"]:
                # 보존해야 할 섹션은 전체를 하나의 청크로
                chunks.append(
                    Chunk(
                        content=section_text,
                        metadata=ChunkMetadata(
                            doc_type=doc_structure["doc_type"],
                            section_type=section["type"],
                            importance=section["importance"],
                            key_terms=[],
                            entities=doc_structure["entities"],
                            context_needed=False,
                            info_density=5,
                            position={
                                "start": current_pos,
                                "end": current_pos + len(section_text)
                            }
                        ),
                        original_text=section_text
                    )
                )
                current_pos += len(section_text)
            else:
                # 일반 섹션은 크기에 맞게 분할
                sentences = nltk.sent_tokenize(section_text)
                current_chunk = []
                current_chunk_size = 0
                
                for sentence in sentences:
                    sentence_len = len(sentence)
                    
                    # 현재 청크가 비어있고 문장이 최대 크기보다 큰 경우
                    if not current_chunk and sentence_len > self.chunk_size:
                        # 긴 문장을 강제로 분할
                        words = sentence.split()
                        temp_chunk = []
                        temp_size = 0
                        
                        for word in words:
                            word_len = len(word) + 1  # 공백 포함
                            if temp_size + word_len > self.chunk_size and temp_chunk:
                                chunk_text = ' '.join(temp_chunk)
                                chunks.append(
                                    Chunk(
                                        content=chunk_text,
                                        metadata=ChunkMetadata(
                                            doc_type=doc_structure["doc_type"],
                                            section_type=section["type"],
                                            importance=section["importance"],
                                            key_terms=[],
                                            entities=doc_structure["entities"],
                                            context_needed=True,
                                            info_density=5,
                                            position={
                                                "start": current_pos,
                                                "end": current_pos + len(chunk_text)
                                            }
                                        ),
                                        original_text=chunk_text
                                    )
                                )
                                current_pos += len(chunk_text)
                                temp_chunk = []
                                temp_size = 0
                            temp_chunk.append(word)
                            temp_size += word_len
                            
                        if temp_chunk:
                            chunk_text = ' '.join(temp_chunk)
                            chunks.append(
                                Chunk(
                                    content=chunk_text,
                                    metadata=ChunkMetadata(
                                        doc_type=doc_structure["doc_type"],
                                        section_type=section["type"],
                                        importance=section["importance"],
                                        key_terms=[],
                                        entities=doc_structure["entities"],
                                        context_needed=True,
                                        info_density=5,
                                        position={
                                            "start": current_pos,
                                            "end": current_pos + len(chunk_text)
                                        }
                                    ),
                                    original_text=chunk_text
                                )
                            )
                            current_pos += len(chunk_text)
                    
                    # 일반적인 경우
                    elif current_chunk_size + sentence_len <= self.chunk_size:
                        current_chunk.append(sentence)
                        current_chunk_size += sentence_len
                    else:
                        # 현재 청크가 가득 차면 저장
                        if current_chunk:
                            chunk_text = ' '.join(current_chunk)
                            chunks.append(
                                Chunk(
                                    content=chunk_text,
                                    metadata=ChunkMetadata(
                                        doc_type=doc_structure["doc_type"],
                                        section_type=section["type"],
                                        importance=section["importance"],
                                        key_terms=[],
                                        entities=doc_structure["entities"],
                                        context_needed=True,
                                        info_density=5,
                                        position={
                                            "start": current_pos,
                                            "end": current_pos + len(chunk_text)
                                        }
                                    ),
                                    original_text=chunk_text
                                )
                            )
                            current_pos += len(chunk_text)
                            
                        # 새로운 청크 시작
                        current_chunk = [sentence]
                        current_chunk_size = sentence_len
                
                # 마지막 청크 처리
                if current_chunk:
                    chunk_text = ' '.join(current_chunk)
                    chunks.append(
                        Chunk(
                            content=chunk_text,
                            metadata=ChunkMetadata(
                                doc_type=doc_structure["doc_type"],
                                section_type=section["type"],
                                importance=section["importance"],
                                key_terms=[],
                                entities=doc_structure["entities"],
                                context_needed=True,
                                info_density=5,
                                position={
                                    "start": current_pos,
                                    "end": current_pos + len(chunk_text)
                                }
                            ),
                            original_text=chunk_text
                        )
                    )
        
        return chunks

    async def _optimize_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """LLM을 사용하여 청크 최적화
        
        Args:
            chunks (List[Chunk]): 기본 청크 리스트
            
        Returns:
            List[Chunk]: 최적화된 청크 리스트
        """
        # 현재는 단순히 원본 청크 반환
        return chunks

    async def _extract_search_keywords(self, chunk: Chunk) -> List[str]:
        """청크에서 중요 검색 키워드 추출
        
        Args:
            chunk (Chunk): 분석할 청크
            
        Returns:
            List[str]: 추출된 키워드 리스트
        """
        # 현재는 빈 리스트 반환
        return []

    async def _optimize_info_density(self, chunk: Chunk) -> Chunk:
        """청크의 정보 밀도 최적화
        
        Args:
            chunk (Chunk): 최적화할 청크
            
        Returns:
            Chunk: 최적화된 청크
        """
        # 현재는 원본 청크 반환
        return chunk

    async def _maintain_context(self, chunks: List[Chunk]) -> List[Chunk]:
        """청크 간의 문맥 연결성 유지
        
        Args:
            chunks (List[Chunk]): 처리할 청크 리스트
            
        Returns:
            List[Chunk]: 문맥이 보강된 청크 리스트
        """
        # 현재는 원본 청크 리스트 반환
        return chunks

    async def process_document(self, text: str) -> List[Chunk]:
        """문서 전체 처리 프로세스
        
        Args:
            text (str): 처리할 문서 텍스트
            
        Returns:
            List[Chunk]: 최종 처리된 청크 리스트
        """
        if not text.strip():
            logger.warning("빈 문서가 입력되었습니다.")
            return []
            
        try:
            # 1. 문서 구조 분석
            doc_structure = await self._analyze_document_structure(text)
            if not doc_structure["sections"]:
                logger.warning("문서 구조 분석 결과가 없습니다.")
                return []
            
            # 2. 기본 청크 생성
            base_chunks = self._create_base_chunks(text, doc_structure)
            if not base_chunks:
                logger.warning("기본 청크 생성에 실패했습니다.")
                return []
            
            # 3. 청크 최적화 (선택적)
            optimized_chunks = await self._optimize_chunks(base_chunks)
            if not optimized_chunks:
                logger.warning("청크 최적화에 실패했습니다. 기본 청크를 반환합니다.")
                return base_chunks
            
            # 4. 검색 키워드 추출
            for chunk in optimized_chunks:
                try:
                    keywords = await self._extract_search_keywords(chunk)
                    chunk.metadata.key_terms.extend(keywords)
                except Exception as e:
                    logger.warning(f"키워드 추출 중 오류 발생: {str(e)}")
            
            # 5. 정보 밀도 최적화 (선택적)
            try:
                density_optimized_chunks = []
                for chunk in optimized_chunks:
                    optimized = await self._optimize_info_density(chunk)
                    density_optimized_chunks.append(optimized)
                
                if density_optimized_chunks:
                    optimized_chunks = density_optimized_chunks
            except Exception as e:
                logger.warning(f"정보 밀도 최적화 중 오류 발생: {str(e)}")
            
            # 6. 문맥 연결성 유지 (선택적)
            try:
                final_chunks = await self._maintain_context(optimized_chunks)
                if final_chunks:
                    return final_chunks
            except Exception as e:
                logger.warning(f"문맥 연결성 유지 중 오류 발생: {str(e)}")
            
            return optimized_chunks
            
        except Exception as e:
            logger.error(f"문서 처리 중 오류 발생: {str(e)}")
            raise

    async def create_chunks(self, text: str) -> List[Chunk]:
        """RAG 최적화 청크 생성"""
        if not text.strip():
            return []
            
        # 1. 문서 구조 분석
        doc_structure = await self._analyze_document_structure(text)
        if not doc_structure or "sections" not in doc_structure:
            return []
            
        # 2. 기본 청크 생성
        base_chunks = self._create_base_chunks(text, doc_structure)
        if not base_chunks:
            return []
            
        # 3. 각 청크 최적화
        optimized_chunks = []
        for chunk in base_chunks:
            section = chunk
            context = {
                "doc_type": doc_structure["doc_type"],
                "section_type": section.metadata.section_type,
                "importance": section.metadata.importance
            }
            
            optimized = await self._optimize_chunk_content(
                chunk.content, context
            )
            
            metadata = ChunkMetadata(
                doc_type=doc_structure["doc_type"],
                section_type=section.metadata.section_type,
                importance=section.metadata.importance,
                key_terms=optimized["key_terms"],
                entities={},
                context_needed=optimized["context_needed"],
                info_density=optimized["info_density"],
                position={
                    "start": 0,
                    "end": len(chunk.content)
                }
            )
            
            optimized_chunks.append(
                Chunk(
                    content=optimized["optimized_text"],
                    metadata=metadata,
                    original_text=chunk.content
                )
            )
        
        return optimized_chunks

    async def _optimize_chunk_content(self, chunk: str, context: Dict) -> Dict:
        """청크 내용 최적화"""
        optimize_prompt = """
        다음 텍스트 청크를 RAG 시스템에 맞게 최적화해주세요.

        # 최적화 목표
        1. 검색 가능성 향상
        2. 문맥 정보 보존
        3. 정보 밀도 최적화

        # 문맥 정보:
        {context}

        # 입력 청크:
        {chunk}

        # 응답 형식 (JSON):
        {{
            "optimized_text": "최적화된 텍스트 내용",
            "key_terms": ["핵심", "키워드", "목록"],
            "info_density": 8,           # 정보 밀도 (1-10)
            "context_needed": true       # 문맥 필요 여부
        }}
        """
        
        try:
            result = await self.llm_service.analyze(
                optimize_prompt.format(
                    chunk=chunk,
                    context=context
                )
            )
            if not result or "key_terms" not in result:
                logger.warning("청크 최적화 결과가 올바르지 않습니다")
                return {
                    "optimized_text": chunk,
                    "key_terms": [],
                    "info_density": 5,
                    "context_needed": False
                }
            return result
        except Exception as e:
            logger.warning(f"청크 최적화 실패: {e}")
            return {
                "optimized_text": chunk,
                "key_terms": [],
                "info_density": 5,
                "context_needed": False
            }

    def _split_section(self, text: str, section_info: Dict) -> List[Dict]:
        """섹션을 문장 단위로 분할"""
        if not text.strip():
            return []
            
        try:
            # 단순 줄바꿈 기반 분할로 변경
            sentences = [s.strip() for s in text.split('\n') if s.strip()]
            
            chunks = []
            current_chunk = []
            current_length = 0
            
            for sentence in sentences:
                # 문장이 너무 길면 단어 단위로 분할
                if len(sentence) > self.max_chunk_size:
                    words = sentence.split()
                    temp_chunk = []
                    temp_length = 0
                    
                    for word in words:
                        if temp_length + len(word) + 1 > self.max_chunk_size:
                            if temp_chunk:
                                chunks.append({
                                    "content": " ".join(temp_chunk),
                                    "section_type": section_info["type"],
                                    "importance": section_info.get("importance", 5)
                                })
                            temp_chunk = [word]
                            temp_length = len(word)
                        else:
                            temp_chunk.append(word)
                            temp_length += len(word) + 1
                            
                    if temp_chunk:
                        chunks.append({
                            "content": " ".join(temp_chunk),
                            "section_type": section_info["type"],
                            "importance": section_info.get("importance", 5)
                        })
                        
                # 일반적인 문장 처리
                elif current_length + len(sentence) + 1 > self.max_chunk_size:
                    if current_chunk:
                        chunks.append({
                            "content": " ".join(current_chunk),
                            "section_type": section_info["type"],
                            "importance": section_info.get("importance", 5)
                        })
                    current_chunk = [sentence]
                    current_length = len(sentence)
                else:
                    current_chunk.append(sentence)
                    current_length += len(sentence) + 1
            
            if current_chunk:
                chunks.append({
                    "content": " ".join(current_chunk),
                    "section_type": section_info["type"],
                    "importance": section_info.get("importance", 5)
                })
                
            return chunks if chunks else [{
                "content": text[:self.max_chunk_size],
                "section_type": section_info["type"],
                "importance": section_info.get("importance", 5)
            }]
            
        except Exception as e:
            logger.error(f"섹션 분할 중 오류 발생: {e}")
            # 오류 발생시 전체 텍스트를 하나의 청크로 반환
            return [{
                "content": text[:self.max_chunk_size],
                "section_type": section_info["type"],
                "importance": section_info.get("importance", 5)
            }]