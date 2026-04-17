import asyncio
import logging
from typing import Any, Awaitable, Callable

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject

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


# ── Запуск FastAPI ────────────────────────────────────────────────────────────

async def start_web() -> None:
    """Запускает FastAPI сервер в фоне."""
    from web.server import app

    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=settings.web_port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    await server.serve()


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

    await bot.delete_webhook(drop_pending_updates=True)

    # Передаём bot в админку для рассылки
    from web.admin.routes import set_bot
    set_bot(bot)

    logger.info("Бот и веб-сервер запущены")

    # Запускаем бота и веб-сервер параллельно
    await asyncio.gather(
        dp.start_polling(bot),
        start_web(),
    )


if __name__ == "__main__":
    asyncio.run(main())