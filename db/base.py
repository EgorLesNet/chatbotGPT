from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import DATABASE_URL, IS_POSTGRES

if IS_POSTGRES:
    # Supabase: SSL required; statement cache must be off for pgbouncer (pooler)
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={
            "ssl": "require",
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        },
    )
else:
    engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def init_db():
    from db import models  # noqa: F401
    # On Supabase the schema is managed by supabase_schema.sql; create_all only fills gaps.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
