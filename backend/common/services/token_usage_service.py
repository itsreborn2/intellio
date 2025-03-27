from uuid import UUID, uuid4
from typing import Optional, Dict, List, Any, ContextManager, Callable, AsyncGenerator
from datetime import datetime
from sqlalchemy import select, func, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session as SQLAlchemySession
import logging
from contextlib import asynccontextmanager, contextmanager

from common.models.token_usage import TokenUsage, ProjectType, TokenType
# 순환 참조를 방지하기 위해 get_db 임포트를 제거하고 지연 임포트를 사용
# from common.core.deps import get_db

logger = logging.getLogger(__name__)

async def save_token_usage(
    db: AsyncSession,
    user_id: UUID,
    project_type: ProjectType,
    token_type: TokenType,
    model_name: str,
    token_data: Dict[str, Any],
    cost: Optional[float] = None
) -> TokenUsage:
    """토큰 사용량 저장

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        project_type: 프로젝트 유형 (doceasy, stockeasy)
        token_type: 토큰 유형 (llm, embedding)
        model_name: 모델 이름
        token_data: 토큰 사용량 데이터
        cost: 비용 (선택사항)

    Returns:
        TokenUsage: 저장된 토큰 사용량 레코드
    """
    try:
        #logger.info(f"[토큰 추적] DB 저장 시작: user_id={user_id}, type={token_type}, model={model_name}")
        
        # 토큰 데이터에서 값 추출
        prompt_tokens = token_data.get("prompt_tokens", 0)
        completion_tokens = token_data.get("completion_tokens", 0) if token_type == TokenType.LLM else None
        total_tokens = token_data.get("total_tokens", 0)
        
        # 비용이 제공되지 않은 경우 token_data에서 가져오기
        if cost is None:
            cost = token_data.get("total_cost", 0.0)
        
        #logger.debug(f"[토큰 추적] 토큰 데이터: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}, cost={cost}")
        
        # TokenUsage 레코드 생성
        token_usage = TokenUsage(
            id=uuid4(),
            user_id=user_id,
            project_type=project_type,
            token_type=token_type,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost
        )
        
        # 데이터베이스에 저장
        db.add(token_usage)
        await db.commit()
        await db.refresh(token_usage)
        
        logger.info(f"[토큰 추적] DB 저장 성공: ID={token_usage.id}, 토큰 합계={total_tokens}")
        return token_usage
    except Exception as e:
        logger.error(f"[토큰 추적] DB 저장 실패: {str(e)}")
        await db.rollback()
        raise

class TokenUsageTracker:
    """토큰 사용량 추적기"""
    
    def __init__(self, user_id: UUID, project_type: ProjectType, token_type: TokenType, model_name: str):
        self.user_id = user_id
        self.project_type = project_type
        self.token_type = token_type
        self.model_name = model_name
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        logger.info(f"[토큰 추적] TokenUsageTracker 생성: user_id={user_id}, type={token_type}, model={model_name}")
        
    def add_tokens(self, prompt_tokens: int, completion_tokens: int = 0, total_tokens: int = None, cost: float = 0.0):
        """토큰 사용량 추가"""
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += total_tokens if total_tokens is not None else (prompt_tokens + completion_tokens)
        self.total_cost += cost
        logger.info(f"[토큰 추적] 토큰 추가: prompt={prompt_tokens}, completion={completion_tokens}, total={self.total_tokens}, cost={self.total_cost}")
        
    async def save(self, db: AsyncSession):
        """기록된 토큰 사용량을 데이터베이스에 저장"""
        token_data = {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens if self.token_type == TokenType.LLM else None,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost
        }
        
        #logger.info(f"[토큰 추적] 토큰 추적기 데이터 저장 요청: {token_data}")
        
        return await save_token_usage(
            db=db,
            user_id=self.user_id,
            project_type=self.project_type,
            token_type=self.token_type,
            model_name=self.model_name,
            token_data=token_data
        )

