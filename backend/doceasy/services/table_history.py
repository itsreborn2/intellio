from typing import List
from uuid import UUID, uuid4
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from common.core.database import get_db_async
from doceasy.models.table_history import TableHistory
from doceasy.schemas.table_history import TableHistoryCreate, TableHistoryResponse

class TableHistoryService:
    """테이블 히스토리 서비스"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        

    async def create(self, data: TableHistoryCreate) -> TableHistoryResponse:
        """테이블 히스토리 생성 또는 업데이트"""
        # 기존 레코드 조회
        stmt = select(TableHistory).where(
            TableHistory.project_id == data.project_id,
            TableHistory.document_id == data.document_id,
            TableHistory.prompt == data.prompt
        )
        result = await self.db.execute(stmt)
        existing_history = result.scalar_one_or_none()
        
        if existing_history:
            # 기존 레코드 업데이트
            existing_history.title = data.title
            existing_history.result = data.result
            await self.db.commit()
            await self.db.refresh(existing_history)
            return TableHistoryResponse.model_validate(existing_history)
        else:
            # 새 레코드 생성
            table_history = TableHistory(
                id=uuid4(),
                user_id=data.user_id,
                project_id=data.project_id,
                document_id=data.document_id,
                prompt=data.prompt,
                title=data.title,
                result=data.result
            )
            
            self.db.add(table_history)
            await self.db.commit()
            await self.db.refresh(table_history)
            
            return TableHistoryResponse.model_validate(table_history)

    async def create_many(self, data_list: List[TableHistoryCreate]) -> List[TableHistoryResponse]:
        """여러 테이블 히스토리를 한 번에 생성 또는 업데이트"""
        histories = []
        
        for data in data_list:
            # 기존 레코드 조회
            stmt = select(TableHistory).where(
                TableHistory.project_id == data.project_id,
                TableHistory.document_id == data.document_id,
                TableHistory.prompt == data.prompt
            )
            result = await self.db.execute(stmt)
            existing_history = result.scalar_one_or_none()
            
            if existing_history:
                # 기존 레코드 업데이트
                existing_history.title = data.title
                existing_history.result = data.result
                # updated_at은 SQLAlchemy가 자동으로 처리
                histories.append(existing_history)
            else:
                # 새 레코드 생성
                new_history = TableHistory(
                    id=uuid4(),
                    user_id=data.user_id,
                    project_id=data.project_id,
                    document_id=data.document_id,
                    prompt=data.prompt,
                    title=data.title,
                    result=data.result
                )
                self.db.add(new_history)  # add는 await 하지 않음
                histories.append(new_history)
        
        # 한 번에 커밋
        await self.db.commit()
        
        # 모든 히스토리 새로고침
        for history in histories:
            await self.db.refresh(history)
        
        return [TableHistoryResponse.model_validate(history) for history in histories]
    
    async def get_by_project(self, project_id: str) -> List[TableHistoryResponse]:
        """프로젝트별 테이블 히스토리 조회"""
        stmt = (
            select(TableHistory)
            .where(TableHistory.project_id == project_id)
            .order_by(TableHistory.created_at.asc())
        )
        result = await self.db.execute(stmt)
        histories = result.scalars().all()
        return [TableHistoryResponse.model_validate(history) for history in histories]

    async def get_grouped_by_project(self, project_id: str) -> List[dict]:
        """프로젝트별 테이블 히스토리를 그룹화하여 조회"""
        
        # TableHistory 모델의 별칭 생성
        th = aliased(TableHistory)
        
        # 그룹화 쿼리 구성
        stmt = (
            select(
                th.title,
                th.prompt,
                func.json_agg(
                    func.json_build_object(
                        'doc_id', th.document_id,
                        'content', th.result
                    )
                ).label('cells')
            )
            .where(th.project_id == project_id)
            .group_by(th.title, th.prompt)
            .order_by(th.title, th.prompt)
        )
        
        result = await self.db.execute(stmt)
        grouped_data = result.all()
        
        return [
            {
                'header': {'name': row.title, 'prompt': row.prompt},
                'cells': row.cells
            }
            for row in grouped_data
        ]
        
    async def get_by_document(self, document_id: UUID) -> List[TableHistoryResponse]:
        """문서별 테이블 히스토리 조회"""
        stmt = (
            select(TableHistory)
            .where(TableHistory.document_id == document_id)
            .order_by(TableHistory.created_at.asc())
        )
        result = await self.db.execute(stmt)
        histories = result.scalars().all()
        return [TableHistoryResponse.model_validate(history) for history in histories]
