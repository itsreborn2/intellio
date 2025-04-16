from uuid import UUID, uuid4
from typing import Optional, Dict, List, Any, ContextManager, Callable, AsyncGenerator, Awaitable, AsyncContextManager, Union, TypeVar
from datetime import datetime, timedelta
from sqlalchemy import select, func, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session as SQLAlchemySession
import logging
from contextlib import asynccontextmanager, contextmanager
import asyncio

from common.models.token_usage import TokenUsage, ProjectType, TokenType
from stockeasy.models.chat import StockChatMessage, StockChatSession
# 순환 참조를 방지하기 위해 get_db 임포트를 제거하고 지연 임포트를 사용
# from common.core.deps import get_db

logger = logging.getLogger(__name__)

# 세션 타입을 위한 타입 변수
T = TypeVar('T')
# 비동기 세션 팩토리 타입 정의
SessionFactoryType = Callable[[], AsyncGenerator[AsyncSession, None]]
# 또는 더 유연한 타입 정의
SessionFactoryContextType = Callable[[], Union[AsyncGenerator[AsyncSession, None], AsyncContextManager[AsyncSession]]]

# 글로벌 토큰 사용량 저장 큐
class TokenUsageQueue:
    """
    토큰 사용량 데이터를 저장하는 큐
    저장 요청은 큐에 추가되고, 백그라운드 태스크에서 처리됨
    """
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._queue = asyncio.Queue()
            cls._instance._task = None
            cls._instance._initialized = False
            cls._instance._session_factory = None
        return cls._instance
    
    async def initialize(self, session_factory: SessionFactoryContextType):
        """
        큐 초기화 및 백그라운드 처리 태스크 시작
        
        Args:
            session_factory: 데이터베이스 세션을 생성하는 비동기 팩토리 함수
                            (AsyncGenerator 또는 AsyncContextManager를 반환하는 함수)
        """
        if not self._initialized:
            async with self._lock:
                if not self._initialized:
                    self._session_factory = session_factory
                    self._task = asyncio.create_task(self._process_queue())
                    self._initialized = True
                    logger.info("토큰 사용량 저장 큐 초기화 완료")
    
    async def add_usage(self, user_id: UUID, project_type: str, token_type: str, 
                       model_name: str, token_data: Dict[str, Any]):
        """
        토큰 사용량 데이터를 큐에 추가
        
        Args:
            user_id: 사용자 ID
            project_type: 프로젝트 유형
            token_type: 토큰 유형
            model_name: 모델 이름
            token_data: 토큰 사용량 데이터
        """
        if not self._initialized:
            logger.warning("토큰 사용량 큐가 초기화되지 않았습니다")
            return
            
        await self._queue.put({
            "user_id": user_id,
            "project_type": project_type,
            "token_type": token_type,
            "model_name": model_name,
            "token_data": token_data
        })
        logger.debug(f"토큰 사용량 데이터가 큐에 추가됨 ({user_id}, {project_type}, {token_type})")
    
    async def _process_queue(self):
        """큐에 있는 토큰 사용량 데이터를 처리하는 백그라운드 태스크"""
        try:
            logger.info("토큰 사용량 처리 태스크 시작")
            while True:
                try:
                    # 큐에서 데이터 가져오기
                    usage_data = await self._queue.get()
                    
                    try:
                        # 세션 생성
                        if self._session_factory:
                            async for db in self._session_factory():
                                try:
                                    # 토큰 사용량 저장
                                    await save_token_usage(
                                        db=db,
                                        user_id=usage_data["user_id"],
                                        project_type=ProjectType(usage_data["project_type"]),
                                        token_type=TokenType(usage_data["token_type"]),
                                        model_name=usage_data["model_name"],
                                        token_data=usage_data["token_data"]
                                    )
                                    logger.debug(f"토큰 사용량 데이터 저장 완료: {usage_data['user_id']}")
                                except Exception as db_error:
                                    logger.error(f"토큰 사용량 저장 중 오류 발생: {str(db_error)}")
                                finally:
                                    # 태스크 완료 표시
                                    self._queue.task_done()
                                # 세션은 한 번만 가져오면 됨
                                break
                        else:
                            logger.error("세션 팩토리가 설정되지 않았습니다")
                            self._queue.task_done()
                    except Exception as e:
                        logger.error(f"토큰 사용량 처리 중 오류 발생: {str(e)}")
                        self._queue.task_done()
                except asyncio.CancelledError:
                    # 태스크가 취소된 경우
                    logger.info("토큰 사용량 처리 태스크가 취소되었습니다")
                    return
                except Exception as e:
                    # 예외 발생 시 로깅하고 계속 진행
                    logger.error(f"토큰 사용량 큐 처리 중 예외 발생: {str(e)}")
                    continue
        except asyncio.CancelledError:
            logger.info("토큰 사용량 처리 태스크가 취소되었습니다")
        except Exception as e:
            logger.error(f"토큰 사용량 처리 태스크에서 예외 발생: {str(e)}")
    
    async def shutdown(self):
        """백그라운드 태스크 종료 및 남은 작업 처리"""
        if self._task and not self._task.done():
            # 남은 작업 처리 대기
            await self._queue.join()
            # 태스크 취소
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info("토큰 사용량 처리 태스크가 정상적으로 종료되었습니다")
            finally:
                self._task = None
                self._initialized = False