@asynccontextmanager
async def track_token_usage(
    user_id: UUID, 
    project_type: str, 
    token_type: str, 
    model_name: str,
    db_getter = None
):
    """토큰 사용량을 추적하는 컨텍스트 매니저
    
    사용 예시:
    ```
    async with track_token_usage(user_id, "doceasy", "embedding", "text-embedding-ada-002") as tracker:
        # 임베딩 생성 코드...
        tracker.add_tokens(prompt_tokens=100, cost=0.01)
    # 컨텍스트 종료 시 자동으로 DB에 저장
    ```
    """
    logger.info(f"[토큰 추적] 컨텍스트 매니저 시작: user_id={user_id}, project_type={project_type}, token_type={token_type}")
    tracker = TokenUsageTracker(
        user_id=user_id,
        project_type=ProjectType(project_type),
        token_type=TokenType(token_type),
        model_name=model_name
    )
    
    try:
        yield tracker
        
        # 컨텍스트 종료 시 DB에 저장
        if tracker.total_tokens > 0:
            logger.info(f"[토큰 추적] 컨텍스트 종료 - DB 저장 시작: total_tokens={tracker.total_tokens}")
            try:
                # DB 세션 가져오기
                db = None
                
                # db_getter가 None인 경우 common.core.deps에서 get_db를 지연 임포트
                if db_getter is None:
                    # 지연 임포트
                    logger.debug(f"[토큰 추적] db_getter가 None - 지연 임포트 시도")
                    from common.core.deps import get_db
                    db_getter = get_db
                
                # db_getter가 제너레이터인 경우 (FastAPI Depends 함수)
                if callable(db_getter):
                    logger.debug(f"[토큰 추적] 콜러블 db_getter 사용")
                    async for session in db_getter():
                        db = session
                        break
                else:
                    # 이미 세션인 경우
                    logger.debug(f"[토큰 추적] 기존 세션 사용")
                    db = db_getter
                    
                if db:
                    logger.debug(f"[토큰 추적] DB 세션 획득 성공, tracker.save() 호출")
                    await tracker.save(db)
                else:
                    logger.warning("[토큰 추적] DB 세션을 가져올 수 없어 토큰 사용량을 저장하지 못했습니다.")
            except Exception as e:
                logger.error(f"[토큰 추적] 토큰 사용량 저장 중 오류 발생: {str(e)}")
        else:
            logger.info(f"[토큰 추적] 토큰이 0개이므로 저장하지 않음")
    except Exception as e:
        logger.error(f"[토큰 추적] 토큰 사용량 추적 중 오류 발생: {str(e)}")
        # 예외를 다시 발생시켜 호출자에게 전파
        raise

