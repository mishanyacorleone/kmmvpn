from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from collections.abc import AsyncGenerator

from config import settings
from models.database import Base

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=10,
    max_overflow=20
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def create_tables() -> None:
    """Создает все таблицы, если их нет"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency для получения сессии БД"""
    async with async_session_maker() as session:
        yield session
