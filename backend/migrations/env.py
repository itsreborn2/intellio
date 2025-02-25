import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from dotenv import load_dotenv

# .env 파일의 절대 경로
if os.getenv('ENV') == 'development':
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.development")
else:
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.production")
print(f"dotenv_path : {dotenv_path}")
load_dotenv(dotenv_path, override=True)
print(f"DATABASE_URL[After] : {os.getenv('DATABASE_URL')}")
print(f"POSTGRES_HOST : {os.getenv('POSTGRES_HOST')}")
print(f"POSTGRES_PORT : {os.getenv('POSTGRES_PORT')}")
print(f"POSTGRES_DB : {os.getenv('POSTGRES_DB')}")

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
print(f"ROOT : {os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}")

# Import all models here
from common.models.base import Base
from doceasy.models.table_history import TableHistory
from doceasy.models.chat import ChatHistory
from doceasy.models.document import Document
from common.models.user import User
from doceasy.models.project import Project
from doceasy.models.category import Category
from stockeasy.models.telegram_message import TelegramMessage


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# Load environment variables
config.set_main_option('sqlalchemy.url', os.getenv('DATABASE_URL'))

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
