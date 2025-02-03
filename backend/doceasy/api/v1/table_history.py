from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from common.core.database import get_db_async
from doceasy.services.table_history import TableHistoryService
from doceasy.schemas.table_response import TableResponse, TableColumn, TableHeader, TableCell
from doceasy.schemas.table_history import TableHistoryList
import logging

router = APIRouter(prefix="/table-history", tags=["table-history"])

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # 디버그 로깅 활성화

#table-histories/project/${projectId}`,GET
@router.get("/project/{project_id}", response_model=TableResponse)
async def get_project_table_histories(
    project_id: str,
    db: AsyncSession = Depends(get_db_async)
) -> TableResponse:
    """프로젝트별 테이블 히스토리 조회"""
    try:
        logger.info(f"project_id: {project_id}")
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
    except Exception as e:
        logger.error(f"테이블 히스토리 조회 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="테이블 조회에 실패하였습니다")

@router.get("/document/{document_id}", response_model=TableHistoryList)
async def get_document_histories(
    document_id: UUID,
    db: AsyncSession = Depends(get_db_async)
):
    """문서별 테이블 히스토리 조회"""
    service = TableHistoryService(db)
    histories = await service.get_by_document(document_id)
    return TableHistoryList(items=histories) 