async def get_token_usage(
    db: AsyncSession,
    user_id: Optional[UUID] = None,
    project_type: Optional[ProjectType] = None,
    token_type: Optional[TokenType] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    group_by: Optional[List[str]] = None
) -> Dict[str, Any]:
    """토큰 사용량 조회

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID (선택사항)
        project_type: 프로젝트 유형 (선택사항)
        token_type: 토큰 유형 (선택사항)
        start_date: 시작 날짜 (선택사항)
        end_date: 종료 날짜 (선택사항)
        group_by: 그룹화 기준 (선택사항) - ['project_type', 'token_type', 'model_name', 'day', 'month']

    Returns:
        Dict[str, Any]: 토큰 사용량 데이터
    """
    try:
        # 쿼리 생성
        query = select(TokenUsage)
        
        # 필터 적용
        if user_id:
            query = query.where(TokenUsage.user_id == user_id)
        if project_type:
            query = query.where(TokenUsage.project_type == project_type)
        if token_type:
            query = query.where(TokenUsage.token_type == token_type)
        if start_date:
            query = query.where(TokenUsage.created_at >= start_date)
        if end_date:
            query = query.where(TokenUsage.created_at <= end_date)
        
        # 쿼리 실행
        result = await db.execute(query)
        token_usages = result.scalars().all()
        
        # 결과 처리
        if not group_by:
            # 그룹화하지 않을 경우 전체 합계 계산
            summary = {
                "total_prompt_tokens": sum(usage.prompt_tokens for usage in token_usages),
                "total_completion_tokens": sum(usage.completion_tokens or 0 for usage in token_usages),
                "total_tokens": sum(usage.total_tokens for usage in token_usages),
                "total_cost": sum(usage.cost for usage in token_usages),
            }
            
            # 프로젝트별 요약
            project_summary = {}
            for project in ProjectType:
                project_tokens = [u for u in token_usages if u.project_type == project]
                if project_tokens:
                    project_summary[project.value] = {
                        "total_prompt_tokens": sum(u.prompt_tokens for u in project_tokens),
                        "total_completion_tokens": sum(u.completion_tokens or 0 for u in project_tokens),
                        "total_tokens": sum(u.total_tokens for u in project_tokens),
                        "total_cost": sum(u.cost for u in project_tokens),
                    }
            
            # 토큰 유형별 요약
            token_type_summary = {}
            for token_type in TokenType:
                type_tokens = [u for u in token_usages if u.token_type == token_type]
                if type_tokens:
                    token_type_summary[token_type.value] = {
                        "total_prompt_tokens": sum(u.prompt_tokens for u in type_tokens),
                        "total_completion_tokens": sum(u.completion_tokens or 0 for u in type_tokens),
                        "total_tokens": sum(u.total_tokens for u in type_tokens),
                        "total_cost": sum(u.cost for u in type_tokens),
                    }
            
            return {
                "token_usages": [
                    {
                        "id": str(usage.id),
                        "user_id": str(usage.user_id),
                        "project_type": usage.project_type.value,
                        "token_type": usage.token_type.value,
                        "model_name": usage.model_name,
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens,
                        "cost": usage.cost,
                        "created_at": usage.created_at.isoformat()
                    } for usage in token_usages
                ],
                "summary": summary,
                "project_summary": project_summary,
                "token_type_summary": token_type_summary
            }
        else:
            # 그룹화 적용
            grouped_data = {}
            
            for usage in token_usages:
                # 그룹 키 생성
                group_key = []
                
                for group_field in group_by:
                    if group_field == 'project_type':
                        group_key.append(f"project:{usage.project_type.value}")
                    elif group_field == 'token_type':
                        group_key.append(f"token:{usage.token_type.value}")
                    elif group_field == 'model_name':
                        group_key.append(f"model:{usage.model_name}")
                    elif group_field == 'day':
                        group_key.append(f"day:{usage.created_at.strftime('%Y-%m-%d')}")
                    elif group_field == 'month':
                        group_key.append(f"month:{usage.created_at.strftime('%Y-%m')}")
                
                group_key_str = "|".join(group_key)
                
                # 그룹별 데이터 집계
                if group_key_str not in grouped_data:
                    grouped_data[group_key_str] = {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "cost": 0.0,
                        "count": 0
                    }
                
                grouped_data[group_key_str]["prompt_tokens"] += usage.prompt_tokens
                grouped_data[group_key_str]["completion_tokens"] += usage.completion_tokens or 0
                grouped_data[group_key_str]["total_tokens"] += usage.total_tokens
                grouped_data[group_key_str]["cost"] += usage.cost
                grouped_data[group_key_str]["count"] += 1
            
            # 총 합계 계산
            total_summary = {
                "total_prompt_tokens": sum(data["prompt_tokens"] for data in grouped_data.values()),
                "total_completion_tokens": sum(data["completion_tokens"] for data in grouped_data.values()),
                "total_tokens": sum(data["total_tokens"] for data in grouped_data.values()),
                "total_cost": sum(data["cost"] for data in grouped_data.values()),
            }
            
            return {
                "grouped_data": {
                    key: value for key, value in grouped_data.items()
                },
                "total_summary": total_summary
            }
    except Exception as e:
        logger.error(f"토큰 사용량 조회 실패: {str(e)}")
        raise 

# 동기적 토큰 저장 함수 추가
def save_token_usage_sync(
    db: SQLAlchemySession,
    user_id: UUID,
    project_type: ProjectType,
    token_type: TokenType,
    model_name: str,
    token_data: Dict[str, Any],
    cost: Optional[float] = None
) -> TokenUsage:
    """토큰 사용량 동기적으로 저장 (Celery 워커용)

    Args:
        db: 데이터베이스 세션 (동기식)
        user_id: 사용자 ID
        project_type: 프로젝트 유형 (doceasy, stockeasy)
        token_type: 토큰 유형 (llm, embedding)
        model_name: 모델 이름
        token_data: 토큰 사용량 데이터
        cost: 비용 (선택사항)

    Returns:
        TokenUsage: 저장된 토큰 사용량 레코드
    """
    try:
        logger.info(f"[토큰 추적][동기] DB 저장 시작: user_id={user_id}, type={token_type}, model={model_name}")
        
        # 토큰 데이터에서 값 추출
        prompt_tokens = token_data.get("prompt_tokens", 0)
        completion_tokens = token_data.get("completion_tokens", 0) if token_type == TokenType.LLM else None
        total_tokens = token_data.get("total_tokens", 0)
        
        # 비용이 제공되지 않은 경우 token_data에서 가져오기
        if cost is None:
            cost = token_data.get("total_cost", 0.0)
        
        logger.debug(f"[토큰 추적][동기] 토큰 데이터: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}, cost={cost}")
        
        # TokenUsage 레코드 생성
        token_usage_id = uuid4()
        token_usage = TokenUsage(
            id=token_usage_id,
            user_id=user_id,
            project_type=project_type,
            token_type=token_type,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost
        )
        
        # 데이터베이스에 저장
        db.add(token_usage)
        db.commit()
        db.refresh(token_usage)
        
        logger.info(f"[토큰 추적][동기] DB 저장 성공: ID={token_usage.id}, 토큰 합계={total_tokens}")
        return token_usage
    except Exception as e:
        logger.error(f"[토큰 추적][동기] DB 저장 실패: {str(e)}")
        db.rollback()
        raise

