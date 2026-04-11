import asyncio
import logging
from typing import Any, Awaitable, Callable

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from bot.routers import admin, payment, user
from config import settings
from database import async_session_maker, create_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Middleware: инжектит сессию БД в каждый хэндлер ──────────────────────────

class DatabaseMiddleware:
    """
    Middleware которая открывает сессию БД на каждый апдейт
    и передаёт её в хэндлер через data["session"].
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with async_session_maker() as session:
            data["session"] = session
            return await handler(event, data)


# ── Сборка диспетчера ─────────────────────────────────────────────────────────

def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.middleware(DatabaseMiddleware())

    dp.include_router(user.router)
    dp.include_router(payment.router)
    dp.include_router(admin.router)

    return dp


# ── Точка входа ───────────────────────────────────────────────────────────────

async def main() -> None:
    logger.info("Запуск бота...")

    await create_tables()
    logger.info("Таблицы БД готовы")

    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher()

    # Удаляем вебхук если был установлен и чистим очередь апдейтов
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("Бот запущен. Слушаю апдейты...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())