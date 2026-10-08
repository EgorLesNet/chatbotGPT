from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from config import DATABASE_URL, IS_POSTGRES, SERVERLESS

if IS_POSTGRES:
    _kwargs: dict = {
        "echo": False,
        "connect_args": {
            "ssl": "require",
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        },
    }
    if SERVERLESS:
        # Serverless: no client-side pool, Supabase transaction pooler (port 6543) does the pooling
        _kwargs["poolclass"] = NullPool
    else:
        _kwargs.update(pool_size=5, max_overflow=5, pool_pre_ping=True, pool_recycle=1800)
    engine = create_async_engine(DATABASE_URL, **_kwargs)
else:
    engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def init_db():
    if SERVERLESS:
        return  # schema is managed in Supabase (supabase_schema.sql)
    from db import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
