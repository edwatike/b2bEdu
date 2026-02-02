"""Database session factory - решение с asyncpg."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Создаем async engine
engine = create_async_engine(
    settings.DATABASE_URL,
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

