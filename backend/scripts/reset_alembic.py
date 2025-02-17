from sqlalchemy import create_engine, text, inspect
from common.core.config import settings

def reset_alembic():
    engine = create_engine(settings.DATABASE_URL)
    inspector = inspect(engine)
    
    with engine.connect() as conn:
        # Drop all tables
        for table in inspector.get_table_names():
            try:
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
            except Exception as e:
                print(f"Failed to drop table {table}: {e}")
        
        # Drop custom types
        types = ["documentstatus", "categorytype", "retentionperiod"]
        for type_name in types:
            try:
                conn.execute(text(f"DROP TYPE IF EXISTS {type_name} CASCADE"))
            except Exception as e:
                print(f"Failed to drop type {type_name}: {e}")
        
        conn.commit()

if __name__ == "__main__":
    reset_alembic()
