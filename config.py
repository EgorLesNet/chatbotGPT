import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://heqakfypghrjeihrvbjz.supabase.co")


def _normalize_db_url(url: str) -> str:
    """Convert any postgres URL into SQLAlchemy asyncpg format."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    # asyncpg does not understand libpq query params like sslmode
    if url.startswith("postgresql+asyncpg://") and "?" in url:
        url = url.split("?", 1)[0]
    return url


DATABASE_URL = _normalize_db_url(
    os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./prorab.db")
)
IS_POSTGRES = DATABASE_URL.startswith("postgresql")
