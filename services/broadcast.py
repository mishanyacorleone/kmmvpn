import asyncio
import logging

from aiogram import Bot

from repositories.user import UserRepository
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Задержка между сообщениями, чтобы не словить flood от Telegram
_BROADCAST_DELAY_SECONDS = 0.05


async def broadcast_message(
    bot: Bot,
    session: AsyncSession,
    text: str
) -> tuple[int, int]:
    """
    Отправляет сообщение всем активным пользователям.

    Args:
        bot: экземпляр aiogram Bot
        session: сессия БД
        text: текст сообщения
    
    Returns:
        tuple[int, int]: (успешно отправлено, ошибок)
    """

    users = await UserRepository(session).get_all_active()

    success_count = 0
    error_count = 0

    for user in users:
        try:
            await bot.send_message(chat_id=user.telegram_id, text=text)
            success_count += 1
        except Exception as exc:
            logger.warning(
                "Не удалось отправить сообщение пользователю %s: %s",
                user.telegram_id,
                exc
            )
            error_count += 1
        
        await asyncio.sleep(_BROADCAST_DELAY_SECONDS)

    logger.info(
        "Рассылка завершена: %d успешно, %d ошибок",
        success_count,
        error_count
    )
    return success_count, error_count
