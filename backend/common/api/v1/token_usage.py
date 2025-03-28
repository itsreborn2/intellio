from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import UUID
from common.api.v1.auth import get_current_user
from common.core.deps import get_current_session, get_db
from common.models.user import Session, User
from common.services.token_usage_service import get_token_usage
from common.models.token_usage import ProjectType, TokenType
from loguru import logger

router = APIRouter(prefix="/token-usage", tags=["token-usage"])

@router.get("/")
async def read_token_usage(
    project_type: Optional[str] = Query(None, description="프로젝트 유형 (doceasy, stockeasy)"),
    token_type: Optional[str] = Query(None, description="토큰 유형 (llm, embedding)"),
    start_date: Optional[str] = Query(None, description="시작 날짜 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료 날짜 (YYYY-MM-DD)"),
    group_by: Optional[List[str]] = Query(None, description="그룹화 기준 (project_type, token_type, model_name, day, month)"),
    db: AsyncSession = Depends(get_db),
    session: Session = Depends(get_current_session)
):
    """사용자의 토큰 사용량 조회"""
    try:
        # 세션에서 사용자 ID 가져오기
        if not session or not session.user:
            raise HTTPException(status_code=401, detail="인증되지 않은 사용자입니다.")

        # 날짜 변환
        start_date_obj = None
        end_date_obj = None
        
        if start_date:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            # 종료일은 해당 일자의 마지막 시간으로 설정
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        
        # 프로젝트 유형과 토큰 유형 변환
        project_type_enum = None
        token_type_enum = None
        
        if project_type:
            try:
                project_type_enum = ProjectType(project_type)
            except ValueError:
                raise HTTPException(status_code=400, detail="유효하지 않은 프로젝트 유형입니다.")
        
        if token_type:
            try:
                token_type_enum = TokenType(token_type)
            except ValueError:
                raise HTTPException(status_code=400, detail="유효하지 않은 토큰 유형입니다.")
        
        # 일반 사용자는 자신의 토큰 사용량만 조회 가능
        # 슈퍼유저는 모든 사용자의 토큰 사용량을 조회할 수 있는 기능 추가 가능
        token_usage_data = await get_token_usage(
            db=db,
            user_id=session.user.id,
            project_type=project_type_enum,
            token_type=token_type_enum,
            start_date=start_date_obj,
            end_date=end_date_obj,
            group_by=group_by
        )
        
        return token_usage_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"토큰 사용량 조회 중 오류가 발생했습니다: {str(e)}")

@router.get("/summary")
async def read_token_usage_summary(
    project_type: Optional[str] = Query(None, description="프로젝트 유형 (doceasy, stockeasy)"),
    period: str = Query("month", description="기간 (day, week, month, year)"),
    db: AsyncSession = Depends(get_db),
    session: Session = Depends(get_current_session)
):
    """사용자의 토큰 사용량 요약 조회"""
    try:
        # 세션에서 사용자 ID 가져오기
        if not session or not session.user:
            raise HTTPException(status_code=401, detail="인증되지 않은 사용자입니다.")
        # 현재 날짜
        now = datetime.now()
        logger.info(f"summary")
        
        # 기간에 따른 시작 날짜 계산
        if period == "day":
            start_date_obj = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            # 이번 주 월요일부터
            days_since_monday = now.weekday()
            start_date_obj = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "month":
            # 이번 달 1일부터
            start_date_obj = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == "year":
            # 올해 1월 1일부터
            start_date_obj = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            raise HTTPException(status_code=400, detail="유효하지 않은 기간입니다.")
        
        logger.info(f"start_date_obj : {start_date_obj}")
        # 프로젝트 유형 변환
        project_type_enum = None
        if project_type:
            try:
                project_type_enum = ProjectType(project_type)
            except ValueError:
                raise HTTPException(status_code=400, detail="유효하지 않은 프로젝트 유형입니다.")
        
        # 토큰 사용량 조회
        token_usage_data = await get_token_usage(
            db=db,
            user_id=session.user.id,
            project_type=project_type_enum,
            start_date=start_date_obj,
            end_date=now,
            group_by=["token_type"]
        )
        logger.info(f"token_usage_data : {token_usage_data}")
        
        return {
            "period": period,
            "start_date": start_date_obj.isoformat(),
            "end_date": now.isoformat(),
            "summary": token_usage_data.get("total_summary", {}),
            "token_type_summary": token_usage_data.get("grouped_data", {})
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"토큰 사용량 요약 조회 중 오류가 발생했습니다: {str(e)}") 