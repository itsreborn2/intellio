import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

async def reset_database():
    # Create engine with superuser privileges
    engine = create_async_engine(settings.ASYNC_DATABASE_URI)
    
    async with engine.begin() as conn:
        # Terminate all connections to the database
        await conn.execute(text("""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = 'intellio_db'
            AND pid <> pg_backend_pid();
        """))
        
        # Drop and recreate database
        await conn.execute(text("DROP DATABASE IF EXISTS intellio_db;"))
        await conn.execute(text("CREATE DATABASE intellio_db;"))
    
    await engine.dispose()
    print("Database reset completed successfully!")

if __name__ == "__main__":
    asyncio.run(reset_database())
