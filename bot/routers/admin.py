import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.admin import (
    admin_menu_keyboard,
    admin_servers_keyboard,
    admin_server_actions_keyboard,
    admin_confirm_delete_server_keyboard,
    admin_confirm_broadcast_keyboard,
    admin_back_keyboard,
)
from bot.keyboards.user import back_to_menu_keyboard
from config import settings
from repositories.server import ServerRepository
from repositories.user import UserRepository
from services.broadcast import broadcast_message
from services.server_manager import server_manager

logger = logging.getLogger(__name__)
router = Router()


class AddServerStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_host = State()
    waiting_for_panel_port = State()
    waiting_for_username = State()
    waiting_for_password = State()
    waiting_for_inbound_id = State()
    waiting_for_max_clients = State()


class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    confirming = State()


def _is_admin(telegram_id: int) -> bool:
    return telegram_id in settings.admin_ids


# ── Middleware-фильтр: только для админов ─────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    await message.answer(
        "👨‍💻 Панель администратора",
        reply_markup=admin_menu_keyboard(),
    )


@router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "👨‍💻 Панель администратора",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


# ── Серверы ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_servers")
async def cb_admin_servers(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    servers = await ServerRepository(session).get_all_active()
    await callback.message.edit_text(
        f"🖥 Серверы ({len(servers)}):",
        reply_markup=admin_servers_keyboard(servers),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_server_info:"))
async def cb_admin_server_info(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    server_id = int(callback.data.split(":")[1])
    server_repo = ServerRepository(session)
    server = await server_repo.get_by_id(server_id)

    if not server:
        await callback.answer("Сервер не найден", show_alert=True)
        return

    client_count = await server_repo.get_client_count(server_id)
    stats = await server_manager.get_inbound_stats(server)

    up_gb = round(stats.up_bytes / 1024 ** 3, 2) if stats else "?"
    down_gb = round(stats.down_bytes / 1024 ** 3, 2) if stats else "?"
    status = "🟢 Активен" if server.is_active else "🔴 Отключён"

    await callback.message.edit_text(
        f"🖥 {server.name}\n\n"
        f"Статус: {status}\n"
        f"Хост: {server.host}\n"
        f"Порт панели: {server.panel_port}\n"
        f"Inbound ID: {server.inbound_id}\n"
        f"Подключений: {client_count}/{server.max_clients}\n"
        f"Трафик ↑: {up_gb} GB\n"
        f"Трафик ↓: {down_gb} GB",
        reply_markup=admin_server_actions_keyboard(server_id, server.is_active),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_toggle_server:"))
async def cb_admin_toggle_server(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    server_id = int(callback.data.split(":")[1])
    server_repo = ServerRepository(session)
    server = await server_repo.get_by_id(server_id)

    if not server:
        await callback.answer("Сервер не найден", show_alert=True)
        return

    await server_repo.set_active(server_id, not server.is_active)
    status = "включён" if not server.is_active else "отключён"
    await callback.answer(f"Сервер {status}", show_alert=True)

    # Обновляем страницу сервера
    server = await server_repo.get_by_id(server_id)
    client_count = await server_repo.get_client_count(server_id)
    status_text = "🟢 Активен" if server.is_active else "🔴 Отключён"

    await callback.message.edit_text(
        f"🖥 {server.name}\n\n"
        f"Статус: {status_text}\n"
        f"Хост: {server.host}\n"
        f"Порт панели: {server.panel_port}\n"
        f"Inbound ID: {server.inbound_id}\n"
        f"Подключений: {client_count}/{server.max_clients}",
        reply_markup=admin_server_actions_keyboard(server_id, server.is_active),
    )


@router.callback_query(F.data.startswith("admin_delete_server:"))
async def cb_admin_delete_server(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    server_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "❓ Удалить сервер?\n\nВсе подключения на этом сервере станут неактивными.",
        reply_markup=admin_confirm_delete_server_keyboard(server_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_confirm_delete_server:"))
async def cb_admin_confirm_delete_server(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    server_id = int(callback.data.split(":")[1])
    await ServerRepository(session).delete(server_id)
    server_manager.remove_client(server_id)

    await callback.message.edit_text(
        "✅ Сервер удалён.",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


# ── Добавление сервера (FSM) ──────────────────────────────────────────────────

@router.callback_query(F.data == "admin_add_server")
async def cb_admin_add_server(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.set_state(AddServerStates.waiting_for_name)
    await callback.message.answer("Введи название сервера (например: Нидерланды 1):")
    await callback.answer()


@router.message(AddServerStates.waiting_for_name)
async def fsm_server_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(AddServerStates.waiting_for_host)
    await message.answer("Введи IP адрес или домен сервера:")


@router.message(AddServerStates.waiting_for_host)
async def fsm_server_host(message: Message, state: FSMContext) -> None:
    await state.update_data(host=message.text.strip())
    await state.set_state(AddServerStates.waiting_for_panel_port)
    await message.answer("Введи порт панели x-ui (например: 15883):")


@router.message(AddServerStates.waiting_for_panel_port)
async def fsm_server_panel_port(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit():
        await message.answer("❌ Порт должен быть числом. Попробуй ещё раз:")
        return

    await state.update_data(panel_port=int(message.text.strip()))
    await state.set_state(AddServerStates.waiting_for_username)
    await message.answer("Введи логин от панели x-ui:")


@router.message(AddServerStates.waiting_for_username)
async def fsm_server_username(message: Message, state: FSMContext) -> None:
    await state.update_data(panel_username=message.text.strip())
    await state.set_state(AddServerStates.waiting_for_password)
    await message.answer("Введи пароль от панели x-ui:")


@router.message(AddServerStates.waiting_for_password)
async def fsm_server_password(message: Message, state: FSMContext) -> None:
    await state.update_data(panel_password=message.text.strip())
    await state.set_state(AddServerStates.waiting_for_inbound_id)
    await message.answer("Введи ID inbound в x-ui (число, видно в панели):")


@router.message(AddServerStates.waiting_for_inbound_id)
async def fsm_server_inbound_id(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit():
        await message.answer("❌ ID должен быть числом. Попробуй ещё раз:")
        return

    await state.update_data(inbound_id=int(message.text.strip()))
    await state.set_state(AddServerStates.waiting_for_max_clients)
    await message.answer("Максимальное количество клиентов на сервере (например: 20):")


@router.message(AddServerStates.waiting_for_max_clients)
async def fsm_server_max_clients(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    if not message.text.strip().isdigit():
        await message.answer("❌ Введи число. Попробуй ещё раз:")
        return

    data = await state.get_data()
    await state.clear()

    try:
        server = await ServerRepository(session).create(
            name=data["name"],
            host=data["host"],
            panel_port=data["panel_port"],
            panel_username=data["panel_username"],
            panel_password=data["panel_password"],
            inbound_id=data["inbound_id"],
            max_clients=int(message.text.strip()),
        )

        await message.answer(
            f"✅ Сервер добавлен!\n\n"
            f"Название: {server.name}\n"
            f"Хост: {server.host}\n"
            f"Inbound ID: {server.inbound_id}\n"
            f"Макс. клиентов: {server.max_clients}",
            reply_markup=admin_back_keyboard(),
        )

    except Exception as exc:
        logger.error("Ошибка добавления сервера: %s", exc)
        await message.answer(
            "😔 Не удалось добавить сервер. Попробуй ещё раз.",
            reply_markup=admin_back_keyboard(),
        )


# ── Статистика ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    user_repo = UserRepository(session)
    total_users = await user_repo.count_active()
    subscribed_users = await user_repo.count_with_subscription()

    servers = await ServerRepository(session).get_all_active()

    await callback.message.edit_text(
        f"📊 Статистика\n\n"
        f"👤 Всего пользователей: {total_users}\n"
        f"✅ С активной подпиской: {subscribed_users}\n"
        f"🖥 Активных серверов: {len(servers)}",
        reply_markup=admin_back_keyboard(),
    )
    await callback.answer()


# ── Рассылка (FSM) ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.set_state(BroadcastStates.waiting_for_message)
    await callback.message.answer("Введи текст рассылки:")
    await callback.answer()


@router.message(BroadcastStates.waiting_for_message)
async def fsm_broadcast_message(message: Message, state: FSMContext) -> None:
    await state.update_data(text=message.text)
    await state.set_state(BroadcastStates.confirming)

    await message.answer(
        f"📢 Превью рассылки:\n\n{message.text}\n\nОтправить всем пользователям?",
        reply_markup=admin_confirm_broadcast_keyboard(),
    )


@router.callback_query(F.data == "admin_confirm_broadcast", BroadcastStates.confirming)
async def cb_admin_confirm_broadcast(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    await state.clear()

    text = data.get("text", "")
    await callback.message.edit_text("⏳ Отправляю рассылку...")
    await callback.answer()

    success, errors = await broadcast_message(
        bot=callback.bot,
        session=session,
        text=text,
    )

    await callback.message.edit_text(
        f"✅ Рассылка завершена\n\n"
        f"Отправлено: {success}\n"
        f"Ошибок: {errors}",
        reply_markup=admin_back_keyboard(),
    )