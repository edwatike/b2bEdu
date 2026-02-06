"""Database session factory - решение с asyncpg."""
import logging

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

logger = logging.getLogger(__name__)

def _build_engine_settings(database_url: str) -> tuple[str, dict]:
    """Normalize DB URL options for asyncpg.

    asyncpg does not support ``sslmode`` kwarg from libpq-style URLs.
    """
    connect_args: dict = {}
    try:
        url_obj = make_url(database_url)
    except Exception:
        return database_url, connect_args

    query = dict(url_obj.query or {})
    sslmode = str(query.pop("sslmode", "")).strip().lower()
    if sslmode and "ssl" not in query:
        # Map common libpq style sslmode values to asyncpg "ssl" argument.
        if sslmode == "disable":
            connect_args["ssl"] = False
        elif sslmode in {"allow", "prefer", "require", "verify-ca", "verify-full"}:
            connect_args["ssl"] = True
        logger.warning(
            "DATABASE_URL includes unsupported 'sslmode=%s'; converted for asyncpg and removed from URL.",
            sslmode,
        )

    normalized_url = url_obj.set(query=query).render_as_string(hide_password=False)
    return normalized_url, connect_args


_normalized_db_url, _connect_args = _build_engine_settings(settings.DATABASE_URL)

# Создаем async engine
engine = create_async_engine(
    _normalized_db_url,
    connect_args=_connect_args,
    echo=settings.LOG_SQL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
)

# Создаем фабрику сессий
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    """Dependency для получения сессии с БД."""
    async with AsyncSessionLocal() as session:
        yield session
