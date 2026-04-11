from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from models.database import Server


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню администратора."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🖥 Серверы", callback_data="admin_servers"))
    builder.row(InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"))
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    return builder.as_markup()


def admin_servers_keyboard(servers: list[Server]) -> InlineKeyboardMarkup:
    """Список серверов с кнопками управления."""
    builder = InlineKeyboardBuilder()

    for server in servers:
        status = "🟢" if server.is_active else "🔴"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {server.name}",
                callback_data=f"admin_server_info:{server.id}",
            )
        )

    builder.row(InlineKeyboardButton(text="➕ Добавить сервер", callback_data="admin_add_server"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu"))
    return builder.as_markup()


def admin_server_actions_keyboard(server_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Действия с конкретным сервером."""
    builder = InlineKeyboardBuilder()

    toggle_text = "🔴 Отключить" if is_active else "🟢 Включить"
    builder.row(
        InlineKeyboardButton(
            text=toggle_text,
            callback_data=f"admin_toggle_server:{server_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🗑 Удалить сервер",
            callback_data=f"admin_delete_server:{server_id}",
        )
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_servers"))
    return builder.as_markup()


def admin_confirm_delete_server_keyboard(server_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления сервера."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Да, удалить",
            callback_data=f"admin_confirm_delete_server:{server_id}",
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"admin_server_info:{server_id}",
        ),
    )
    return builder.as_markup()


def admin_confirm_broadcast_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение рассылки."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📢 Отправить всем", callback_data="admin_confirm_broadcast"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_menu"),
    )
    return builder.as_markup()


def admin_back_keyboard() -> InlineKeyboardMarkup:
    """Кнопка назад в админ меню."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu"))
    return builder.as_markup()