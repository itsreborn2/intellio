import asyncio
import uuid
import sys
import os
import traceback

# 프로젝트 루트를 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from common.models.base import Base
from common.models.user import User
from common.core.config import settings

# --- 설정 ---
DATABASE_URL = settings.DATABASE_URL.replace("postgresql+psycopg2", "postgresql+asyncpg")
NUM_USERS_TO_CREATE = 100

async def create_users():
    """지정된 수의 테스트 사용자를 생성하여 데이터베이스에 추가합니다."""
    print(f"데이터베이스에 연결 중: {DATABASE_URL}")
    engine = create_async_engine(DATABASE_URL, echo=False)

    # --- 테이블 생성 ---
    async with engine.begin() as conn:
        # users 테이블만 명시적으로 생성합니다. (checkfirst=True는 테이블이 이미 존재하면 무시)
        # User.metadata.tables['users']를 사용하여 'users' 테이블 객체를 명시적으로 전달합니다.
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=[User.metadata.tables['users']], checkfirst=True))
    print("데이터베이스 테이블이 성공적으로 확인/생성되었습니다.")

    AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)

    users_to_add = []
    for i in range(1, NUM_USERS_TO_CREATE + 1):
        user = User(
            id=uuid.uuid4(),
            email=f"testuser{i}@intellio.com",
            name=f"Test User {i}",
            hashed_password=None,  # OAuth 사용자는 비밀번호가 없음
            is_active=True,
            is_superuser=False,
            oauth_provider="google"  # OAuth 제공자 명시
        )
        users_to_add.append(user)

    try:
        async with AsyncSessionFactory() as session:
            async with session.begin():
                print(f"{NUM_USERS_TO_CREATE}명의 테스트 사용자 생성을 시작합니다...")
                session.add_all(users_to_add)
        
        print(f"성공적으로 {NUM_USERS_TO_CREATE}명의 사용자를 추가했습니다.")

    except Exception as e:
        print("--- 스크립트 실행 실패 ---", file=sys.stderr)
        print(f"오류 발생: {e}", file=sys.stderr)
        print("--- 전체 오류 추적 --- ", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print("---------------------", file=sys.stderr)
        sys.exit(1)

async def main():
    await create_users()

if __name__ == "__main__":
    asyncio.run(main())
