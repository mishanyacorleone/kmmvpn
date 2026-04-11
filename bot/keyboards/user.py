from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from models.database import Connection, Server


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню пользователя"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📡 Мои подключения", callback_data="my_connections"))
    builder.row(InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy_subscription"))
    builder.row(InlineKeyboardButton(text="🌍 Серверы", callback_data="servers_list"))
    builder.row(InlineKeyboardButton(text="ℹ️ Мой статус", callback_data="my_status"))
    return builder.as_markup()


def connections_keyboard(connections: list[Connection]) -> InlineKeyboardMarkup:
    """
    Список подключений пользователя.

    Каждое подключение - кнопка с названием сервера и кнопка удаления.
    """
    builder = InlineKeyboardBuilder()

    for conn in connections:
        server_name = conn.server.name if conn.server else f"Сервер #{conn.server_id}"
        builder.row(
            InlineKeyboardButton(
                text=f"🔑 {server_name}",
                callback_data=f"connection_info:{conn.id}",
            ),
            InlineKeyboardButton(
                text="🗑",
                callback_data=f"delete_connection:{conn.id}",
            ),
        )

    builder.row(InlineKeyboardButton(text="➕ Новое подключение", callback_data="new_connection"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    return builder.as_markup()


def new_connection_keyboard(servers: list[Server]) -> InlineKeyboardMarkup:
    """Выбор сервера для нового подключения."""
    builder = InlineKeyboardBuilder()
 
    for server in servers:
        builder.row(
            InlineKeyboardButton(
                text=f"🌍 {server.name}",
                callback_data=f"connect_to_server:{server.id}",
            )
        )
 
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="my_connections"))
    return builder.as_markup()
 
 
def connection_info_keyboard(connection_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра конкретного подключения."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🔑 Показать ключ",
            callback_data=f"show_key:{connection_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🗑 Удалить подключение",
            callback_data=f"delete_connection:{connection_id}",
        )
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="my_connections"))
    return builder.as_markup()
 
 
def confirm_delete_keyboard(connection_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления подключения."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Да, удалить",
            callback_data=f"confirm_delete:{connection_id}",
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"connection_info:{connection_id}",
        ),
    )
    return builder.as_markup()
 
 
def payment_keyboard(confirmation_url: str) -> InlineKeyboardMarkup:
    """Кнопка оплаты и кнопка проверки после оплаты."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💳 Оплатить", url=confirmation_url)
    )
    builder.row(
        InlineKeyboardButton(text="✅ Я оплатил", callback_data="check_payment")
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu"))
    return builder.as_markup()
 
 
def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Просто кнопка назад в главное меню."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ В главное меню", callback_data="main_menu"))
    return builder.as_markup()
