"""RAG 서비스"""

import logging
from typing import Dict, Any, List, Union
from uuid import UUID
import pandas as pd

from openai import AsyncOpenAI

from app.core.config import settings
from app.services.embedding import EmbeddingService
from app.models.document import Document
from app.schemas.table_response import TableHeader, TableCell, TableColumn, TableResponse
import asyncio
from sqlalchemy import select

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
    """RAG 서비스 초기화"""
    CHAT_SYSTEM_MSG = (
        "다음 규칙을 따라 응답을 작성하세요:\n\n"
        "1. 가독성을 위한 형식\n"
        "- 주요 구분점에서만 빈 줄 사용\n"
        "- 하위 항목들은 줄바꿈만 사용하고 빈 줄 없음\n"
        "- 목록 들여쓰기 규칙:\n"
        "  • 최상위 항목은 들여쓰기 없이 시작 ('•')\n"
        "  • 2단계 항목은 2칸 들여쓰기 ('-')\n"
        "  • 3단계 항목은 4칸 들여쓰기 ('·')\n"
        "  • 금액, 수치 등의 정보는 해당 항목과 동일 선상에 배치\n\n"
        "2. 특수 표시 규칙:\n"
        "- 증가/긍정적 금액: <mp>금액</mp> 형식으로 표시 (파란색)\n"
        "- 감소/부정적 금액: <mn>금액</mn> 형식으로 표시 (빨간색)\n"
        "- 기본/중립적 금액: <m>금액</m> 형식으로 표시 (검정색 볼드)\n"
        "- 증가/상승 수치: <np>수치</np> 형식으로 표시 (파란색)\n"
        "- 감소/하락 수치: <nn>수치</nn> 형식으로 표시 (빨간색)\n"
        "- 기본/목표 수치: <n>수치</n> 형식으로 표시 (검정색 볼드)\n"
        "- 제목은 '# 제목:' 형식으로 표시\n"
        "- 중요 구분점은 '>' 사용\n"
        "- 핵심 키워드는 '[키워드]' 형식으로 표시\n"
        "- 결론/요약은 '※' 기호로 시작\n\n"
        "3. 내용 작성\n"
        "- 문서의 내용에만 기반하여 답변\n"
        "- 관련 내용이 없다면 '관련 내용이 문서에 없습니다'로 응답\n"
        "- 불확실한 내용은 추측하지 않음\n"
        "- 본문 내용은 그대로 반환하되 사용자의 요청이 있기 전까진 한국어로 응답\n\n"
        "4. 응답 구조화\n"
        "- 분석/요약이 필요한 경우 제목-내용-결론 형식으로 구성\n"
        "- 복잡한 내용은 단계별로 구분하여 설명"
    )
    
    TABLE_HEADER_SYSTEM_MSG = """
사용자의 자연어 명령을 2-3단어로 된 간단한 헤더로 변환하세요.

규칙:
1. 반드시 2-3단어로 구성된 헤더만 생성
2. 헤더는 명사형으로 끝나야 함
3. 명령의 핵심 의미를 포함해야 함
4. 불필요한 조사나 어미 제거

예시:
입력: "피고가 어떤 주장을 하고 있는지 정리해서 보여주세요"
답변: 피고주장

입력: "손해배상 청구액이 얼마인지 알려주시겠어요?"
답변: 손해배상액

입력: "원고 측에서 요구하는 사항들을 정리해주시겠습니까?"
답변: 원고요구사항

입력: "이 사건의 쟁점이 무엇인지 간단히 알려주세요"
답변: 주요쟁점
"""

    TABLE_CONTENT_SYSTEM_MSG = (
        "주어진 문서에서 지정된 항목에 대한 내용을 추출하세요. "
        "다음 규칙을 반드시 따르세요:\n"
        "1. 항목에 정확히 대응하는 내용만 추출\n"
        "2. 문서에 없는 내용은 '내용없음'으로 표시\n"
        "3. 추측이나 해석 없이 원문의 내용만 사용\n"
        "4. 내용은 간단명료하게 정리"
    )

    def __init__(self):
        """RAG 서비스 초기화"""
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.embedding_service = EmbeddingService()
        self.model = "gpt-3.5-turbo"  # 기본 모델
        self.db = None  # DB 세션을 저장할 속성 추가

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

    async def extract_table_headers(self, query: str) -> str:
        """사용자의 자연어 쿼리를 2-3단어의 헤더로 변환"""
        try:
            messages = [
                {"role": "system", "content": self.TABLE_HEADER_SYSTEM_MSG},
                {"role": "user", "content": query}
            ]
            
            completion = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.0
            )
            
            header = completion.choices[0].message.content.strip()
            logger.info(f"생성된 헤더: {header}")
            
            return header
            
        except Exception as e:
            logger.error(f"헤더 추출 중 오류 발생: {str(e)}")
            raise

    async def _fill_table_cell(self, query: str, header: str, document_id: str) -> str:
        """테이블 셀의 내용을 채웁니다."""
        try:
            # 1. 문서의 청크들을 가져옵니다
            chunks = await self.embedding_service.get_document_chunks(document_id)
            if not chunks:
                logger.warning(f"문서 {document_id}의 청크를 찾을 수 없습니다")
                return "분석중..."

            # 2. 청크의 텍스트를 하나로 합칩니다
            full_text = "\n".join(chunk["text"] for chunk in chunks)
            if not full_text:
                logger.warning(f"문서 {document_id}의 텍스트가 비어있습니다")
                return "분석중..."

            # 3. GPT를 사용하여 내용을 추출합니다
            system_prompt = """주어진 문서에서 지정된 항목에 대한 내용을 추출하세요. 다음 규칙을 반드시 따르세요:
1. 항목에 정확히 대응하는 내용만 추출
2. 문서에 없는 내용은 '내용없음'으로 표시
3. 추측이나 해석 없이 원문의 내용만 사용
4. 내용은 간단명료하게 정리"""

            user_prompt = f"""
문서 내용:
{full_text}

추출할 항목: {header}
추출할 내용: {query}
"""
            logger.info(f"문서 {document_id} 내용 길이: {len(full_text)} 문자")
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0
            )
            
            content = response.choices[0].message.content
            logger.info(f"문서 {document_id} 추출 결과: {content[:100]}...")
            return content

        except Exception as e:
            logger.error(f"테이블 셀 내용 추출 중 오류: {str(e)}")
            return "오류 발생"

    async def search_table(self, query: str, doc_ids: List[str]) -> TableResponse:
        """테이블 형식으로 문서 검색"""
        try:
            # 1. 기본 DataFrame 생성
            df = pd.DataFrame({
                'doc_id': doc_ids
            })
            
            # 2. 헤더 추출
            header = await self.extract_table_headers(query)
            
            # 3. 병렬로 각 문서의 내용 추출
            async def process_document(doc_id: str) -> str:
                return await self._fill_table_cell(query, header, doc_id)
            
            # 병렬 처리로 모든 문서 분석
            contents = await asyncio.gather(*[
                process_document(doc_id) for doc_id in doc_ids
            ])
            
            # 4. DataFrame에 결과 추가
            df[header] = contents
            
            # 5. TableResponse 형식으로 변환
            cells = [
                TableCell(doc_id=row['doc_id'], content=row[header])
                for _, row in df.iterrows()
            ]
            
            column = TableColumn(
                header=TableHeader(
                    name=header,
                    prompt=""
                ),
                cells=cells
            )
            
            return TableResponse(columns=[column])
            
        except Exception as e:
            logger.error(f"테이블 검색 중 오류 발생: {str(e)}")
            raise

    async def _handle_table_mode(self, query: str, document_ids: List[str] = None) -> TableResponse:
        """테이블 모드 처리"""
        try:
            # 1. 문서 조회
            result = await self.db.execute(
                select(Document)
                .where(Document.id.in_(document_ids))
                .order_by(Document.created_at)
            )
            documents = result.scalars().all()
            
            if not documents:
                logger.warning("No documents found")
                return TableResponse(columns=[])

            # 2. 쿼리에 대한 새 컬럼 생성
            header = await self.extract_table_headers(query)
            logger.info(f"생성된 헤더: {header}")
            
            # 3. 각 문서에 대해 병렬로 내용 추출
            tasks = []
            for doc in documents:
                # 문서 상태 및 임베딩 ID 확인
                embedding_ids = doc.embedding_ids.split(',') if doc.embedding_ids else []
                logger.info(f"문서 {doc.id} 상태: {doc.status}, 임베딩 수: {len(embedding_ids)}")
                
                # 문서가 완료 상태이고 임베딩이 있는 경우에만 내용 추출
                if doc.status == 'COMPLETED' and embedding_ids:
                    logger.info(f"문서 {doc.id} 내용 추출 시작")
                    task = asyncio.create_task(self._fill_table_cell(query, header, str(doc.id)))
                    tasks.append((doc.id, task))
                else:
                    logger.info(f"문서 {doc.id} 처리 중... (상태: {doc.status}, 임베딩: {'있음' if embedding_ids else '없음'})")
                    tasks.append((doc.id, asyncio.create_task(asyncio.sleep(0, result="분석중..."))))
            
            # 병렬 실행 및 결과 수집
            cell_contents = {}
            for doc_id, task in tasks:
                try:
                    content = await task
                    cell_contents[doc_id] = content
                    if content != "분석중...":
                        logger.info(f"문서 {doc_id} 내용 추출 완료: {content[:100]}...")
                except Exception as e:
                    logger.error(f"문서 {doc_id} 처리 중 오류 발생: {str(e)}")
                    cell_contents[doc_id] = "처리 중 오류 발생"
            
            # 4. 쿼리 컬럼 생성
            query_column = TableColumn(
                header=TableHeader(
                    name=header,
                    prompt=""
                ),
                cells=[
                    TableCell(doc_id=str(doc.id), content=cell_contents[doc.id])
                    for doc in documents
                ]
            )
            
            # 5. 쿼리 컬럼만 반환
            logger.info("테이블 응답 생성 완료")
            return TableResponse(columns=[query_column])
            
        except Exception as e:
            logger.error(f"테이블 모드 처리 중 오류 발생: {str(e)}")
            raise

    async def _handle_chat_mode(self, query: str, top_k: int = 5, document_ids: List[str] = None) -> Dict[str, Any]:
        """채팅 모드 처리"""
        try:
            # 1. 유사 문서 검색 (특정 문서 ID들로 제한)
            similar_chunks = await self.embedding_service.search_similar(
                query=query,
                top_k=top_k,
                document_ids=document_ids
            )
            
            if not similar_chunks:
                return {
                    "answer": "관련 내용이 문서에 없습니다.",
                    "context": []
                }

            # 2. 컨텍스트 준비
            context_texts = [
                f"[Score: {chunk['score']:.2f}] {chunk['text']}"  
                for chunk in similar_chunks
            ]
            context_str = "\n\n".join(context_texts)
            
            # 3. Chat 응답 생성
            user_msg = (
                f"Question: {query}\n\n"
                f"Context:\n{context_str}\n\n"
                "Please answer based on this context."
            )
            
            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.CHAT_SYSTEM_MSG},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.7,
            )
            
            answer = response.choices[0].message.content
            
            return {
                "answer": answer.strip(),
                "context": [
                    {"text": chunk["text"], "score": chunk["score"]}  
                    for chunk in similar_chunks
                ]
            }
            
        except Exception as e:
            logger.error(f"채팅 모드 처리 중 오류 발생: {str(e)}")
            raise

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
            return await self._handle_table_mode(query, document_ids=document_ids)
        return await self._handle_chat_mode(query, 5, document_ids=document_ids)
