"""RAG 서비스"""

from typing import Dict, Any, List, Union
from uuid import UUID
import pandas as pd
import logging
from sqlalchemy import select

from app.core.config import settings
from app.services.embedding import EmbeddingService
from app.services.prompt_manager import PromptManager, PromptMode
from app.models.document import Document
from app.schemas.table_response import TableHeader, TableCell, TableColumn, TableResponse

logger = logging.getLogger(__name__)

# 문서 상태 상수
DOCUMENT_STATUS_REGISTERED = 'REGISTERED'
DOCUMENT_STATUS_UPLOADING = 'UPLOADING'
DOCUMENT_STATUS_UPLOADED = 'UPLOADED'
DOCUMENT_STATUS_PROCESSING = 'PROCESSING'
DOCUMENT_STATUS_COMPLETED = 'COMPLETED'
DOCUMENT_STATUS_PARTIAL = 'PARTIAL'
DOCUMENT_STATUS_ERROR = 'ERROR'
DOCUMENT_STATUS_DELETED = 'DELETED'

class RAGService:
    """RAG 서비스"""
    
    def __init__(self):
        """RAG 서비스 초기화"""
        self.embedding_service = EmbeddingService()
        self.prompt_manager = PromptManager()
        self.db = None

    async def initialize(self, db):
        """DB 세션 초기화"""
        self.db = db

    async def verify_document_access(self, document_id: str) -> bool:
        """문서 접근 권한 확인
        
        Args:
            document_id: 확인할 문서 ID
            
        Returns:
            bool: 접근 가능 여부
        """
        try:
            # 문서 존재 여부 확인
            result = await self.db.execute(
                select(Document)
                .where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            
            if not document:
                logger.warning(f"문서를 찾을 수 없음: {document_id}")
                return False
                
            # 문서 상태 확인
            if document.status not in ['COMPLETED', 'PARTIAL']:
                logger.warning(f"문서가 아직 처리되지 않음: {document_id} (상태: {document.status})")
                return False
            
            # 임베딩 존재 여부 확인
            if not document.embedding_ids:
                logger.warning(f"문서에 임베딩이 없음: {document_id}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"문서 접근 권한 확인 중 오류 발생: {str(e)}", exc_info=True)
            return False

    async def _handle_chat_mode(self, query: str, top_k: int = 5, document_ids: List[str] = None):
        """채팅 모드 처리"""
        try:
            # 관련 문서 검색
            relevant_chunks = await self._get_relevant_chunks(query, top_k, document_ids)
            
            if not relevant_chunks:
                return {
                    "answer": "관련 문서를 찾을 수 없습니다.",
                    "context": []
                }
            
            # 문서 컨텍스트 구성
            doc_contexts = []
            for chunk in relevant_chunks:
                doc_contexts.append(
                    f"문서 ID: {chunk.get('document_id', 'N/A')}\n"
                    f"페이지: {chunk.get('page_number', 'N/A')}\n"
                    f"내용: {chunk.get('text', '')}"
                )
            
            # 프롬프트 체인으로 분석
            chain_response = await self.prompt_manager.process_prompt(
                mode=PromptMode.CHAT,
                context={
                    'query': query,
                    'content': '\n\n'.join(doc_contexts)
                }
            )
            
            return {
                "answer": chain_response,
                "context": relevant_chunks
            }
            
        except Exception as e:
            logger.error(f"채팅 모드 처리 실패: {str(e)}")
            raise

    async def handle_table_mode(self, query: str, document_ids: List[str] = None):
        """테이블 모드 처리"""
        try:
            # 헤더 생성
            header = await self.prompt_manager.process_prompt(
                mode=PromptMode.TABLE_HEADER,
                context={'query': query}
            )
            
            # 관련 문서 검색
            relevant_chunks = await self._get_relevant_chunks(query, top_k=5, document_ids=document_ids)
            
            if not relevant_chunks:
                return TableResponse(columns=[
                    TableColumn(
                        header=TableHeader(name=header, prompt=query),
                        cells=[TableCell(doc_id="1", content="관련 문서를 찾을 수 없습니다.")]
                    )
                ])
            
            # 문서 컨텍스트 구성
            doc_contexts = []
            for chunk in relevant_chunks:
                doc_contexts.append(
                    f"문서 ID: {chunk.get('document_id', 'N/A')}\n"
                    f"페이지: {chunk.get('page_number', 'N/A')}\n"
                    f"내용: {chunk.get('text', '')}"
                )
            
            # 테이블 내용 생성
            content = await self.prompt_manager.process_prompt(
                mode=PromptMode.TABLE,
                context={
                    'query': query,
                    'header': header,
                    'content': '\n\n'.join(doc_contexts)
                }
            )
            
            # TableResponse 형식으로 변환
            return TableResponse(columns=[
                TableColumn(
                    header=TableHeader(name=header, prompt=query),
                    cells=[
                        TableCell(
                            doc_id=chunk.get('document_id', 'N/A'),
                            content=content
                        )
                        for chunk in relevant_chunks[:1]  # 첫 번째 문서만 사용
                    ]
                )
            ])
            
        except Exception as e:
            logger.error(f"테이블 모드 처리 실패: {str(e)}")
            raise

    async def _get_relevant_chunks(self, query: str, top_k: int = 5, document_ids: List[str] = None):
        """관련 문서 검색"""
        try:
            # 임베딩 서비스로 관련 문서 검색
            relevant_contexts = await self.embedding_service.search_similar(
                query=query,
                top_k=top_k,
                document_ids=document_ids
            )
            
            if not relevant_contexts:
                return []
            
            return relevant_contexts
            
        except Exception as e:
            logger.error(f"관련 문서 검색 실패: {str(e)}")
            raise

    def _process_table_response(self, header: str, content: str):
        """테이블 응답 처리"""
        try:
            # 데이터 전처리
            content = self._preprocess_table_content(content)
            
            # 청크 사이즈 계산 (약 8000 토큰)
            chunk_size = 12000
            chunks = [content[i:i + chunk_size] for i in range(0, len(content), chunk_size)]
            
            results = []
            for chunk in chunks:
                try:
                    messages = [
                        {"role": "system", "content": self.prompt_manager.get_system_message(PromptMode.TABLE)},
                        {"role": "user", "content": chunk}
                    ]
                    
                    completion = self.prompt_manager.process_prompt(
                        mode=PromptMode.TABLE,
                        context={
                            'query': header,
                            'content': chunk
                        }
                    )
                    
                    result = completion
                    results.append(result)
                    
                except Exception as e:
                    logger.error(f"테이블 셀 내용 추출 중 오류 발생: {str(e)}")
                    continue
                    
            return {
                "columns": [{"name": header, "key": header}],
                "rows": [{"id": "1", header: "\n".join(results)}]
            }
            
        except Exception as e:
            logger.error(f"테이블 응답 처리 실패: {str(e)}")
            raise

    def _preprocess_table_content(self, content: str) -> str:
        """테이블 내용 전처리"""
        # 연속된 공백 제거
        content = content.replace('\n', ' ')
        content = ' '.join(content.split())
        return content.strip()

    async def query(
        self,
        query: str,
        mode: str = "chat",
        document_ids: List[str] = None
    ) -> Union[Dict[str, Any], TableResponse]:
        """쿼리에 대한 응답 생성
        
        Args:
            query: 사용자 쿼리
            mode: 응답 모드 ("chat" 또는 "table")
            document_ids: 테이블 모드에서 사용할 문서 ID 목록
            
        Returns:
            Union[Dict[str, Any], TableResponse]: 모드에 따른 응답
            - chat 모드: {"answer": str, "context": List[Dict]}
            - table 모드: TableResponse 객체
        """
        if mode == "table":
            return await self.handle_table_mode(query, document_ids=document_ids)
        return await self._handle_chat_mode(query, 5, document_ids=document_ids)

    async def get_document_status(self, document_id: str) -> Dict[str, Any]:
        """문서의 상태 조회
        
        Args:
            document_id: 조회할 문서 ID
            
        Returns:
            Dict[str, Any]: 문서 상태 정보
        """
        try:
            # 문서 조회
            result = await self.db.execute(
                select(Document)
                .where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            
            if not document:
                return {
                    "document_id": document_id,
                    "status": "NOT_FOUND",
                    "error_message": "문서를 찾을 수 없습니다",
                    "is_accessible": False
                }
            
            # 접근 가능 여부 확인
            is_accessible = document.status in ['COMPLETED', 'PARTIAL'] and document.embedding_ids
            
            return {
                "document_id": document_id,
                "status": document.status,
                "error_message": document.error_message,
                "is_accessible": is_accessible
            }
            
        except Exception as e:
            logger.error(f"문서 상태 조회 중 오류 발생: {str(e)}", exc_info=True)
            return {
                "document_id": document_id,
                "status": "ERROR",
                "error_message": str(e),
                "is_accessible": False
            }