class TokenUsageTrackerSync:
    """동기식 토큰 사용량 추적기 (Celery 워커용)"""
    
    def __init__(self, user_id: UUID, project_type: ProjectType, token_type: TokenType, model_name: str):
        self.user_id = user_id
        self.project_type = project_type
        self.token_type = token_type
        self.model_name = model_name
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        logger.info(f"[토큰 추적][동기] TokenUsageTrackerSync 생성: user_id={user_id}, type={token_type}, model={model_name}")
        
    def add_tokens(self, prompt_tokens: int, completion_tokens: int = 0, total_tokens: int = None, cost: float = 0.0):
        """토큰 사용량 추가"""
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += total_tokens if total_tokens is not None else (prompt_tokens + completion_tokens)
        self.total_cost += cost
        logger.debug(f"[토큰 추적][동기] 토큰 추가: prompt={prompt_tokens}, completion={completion_tokens}, total={self.total_tokens}, cost={self.total_cost}")
        
    def save(self, db: SQLAlchemySession):
        """기록된 토큰 사용량을 데이터베이스에 저장 (동기식)"""
        token_data = {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens if self.token_type == TokenType.LLM else None,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost
        }
        
        #logger.debug(f"[토큰 추적][동기] 토큰 추적기 데이터 저장 요청: {token_data}")
        
        return save_token_usage_sync(
            db=db,
            user_id=self.user_id,
            project_type=self.project_type,
            token_type=self.token_type,
            model_name=self.model_name,
            token_data=token_data
        )

@contextmanager
def track_token_usage_sync(
    user_id: UUID, 
    project_type: str, 
    token_type: str, 
    model_name: str,
    db_getter = None
):
    """토큰 사용량을 동기적으로 추적하는 컨텍스트 매니저 (Celery 워커용)
    
    사용 예시:
    ```
    with track_token_usage_sync(user_id, "doceasy", "llm", "models/gemini-2.0-flash") as tracker:
        # LLM 호출 코드...
        tracker.add_tokens(prompt_tokens=100, completion_tokens=50, cost=0.01)
    # 컨텍스트 종료 시 자동으로 DB에 저장
    ```
    """
    logger.info(f"[토큰 추적][동기] 컨텍스트 매니저 시작: user_id={user_id}, project_type={project_type}, token_type={token_type}")
    tracker = TokenUsageTrackerSync(
        user_id=user_id,
        project_type=ProjectType(project_type),
        token_type=TokenType(token_type),
        model_name=model_name
    )
    
    try:
        yield tracker
        
        # 컨텍스트 종료 시 DB에 저장
        if tracker.total_tokens > 0:
            logger.info(f"[토큰 추적][동기] 컨텍스트 종료 - DB 저장 시작: total_tokens={tracker.total_tokens}")
            try:
                # DB 세션 가져오기
                db = None
                
                # db_getter가 None인 경우 db 없이 작동
                if db_getter is None:
                    logger.warning(f"[토큰 추적][동기] db_getter가 None - 토큰 저장 불가")
                    return
                
                # db_getter가 callable인 경우 함수 호출
                if callable(db_getter):
                    logger.debug(f"[토큰 추적][동기] 콜러블 db_getter 사용")
                    db = db_getter()
                else:
                    # 이미 세션인 경우
                    logger.debug(f"[토큰 추적][동기] 기존 세션 사용")
                    db = db_getter
                    
                if db:
                    logger.debug(f"[토큰 추적][동기] DB 세션 획득 성공, tracker.save() 호출")
                    tracker.save(db)
                else:
                    logger.warning("[토큰 추적][동기] DB 세션을 가져올 수 없어 토큰 사용량을 저장하지 못했습니다.")
            except Exception as e:
                logger.error(f"[토큰 추적][동기] 토큰 사용량 저장 중 오류 발생: {str(e)}")
        else:
            logger.info(f"[토큰 추적][동기] 토큰이 0개이므로 저장하지 않음")
    except Exception as e:
        logger.error(f"[토큰 추적][동기] 토큰 사용량 추적 중 오류 발생: {str(e)}")
        # 예외를 다시 발생시켜 호출자에게 전파
        raise 