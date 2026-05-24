from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# import the Base from your project's base.py
from app.db.base import Base
from app.core.config import settings
# import all models to ensure Base.metadata knows about them
import app.db.models.base_class

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

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

# set the sqlalchemy.url from our settings
db_url = settings.DATABASE_URL
if not db_url or not db_url.strip():
    raise ValueError(
        "DATABASE_URL is required. Set DATABASE_URL environment variable or "
        "RENDER_INTERNAL_DATABASE_URL/RENDER_EXTERNAL_DATABASE_URL or "
        "DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME or "
        "RENDER_DB_HOST/RENDER_DB_PORT/RENDER_DB_USER/RENDER_DB_PASSWORD/RENDER_DB_NAME."
    )
config.set_main_option("sqlalchemy.url", db_url)

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

from sqlalchemy.ext.asyncio import create_async_engine

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True  # Enable type comparison for autogenerate
    )

    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    db_url = settings.DATABASE_URL
    if not db_url or not db_url.strip():
        raise ValueError(
            "DATABASE_URL is required but not set. "
            "Check environment variables: DATABASE_URL, RENDER_INTERNAL_DATABASE_URL, "
            "RENDER_EXTERNAL_DATABASE_URL, or DB_HOST/DB_USER/DB_PASSWORD/DB_NAME"
        )
    
    try:
        connectable = create_async_engine(
            db_url,
            poolclass=pool.NullPool,
        )
    except Exception as e:
        raise ValueError(
            f"Failed to create async engine with DATABASE_URL: {db_url}\n"
            f"Error: {e}"
        ) from e

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_migrations_online())