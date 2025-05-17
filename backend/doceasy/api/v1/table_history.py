from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from common.core.database import get_db_async
from doceasy.services.table_history import TableHistoryService
from doceasy.schemas.table_response import TableResponse, TableColumn, TableHeader, TableCell
from doceasy.schemas.table_history import TableHistoryList
from loguru import logger

router = APIRouter(prefix="/table-history", tags=["table-history"])

# logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)  # 디버그 로깅 활성화

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
        # histories = await service.get_by_project(project_id)
        
        # # 같은 header(title과 prompt)를 가진 항목들을 그룹화
        # grouped_histories = {}
        # for history in histories:
        #     key = (history.title, history.prompt)
        #     if key not in grouped_histories:
        #         grouped_histories[key] = []
            
        #     grouped_histories[key].append(
        #         TableCell(
        #             doc_id=str(history.document_id),
        #             content=history.result
        #         )
        #     )
        
        # # 그룹화된 데이터를 TableResponse 형식으로 변환
        # columns = [
        #     TableColumn(
        #         header=TableHeader(
        #             name=title,
        #             prompt=prompt
        #         ),
        #         cells=cells
        #     )
        #     for (title, prompt), cells in grouped_histories.items()
        # ]
        # DB에서 그룹화된 데이터 가져오기
        grouped_data = await service.get_grouped_by_project(project_id)
        
        # TableResponse 형식으로 변환
        columns = [
            TableColumn(
                header=TableHeader(
                    name=item['header']['name'],
                    prompt=item['header']['prompt']
                ),
                cells=[
                    TableCell(
                        doc_id=str(cell['doc_id']),
                        content=cell['content']
                    )
                    for cell in item['cells']
                ]
            )
            for item in grouped_data
        ]
        
        return TableResponse(columns=columns)
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