# 토큰 사용량 데코레이터
def track_token_usage_bg(
    user_id: Optional[UUID] = None,
    project_type: Optional[str] = None,
    token_type: Optional[str] = None,
    model_name: Optional[str] = None
):
    """
    토큰 사용량을 비동기적으로 백그라운드에서 추적하기 위한 데코레이터
    
    사용 예시:
    
    @track_token_usage_bg(project_type="doceasy", token_type="embedding")
    async def create_embeddings_async(self, texts: List[str], user_id: UUID = None) -> List[List[float]]:
        # 함수 구현...
        # 토큰 사용량은 자동으로 수집되어 백그라운드에서 저장됨
    """
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            # 비동기 함수인 경우
            async def wrapper(*args, **kwargs):
                # 파라미터에서 필요한 값 추출
                _user_id = kwargs.get('user_id', user_id)
                _project_type = kwargs.get('project_type', project_type)
                _token_type = kwargs.get('token_type', token_type) or "embedding"  # 기본값
                _model_name = kwargs.get('model_name', None)
                logger.info(f"[track_token_usage_bg][async] _user_id: {_user_id}, _project_type: {_project_type}, _token_type: {_token_type}, _model_name: {_model_name}")
                # 모델 이름이 없으면 클래스 인스턴스에서 가져오기
                if not _model_name and len(args) > 0 and hasattr(args[0], 'model_name'):
                    _model_name = args[0].model_name
                
                if _user_id and _project_type:
                    # OpenAI 토큰 콜백 핸들러 가져오기 (지연 임포트)
                    try:
                        # 필요할 때만 임포트
                        from langchain_community.callbacks.manager import get_openai_callback
                    except ImportError:
                        try:
                            # 이전 버전 지원
                            from langchain.callbacks import get_openai_callback
                        except ImportError:
                            logger.warning("OpenAI 콜백 핸들러를 임포트할 수 없어 토큰 추적 없이 실행합니다")
                            return await func(*args, **kwargs)
                    
                    # LangChain 콜백 핸들러를 사용하여 토큰 수집
                    try:
                        with get_openai_callback() as cb:
                            # 원래 함수 실행
                            result = await func(*args, **kwargs)
                            
                            # 토큰 사용량 데이터 수집
                            token_data = {
                                "prompt_tokens": cb.prompt_tokens,
                                "completion_tokens": cb.completion_tokens if _token_type == "llm" else None,
                                "total_tokens": cb.total_tokens,
                                "total_cost": cb.total_cost
                            }
                            
                            # 백그라운드에서 토큰 사용량 저장
                            queue = TokenUsageQueue()
                            await queue.add_usage(
                                user_id=_user_id,
                                project_type=_project_type,
                                token_type=_token_type,
                                model_name=_model_name,
                                token_data=token_data
                            )
                            
                            return result
                    except Exception as e:
                        logger.warning(f"토큰 추적 중 오류 발생: {str(e)}. 토큰 추적 없이 실행합니다.")
                        return await func(*args, **kwargs)
                else:
                    # 필요한 파라미터가 없는 경우, 원래 함수만 실행
                    return await func(*args, **kwargs)
        else:
            # 동기 함수인 경우
            def wrapper(*args, **kwargs):
                # 파라미터에서 필요한 값 추출
                _user_id = kwargs.get('user_id', user_id)
                _project_type = kwargs.get('project_type', project_type)
                _token_type = kwargs.get('token_type', token_type) or "embedding"  # 기본값
                _model_name = kwargs.get('model_name', None)
                logger.info(f"[track_token_usage_bg][sync] _user_id: {_user_id}, _project_type: {_project_type}, _token_type: {_token_type}, _model_name: {_model_name}")
                # 모델 이름이 없으면 클래스 인스턴스에서 가져오기
                if not _model_name and len(args) > 0 and hasattr(args[0], 'model_name'):
                    _model_name = args[0].model_name
                
                # 원래 함수 실행
                result = func(*args, **kwargs)
                
                # 필요한 파라미터가 있고 이벤트 루프가 실행 중인 경우
                if _user_id and _project_type:
                    try:
                        # 비동기 함수를 실행하기 위한 코드
                        async def process_token_usage():
                            # OpenAI 토큰 정보가 있는 경우
                            if hasattr(result, "usage_metadata") or hasattr(result, "usage"):
                                # 토큰 사용량 데이터 수집
                                usage_attr = "usage_metadata" if hasattr(result, "usage_metadata") else "usage"
                                usage_obj = getattr(result, usage_attr)
                                
                                token_data = {
                                    "prompt_tokens": usage_obj.prompt_tokens if hasattr(usage_obj, "prompt_tokens") else 0,
                                    "completion_tokens": usage_obj.completion_tokens if hasattr(usage_obj, "completion_tokens") else None,
                                    "total_tokens": usage_obj.total_tokens if hasattr(usage_obj, "total_tokens") else 0,
                                    "total_cost": 0.0  # 비용 계산 로직 필요
                                }
                                logger.info(f"토큰 정보: {token_data}")
                                
                                # 백그라운드에서 토큰 사용량 저장
                                queue = TokenUsageQueue()
                                await queue.add_usage(
                                    user_id=_user_id,
                                    project_type=_project_type,
                                    token_type=_token_type,
                                    model_name=_model_name,
                                    token_data=token_data
                                )
                            else:
                                logger.info("토큰 사용량 정보가 없습니다")
                        
                        # 이벤트 루프가 실행 중인지 확인
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                # 이벤트 루프가 실행 중이면 태스크 생성
                                asyncio.create_task(process_token_usage())
                            else:
                                # 이벤트 루프가 실행 중이 아니면 별도로 실행
                                asyncio.run(process_token_usage())
                        except RuntimeError:
                            logger.warning("이벤트 루프를 가져올 수 없어 토큰 사용량 저장을 건너뜁니다")
                    except Exception as e:
                        logger.error(f"토큰 사용량 처리 중 오류 발생: {str(e)}")
                
                return result
        
        # 래퍼 함수에 원래 함수의 메타데이터 복사
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.__annotations__ = func.__annotations__
        
        return wrapper
    
    return decorator

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
        #logger.info(f"[토큰 추적] 토큰 추가: prompt={prompt_tokens}, completion={completion_tokens}, total={self.total_tokens}, cost={self.total_cost}")
        
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
    db_getter: Optional[Union[AsyncSession, SessionFactoryContextType]] = None
):
    """토큰 사용량을 추적하는 컨텍스트 매니저
    
    사용 예시:
    ```
    async with track_token_usage(user_id, "doceasy", "embedding", "text-embedding-ada-002") as tracker:
        # 임베딩 생성 코드...
        tracker.add_tokens(prompt_tokens=100, cost=0.01)
    # 컨텍스트 종료 시 자동으로 DB에 저장
    ```
    
    Args:
        user_id: 사용자 ID
        project_type: 프로젝트 유형
        token_type: 토큰 유형
        model_name: 모델 이름
        db_getter: DB 세션 또는 세션 팩토리 함수
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
            #logger.info(f"[토큰 추적] 컨텍스트 종료 - DB 저장 시작: total_tokens={tracker.total_tokens}")
            try:
                # DB 세션 가져오기
                db = None
                
                # db_getter가 None인 경우 common.core.deps에서 get_db를 지연 임포트
                if db_getter is None:
                    # 지연 임포트
                    logger.debug(f"[토큰 추적] db_getter가 None - 지연 임포트 시도")
                    from common.core.deps import get_db
                    db_getter = get_db
                
                # db_getter가 callable인 경우 (세션 팩토리 함수)
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
    db_getter: Optional[Union[SQLAlchemySession, Callable[[], SQLAlchemySession]]] = None
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

async def get_user_question_count(
    db: AsyncSession,
    user_id: UUID,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    group_by: Optional[str] = None
) -> Dict[str, Any]:
    """사용자의 StockEasy 질문 개수 조회

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        start_date: 시작 날짜 (선택사항)
        end_date: 종료 날짜 (선택사항)
        group_by: 그룹화 기준 (선택사항) - 'day', 'week', 'month'

    Returns:
        Dict[str, Any]: 질문 개수 데이터
    """
    try:
        # 사용자의 채팅 세션 ID 목록 조회
        sessions_query = select(StockChatSession.id).where(
            StockChatSession.user_id == user_id
        )
        result = await db.execute(sessions_query)
        session_ids = result.scalars().all()
        
        # 세션이 없으면 빈 결과 반환
        if not session_ids:
            return {
                "total_questions": 0,
                "grouped_data": {}
            }
        
        # 전체 질문 수 조회 쿼리
        count_query = select(func.count()).where(
            StockChatMessage.chat_session_id.in_(session_ids),
            StockChatMessage.role == "user"
        )
        
        # 날짜 필터 추가
        if start_date:
            count_query = count_query.where(StockChatMessage.created_at >= start_date)
        if end_date:
            count_query = count_query.where(StockChatMessage.created_at <= end_date)
        
        # 전체 질문 수 조회
        result = await db.execute(count_query)
        total_questions = result.scalar() or 0
        
        # 그룹화된 데이터 조회
        grouped_data = {}
        if group_by:
            # 그룹화 기준에 따른 쿼리 구성
            if group_by == "day":
                # 일별 그룹화
                date_format = func.date_trunc('day', StockChatMessage.created_at)
                label = 'day'
            elif group_by == "week":
                # 주별 그룹화
                date_format = func.date_trunc('week', StockChatMessage.created_at)
                label = 'week'
            elif group_by == "month":
                # 월별 그룹화
                date_format = func.date_trunc('month', StockChatMessage.created_at)
                label = 'month'
            else:
                # 유효하지 않은 그룹화 기준인 경우 빈 사전 반환
                return {
                    "total_questions": total_questions,
                    "grouped_data": {}
                }
            
            # 그룹화된 쿼리 구성
            group_query = select(
                date_format.label(label),
                func.count().label('count')
            ).where(
                StockChatMessage.chat_session_id.in_(session_ids),
                StockChatMessage.role == "user"
            )
            
            # 날짜 필터 추가
            if start_date:
                group_query = group_query.where(StockChatMessage.created_at >= start_date)
            if end_date:
                group_query = group_query.where(StockChatMessage.created_at <= end_date)
            
            # 그룹화 및 정렬
            group_query = group_query.group_by(date_format).order_by(date_format)
            
            # 쿼리 실행
            result = await db.execute(group_query)
            for row in result:
                date_key = row[0].strftime('%Y-%m-%d')
                count = row[1]
                grouped_data[date_key] = count
        
        # 결과 반환
        return {
            "total_questions": total_questions,
            "grouped_data": grouped_data
        }
        
    except Exception as e:
        from loguru import logger
        logger.error(f"사용자 질문 수 조회 중 오류 발생: {str(e)}")
        raise e 