from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.table_history import TableHistoryService
from app.schemas.table_response import TableResponse, TableColumn, TableHeader, TableCell
from app.schemas.table_history import TableHistoryList
import logging

router = APIRouter(prefix="/table-history", tags=["table-history"])

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # 디버그 로깅 활성화

#table-histories/project/${projectId}`,GET
@router.get("/project/{project_id}", response_model=TableResponse)
async def get_project_table_histories(
    project_id: str,
    db: AsyncSession = Depends(get_db)
) -> TableResponse:
    """프로젝트별 테이블 히스토리 조회"""
    logger.warn(f"project_id: {project_id}")
    service = TableHistoryService(db)
    histories = await service.get_by_project(project_id)
    
    # TableResponse 형식으로 변환
    return TableResponse(
        columns=[
            TableColumn(
                header=TableHeader(
                    name=history.title,
                    prompt=history.prompt
                ),
                cells=[
                    TableCell(
                        doc_id=str(history.document_id),
                        content=history.result
                    )
                ]
            )
            for history in histories
        ]
    )

@router.get("/document/{document_id}", response_model=TableHistoryList)
async def get_document_histories(
    document_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """문서별 테이블 히스토리 조회"""
    service = TableHistoryService(db)
    histories = await service.get_by_document(document_id)
    return TableHistoryList(items=histories) 