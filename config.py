import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://heqakfypghrjeihrvbjz.supabase.co")
WEB_APP_URL = os.getenv("WEB_APP_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
SERVERLESS = bool(os.getenv("VERCEL"))


def _normalize_db_url(url: str) -> str:
    """Convert any postgres URL into SQLAlchemy asyncpg format."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    if url.startswith("postgresql+asyncpg://") and "?" in url:
        url = url.split("?", 1)[0]
    return url


DATABASE_URL = _normalize_db_url(
    os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./prorab.db")
)
IS_POSTGRES = DATABASE_URL.startswith("postgresql")
