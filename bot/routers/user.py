import logging
from datetime import timezone

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.user import (
    main_menu_keyboard,
    connections_keyboard,
    new_connection_keyboard,
    connection_info_keyboard,
    confirm_delete_keyboard,
    back_to_menu_keyboard
)
from repositories.connection import ConnectionRepository
from repositories.server import ServerRepository
from repositories.user import UserRepository
from services.connection import ConnectionService
from services.server_manager import server_manager

logger = logging.getLogger(__name__)
router = Router()


def _subscription_status_text(user) -> str:
    """Формирует текст статуса подписки"""
    if not user.subscription_expires_at:
        return "❌ Подписка не активна"

    expires_at = user.subscription_expires_at
    from datetime import datetime
    now = datetime.now(timezone.utc)

    if expires_at <= now:
        return "❌ Подписка истекла"

    delta = expires_at - now 
    days_left = delta.days
    date_str = expires_at.strftime("%d.%m.%Y")
    return f"✅ Подписка активна до {date_str} (осталось {days_left} дн.)"
 
 
# ── /start ────────────────────────────────────────────────────────────────────
 
@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    user_repo = UserRepository(session)
    user, is_new = await user_repo.get_or_create(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
    )
 
    greeting = "Добро пожаловать" if is_new else "С возвращением"
    name = message.from_user.first_name or "друг"
 
    await message.answer(
        f"{greeting}, {name}! 👋\n\n"
        "Это VPN сервис для доступа к заблокированным сайтам.\n"
        "Выбери действие:",
        reply_markup=main_menu_keyboard(),
    )
 
 
# ── Главное меню ──────────────────────────────────────────────────────────────
 
@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.message.edit_text(
        "Главное меню. Выбери действие:",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
 
 
# ── Статус пользователя ───────────────────────────────────────────────────────
 
@router.callback_query(F.data == "my_status")
async def cb_my_status(callback: CallbackQuery, session: AsyncSession) -> None:
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
 
    status_text = _subscription_status_text(user)
    connections = await ConnectionRepository(session).get_user_connections(user.id)
 
    await callback.message.edit_text(
        f"👤 Твой статус\n\n"
        f"{status_text}\n"
        f"🔑 Активных подключений: {len(connections)}",
        reply_markup=back_to_menu_keyboard(),
    )
    await callback.answer()
 
 
# ── Список серверов ───────────────────────────────────────────────────────────
 
@router.callback_query(F.data == "servers_list")
async def cb_servers_list(callback: CallbackQuery, session: AsyncSession) -> None:
    servers = await ServerRepository(session).get_all_active()
 
    if not servers:
        await callback.message.edit_text(
            "😔 Серверов пока нет.",
            reply_markup=back_to_menu_keyboard(),
        )
        await callback.answer()
        return
 
    lines = ["🌍 Доступные серверы:\n"]
    for server in servers:
        stats = await server_manager.get_inbound_stats(server)
        client_count = stats.total_clients if stats else "?"
        lines.append(f"• {server.name} — {client_count}/{server.max_clients} подключений")
 
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=back_to_menu_keyboard(),
    )
    await callback.answer()
 
 
# ── Мои подключения ───────────────────────────────────────────────────────────
 
@router.callback_query(F.data == "my_connections")
async def cb_my_connections(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await UserRepository(session).get_by_telegram_id(callback.from_user.id)
    connections = await ConnectionRepository(session).get_user_connections(user.id)
 
    if not connections:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="➕ Новое подключение", callback_data="new_connection"))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
 
        await callback.message.edit_text(
            "У тебя пока нет подключений.\nСоздай первое!",
            reply_markup=builder.as_markup(),
        )
        await callback.answer()
        return
 
    await callback.message.edit_text(
        f"🔑 Твои подключения ({len(connections)}):",
        reply_markup=connections_keyboard(connections),
    )
    await callback.answer()
 
 
# ── Информация о подключении ──────────────────────────────────────────────────
 
@router.callback_query(F.data.startswith("connection_info:"))
async def cb_connection_info(callback: CallbackQuery, session: AsyncSession) -> None:
    connection_id = int(callback.data.split(":")[1])
    connection = await ConnectionRepository(session).get_by_id(connection_id)
 
    if not connection:
        await callback.answer("Подключение не найдено", show_alert=True)
        return
 
    server_name = connection.server.name if connection.server else "Неизвестный сервер"
    date_str = connection.created_at.strftime("%d.%m.%Y")
 
    await callback.message.edit_text(
        f"🔑 Подключение #{connection_id}\n\n"
        f"🌍 Сервер: {server_name}\n"
        f"📅 Создано: {date_str}",
        reply_markup=connection_info_keyboard(connection_id),
    )
    await callback.answer()
 
 
# ── Показать ключ подключения ─────────────────────────────────────────────────
 
