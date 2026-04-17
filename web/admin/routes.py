import logging
from datetime import datetime, timezone

from aiogram import Bot
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session_maker
from repositories.server import ServerRepository
from repositories.user import UserRepository
from repositories.connection import ConnectionRepository
from services.broadcast import broadcast_message
from services.server_manager import server_manager
import os
from fastapi.responses import FileResponse
from web.admin.auth import create_access_token, verify_password, verify_token

UI_PATH = os.path.join(os.path.dirname(__file__), "ui", "index.html")

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin")


@router.get("/", response_class=FileResponse)
async def admin_ui() -> FileResponse:
    """Отдаёт React SPA админки."""
    return FileResponse(UI_PATH)

# Bot instance — устанавливается при старте из main.py
_bot: Bot | None = None


def set_bot(bot: Bot) -> None:
    global _bot
    _bot = bot


def get_bot() -> Bot:
    if not _bot:
        raise HTTPException(status_code=503, detail="Bot не инициализирован")
    return _bot


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


# ── Схемы ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ServerCreateRequest(BaseModel):
    name: str
    host: str
    panel_port: int
    panel_username: str
    panel_password: str
    panel_path: str
    inbound_id: int
    max_clients: int = 20


class BroadcastRequest(BaseModel):
    text: str


class ExtendSubscriptionRequest(BaseModel):
    days: int


# ── Авторизация ───────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """Логин в админку. Возвращает JWT токен."""
    if not verify_password(request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный пароль",
        )
    token = create_access_token()
    logger.info("Успешный вход в админку")
    return LoginResponse(access_token=token)


# ── Статистика ────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(
    _: str = Depends(verify_token),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Общая статистика сервиса."""
    user_repo = UserRepository(session)
    server_repo = ServerRepository(session)

    total_users = await user_repo.count_active()
    subscribed_users = await user_repo.count_with_subscription()
    servers = await server_repo.get_all_active()

    return {
        "total_users": total_users,
        "subscribed_users": subscribed_users,
        "active_servers": len(servers),
    }


# ── Серверы ───────────────────────────────────────────────────────────────────

@router.get("/servers")
async def list_servers(
    _: str = Depends(verify_token),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Список всех серверов с текущей нагрузкой."""
    servers = await ServerRepository(session).get_all_active()
    result = []

    for server in servers:
        stats = await server_manager.get_inbound_stats(server)
        client_count = await ServerRepository(session).get_client_count(server.id)

        result.append({
            "id": server.id,
            "name": server.name,
            "host": server.host,
            "panel_port": server.panel_port,
            "inbound_id": server.inbound_id,
            "max_clients": server.max_clients,
            "current_clients": client_count,
            "is_active": server.is_active,
            "up_bytes": stats.up_bytes if stats else 0,
            "down_bytes": stats.down_bytes if stats else 0,
            "online": stats is not None,
        })

    return result


@router.post("/servers")
async def create_server(
    request: ServerCreateRequest,
    _: str = Depends(verify_token),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Добавляет новый сервер."""
    server = await ServerRepository(session).create(
        name=request.name,
        host=request.host,
        panel_port=request.panel_port,
        panel_username=request.panel_username,
        panel_password=request.panel_password,
        panel_path=request.panel_path,
        inbound_id=request.inbound_id,
        max_clients=request.max_clients,
    )
    return {"id": server.id, "name": server.name, "host": server.host}


@router.delete("/servers/{server_id}")
async def delete_server(
    server_id: int,
    _: str = Depends(verify_token),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Удаляет сервер."""
    await ServerRepository(session).delete(server_id)
    server_manager.remove_client(server_id)
    return {"ok": True}


@router.patch("/servers/{server_id}/toggle")
async def toggle_server(
    server_id: int,
    _: str = Depends(verify_token),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Включает или отключает сервер."""
    repo = ServerRepository(session)
    server = await repo.get_by_id(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Сервер не найден")
    await repo.set_active(server_id, not server.is_active)
    return {"id": server_id, "is_active": not server.is_active}


# ── Пользователи ──────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    _: str = Depends(verify_token),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Список всех пользователей."""
    users = await UserRepository(session).get_all_active()
    now = datetime.now(timezone.utc)
    result = []

    for user in users:
        connections = await ConnectionRepository(session).get_user_connections(user.id)
        has_sub = (
            user.subscription_expires_at is not None
            and user.subscription_expires_at > now
        )
        result.append({
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "has_subscription": has_sub,
            "subscription_expires_at": (
                user.subscription_expires_at.isoformat()
                if user.subscription_expires_at else None
            ),
            "connections_count": len(connections),
            "created_at": user.created_at.isoformat(),
        })

    return result


@router.post("/users/{telegram_id}/extend")
async def extend_user_subscription(
    telegram_id: int,
    request: ExtendSubscriptionRequest,
    _: str = Depends(verify_token),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Продлевает подписку пользователя вручную."""
    from services.subscription import SubscriptionService
    new_expires = await SubscriptionService(session).extend_and_sync(
        telegram_id=telegram_id,
        days=request.days,
    )
    return {
        "telegram_id": telegram_id,
        "subscription_expires_at": new_expires.isoformat(),
    }


@router.delete("/users/{telegram_id}/connections")
async def deactivate_user_connections(
    telegram_id: int,
    _: str = Depends(verify_token),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Деактивирует все подключения пользователя."""
    from services.connection import ConnectionService
    await ConnectionService(session).deactivate_all_connections(telegram_id)
    return {"ok": True}


# ── Рассылка ──────────────────────────────────────────────────────────────────

@router.post("/broadcast")
async def send_broadcast(
    request: BroadcastRequest,
    _: str = Depends(verify_token),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Отправляет сообщение всем пользователям."""
    bot = get_bot()
    success, errors = await broadcast_message(
        bot=bot,
        session=session,
        text=request.text,
    )
    logger.info("Рассылка из админки: %d успешно, %d ошибок", success, errors)
    return {"success": success, "errors": errors}