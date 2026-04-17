from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import settings

router = Router()


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return

    admin_url = f"{settings.base_url}:{settings.web_port}/admin/"
    await message.answer(
        f"👨‍💻 Панель администратора:\n{admin_url}"
    )