@router.callback_query(F.data.startswith("show_key:"))
async def cb_show_key(callback: CallbackQuery, session: AsyncSession) -> None:
    connection_id = int(callback.data.split(":")[1])
    connection = await ConnectionRepository(session).get_by_id(connection_id)
 
    if not connection:
        await callback.answer("Подключение не найдено", show_alert=True)
        return
 
    user = await UserRepository(session).get_by_telegram_id(callback.from_user.id)
    if not user or connection.user_id != user.id:
        await callback.answer("Нет доступа", show_alert=True)
        return
 
    # Пересобираем ключ из данных сервера
    xui_client = server_manager.get_client(connection.server)
    try:
        inbound_data = await xui_client._request(
            "GET", f"/xui/inbound/get/{connection.server.inbound_id}"
        )
        import json
        from urllib.parse import urlencode, quote
 
        inbound_obj = inbound_data["obj"]
        stream_settings = json.loads(inbound_obj.get("streamSettings", "{}"))
        network = stream_settings.get("network", "tcp")
        security = stream_settings.get("security", "none")
 
        params: dict[str, str] = {"type": network}
 
        if security == "reality":
            reality_settings = stream_settings.get("realitySettings", {})
            params["security"] = "reality"
            params["flow"] = "xtls-rprx-vision"
            params["pbk"] = reality_settings.get("publicKey", "")
            params["fp"] = reality_settings.get("fingerprint", "chrome")
            params["sni"] = reality_settings.get("serverNames", [""])[0]
            params["sid"] = reality_settings.get("shortIds", [""])[0]
            params["spx"] = "%2F"
        elif security == "tls":
            tls_settings = stream_settings.get("tlsSettings", {})
            params["security"] = "tls"
            params["sni"] = tls_settings.get("serverName", connection.server.host)
            params["fp"] = "chrome"
 
        query_string = urlencode(params)
        remark = quote(connection.server.name)
        vless_link = (
            f"vless://{connection.xui_client_uuid}@"
            f"{connection.server.host}:{inbound_obj.get('port', '')}?"
            f"{query_string}#{remark}"
        )
 
        await callback.message.answer(
            f"🔑 Твой ключ подключения:\n\n"
            f"<code>{vless_link}</code>\n\n"
            "Скопируй и вставь в приложение (v2rayNG, Hiddify, Streisand).",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
        await callback.answer()
 
    except Exception as exc:
        logger.error("Ошибка получения ключа для подключения %d: %s", connection_id, exc)
        await callback.answer("Не удалось получить ключ. Попробуй позже.", show_alert=True)
 
 
# ── Новое подключение ─────────────────────────────────────────────────────────
 
@router.callback_query(F.data == "new_connection")
async def cb_new_connection(callback: CallbackQuery, session: AsyncSession) -> None:
    has_sub = await UserRepository(session).has_active_subscription(callback.from_user.id)
 
    if not has_sub:
        await callback.message.edit_text(
            "❌ Для создания подключения нужна активная подписка.\n\n"
            "Нажми «Купить подписку» в главном меню.",
            reply_markup=back_to_menu_keyboard(),
        )
        await callback.answer()
        return
 
    servers = await ServerRepository(session).get_available()
 
    if not servers:
        await callback.message.edit_text(
            "😔 Свободных серверов нет. Попробуй позже.",
            reply_markup=back_to_menu_keyboard(),
        )
        await callback.answer()
        return
 
    await callback.message.edit_text(
        "Выбери сервер для подключения:",
        reply_markup=new_connection_keyboard(servers),
    )
    await callback.answer()
 
 
@router.callback_query(F.data.startswith("connect_to_server:"))
async def cb_connect_to_server(callback: CallbackQuery, session: AsyncSession) -> None:
    server_id = int(callback.data.split(":")[1])
 
    await callback.message.edit_text("⏳ Создаю подключение...")
    await callback.answer()
 
    try:
        service = ConnectionService(session)
        result = await service.create_connection(
            telegram_id=callback.from_user.id,
            server_id=server_id,
        )
 
        await callback.message.edit_text(
            f"✅ Подключение создано!\n\n"
            f"🌍 Сервер: {result.server_name}\n\n"
            f"🔑 Твой ключ:\n<code>{result.vless_link}</code>\n\n"
            "Скопируй и вставь в приложение (v2rayNG, Hiddify, Streisand).",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
 
    except ValueError as exc:
        await callback.message.edit_text(
            f"❌ {exc}",
            reply_markup=back_to_menu_keyboard(),
        )
    except RuntimeError as exc:
        logger.error("Ошибка создания подключения для %d: %s", callback.from_user.id, exc)
        await callback.message.edit_text(
            "😔 Не удалось создать подключение. Попробуй позже.",
            reply_markup=back_to_menu_keyboard(),
        )
 
 
# ── Удаление подключения ──────────────────────────────────────────────────────
 
@router.callback_query(F.data.startswith("delete_connection:"))
async def cb_delete_connection(callback: CallbackQuery) -> None:
    connection_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "❓ Уверен что хочешь удалить это подключение?\n"
        "Ключ перестанет работать.",
        reply_markup=confirm_delete_keyboard(connection_id),
    )
    await callback.answer()
 
 
@router.callback_query(F.data.startswith("confirm_delete:"))
async def cb_confirm_delete(callback: CallbackQuery, session: AsyncSession) -> None:
    connection_id = int(callback.data.split(":")[1])
 
    await callback.message.edit_text("⏳ Удаляю подключение...")
    await callback.answer()
 
    try:
        service = ConnectionService(session)
        await service.delete_connection(
            connection_id=connection_id,
            telegram_id=callback.from_user.id,
        )
        await callback.message.edit_text(
            "✅ Подключение удалено.",
            reply_markup=back_to_menu_keyboard(),
        )
 
    except ValueError as exc:
        await callback.message.edit_text(
            f"❌ {exc}",
            reply_markup=back_to_menu_keyboard(),
        )
    except Exception as exc:
        logger.error("Ошибка удаления подключения %d: %s", connection_id, exc)
        await callback.message.edit_text(
            "😔 Не удалось удалить подключение. Попробуй позже.",
            reply_markup=back_to_menu_keyboard(),
        )
