import logging
from collections.abc import AsyncGenerator

import aiohttp
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database import async_session_maker
from models.database import Connection

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def _fetch_vless_key(host: str, sub_port: int, sub_id: str) -> str:
    """
    Получает vless ключ из x-ui подписки конкретного сервера.

    Каждый сервер имеет свой хост и порт подписок.
    """
    url = f"https://{host}:{sub_port}/sub/{sub_id}"
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False)
    ) as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise HTTPException(status_code=404, detail="Подписка не найдена")

            import base64
            raw = await response.read()
            try:
                decoded = base64.b64decode(raw).decode("utf-8")
                keys = [line for line in decoded.splitlines() if line.startswith("vless://")]
                if keys:
                    return keys[0]
            except Exception:
                pass

            text = raw.decode("utf-8")
            for line in text.splitlines():
                if line.startswith("vless://"):
                    return line

            raise HTTPException(status_code=404, detail="Ключ не найден в подписке")


@router.get("/connect/{sub_id}", response_class=HTMLResponse)
async def connect_page(
    sub_id: str,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """
    Страница подключения с vless ключом и инструкцией.

    Находит сервер по sub_id из БД и получает ключ с нужного хоста.
    """
    from config import settings

    # Находим подключение по sub_id чтобы узнать хост сервера
    result = await session.execute(
        select(Connection)
        .options(joinedload(Connection.server))
        .where(Connection.xui_sub_id == sub_id)
    )
    connection = result.scalar_one_or_none()

    if not connection or not connection.server:
        raise HTTPException(status_code=404, detail="Подключение не найдено")

    server = connection.server
    sub_port = settings.xui_sub_port  # порт подписок одинаковый для всех серверов

    try:
        vless_key = await _fetch_vless_key(server.host, sub_port, sub_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Ошибка получения ключа для sub_id %s: %s", sub_id, exc)
        raise HTTPException(status_code=500, detail="Ошибка получения ключа")

    sub_url = f"https://{server.host}:{sub_port}/sub/{sub_id}"
    html = _render_connect_page(vless_key, sub_url)
    return HTMLResponse(content=html)


def _render_connect_page(vless_key: str, sub_url: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VPN Подключение</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #0f0f13; color: #e8e8f0;
      min-height: 100vh; padding: 24px 16px;
    }}
    .container {{ max-width: 640px; margin: 0 auto; }}
    .header {{ text-align: center; margin-bottom: 32px; }}
    .logo {{ font-size: 40px; margin-bottom: 8px; }}
    h1 {{ font-size: 24px; font-weight: 700; color: #fff; margin-bottom: 4px; }}
    .subtitle {{ font-size: 14px; color: #888; }}
    .card {{
      background: #1a1a24; border: 1px solid #2a2a3a;
      border-radius: 16px; padding: 24px; margin-bottom: 16px;
    }}
    .card-title {{
      font-size: 13px; font-weight: 600; color: #888;
      text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 16px;
    }}
    .key-block {{
      background: #0f0f13; border: 1px solid #2a2a3a; border-radius: 10px;
      padding: 14px; font-family: monospace; font-size: 11px;
      color: #a0c4ff; word-break: break-all; line-height: 1.6; margin-bottom: 12px;
    }}
    .btn {{
      display: flex; align-items: center; justify-content: center; gap: 8px;
      width: 100%; padding: 14px; border-radius: 10px; border: none;
      font-size: 15px; font-weight: 600; cursor: pointer;
      transition: all 0.15s; text-decoration: none; margin-bottom: 8px;
    }}
    .btn-primary {{ background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; }}
    .btn-primary:hover {{ opacity: 0.9; transform: translateY(-1px); }}
    .btn-secondary {{ background: #2a2a3a; color: #e8e8f0; }}
    .btn-secondary:hover {{ background: #333345; }}
    .copied {{ background: linear-gradient(135deg, #10b981, #059669) !important; }}
    .qr-wrapper {{
      display: flex; justify-content: center; padding: 16px;
      background: white; border-radius: 12px; margin-bottom: 12px;
    }}
    .apps-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    .app-card {{
      background: #0f0f13; border: 1px solid #2a2a3a; border-radius: 10px;
      padding: 14px; text-align: center; text-decoration: none;
      color: #e8e8f0; transition: border-color 0.15s;
    }}
    .app-card:hover {{ border-color: #6366f1; }}
    .app-icon {{ font-size: 28px; margin-bottom: 6px; }}
    .app-name {{ font-size: 13px; font-weight: 600; }}
    .app-platform {{ font-size: 11px; color: #888; margin-top: 2px; }}
    .steps {{ list-style: none; }}
    .step {{
      display: flex; gap: 14px; padding: 12px 0;
      border-bottom: 1px solid #2a2a3a;
    }}
    .step:last-child {{ border-bottom: none; }}
    .step-num {{
      width: 28px; height: 28px; border-radius: 50%;
      background: linear-gradient(135deg, #6366f1, #8b5cf6);
      display: flex; align-items: center; justify-content: center;
      font-size: 13px; font-weight: 700; flex-shrink: 0;
    }}
    .step-text {{ font-size: 14px; line-height: 1.5; padding-top: 4px; color: #c8c8d8; }}
    .step-text b {{ color: #fff; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="logo">🔐</div>
      <h1>Твоё подключение</h1>
      <p class="subtitle">Следуй инструкции ниже чтобы подключиться</p>
    </div>
    <div class="card">
      <div class="card-title">🔑 Ключ подключения</div>
      <div class="key-block" id="vless-key">{vless_key}</div>
      <button class="btn btn-primary" onclick="copyKey()" id="copy-btn">
        <span>📋</span> Скопировать ключ
      </button>
      <button class="btn btn-secondary" onclick="copySubUrl()">
        🔗 Скопировать ссылку подписки
      </button>
      <span id="sub-url" style="display:none">{sub_url}</span>
    </div>
    <div class="card">
      <div class="card-title">📷 QR код</div>
      <div class="qr-wrapper"><div id="qrcode"></div></div>
      <p style="font-size:13px;color:#888;text-align:center">Отсканируй камерой телефона</p>
    </div>
    <div class="card">
      <div class="card-title">📱 Скачай приложение</div>
      <div class="apps-grid">
        <a class="app-card" href="https://apps.apple.com/app/hiddify-proxy-vpn/id6596777532" target="_blank">
          <div class="app-icon">🍎</div>
          <div class="app-name">Hiddify</div>
          <div class="app-platform">iOS / macOS</div>
        </a>
        <a class="app-card" href="https://play.google.com/store/apps/details?id=app.hiddify.com" target="_blank">
          <div class="app-icon">🤖</div>
          <div class="app-name">Hiddify</div>
          <div class="app-platform">Android</div>
        </a>
        <a class="app-card" href="https://github.com/2dust/v2rayNG/releases/latest" target="_blank">
          <div class="app-icon">⚡</div>
          <div class="app-name">v2rayNG</div>
          <div class="app-platform">Android</div>
        </a>
        <a class="app-card" href="https://github.com/MatsuriDayo/nekoray/releases/latest" target="_blank">
          <div class="app-icon">🐱</div>
          <div class="app-name">Nekoray</div>
          <div class="app-platform">Windows / Linux</div>
        </a>
      </div>
    </div>
    <div class="card">
      <div class="card-title">📖 Инструкция</div>
      <ol class="steps">
        <li class="step">
          <div class="step-num">1</div>
          <div class="step-text">Скачай <b>Hiddify</b> — работает на всех устройствах</div>
        </li>
        <li class="step">
          <div class="step-num">2</div>
          <div class="step-text">Нажми <b>«Скопировать ключ»</b> выше</div>
        </li>
        <li class="step">
          <div class="step-num">3</div>
          <div class="step-text">В Hiddify нажми <b>«+»</b> → <b>«Вставить из буфера»</b></div>
        </li>
        <li class="step">
          <div class="step-num">4</div>
          <div class="step-text">Нажми <b>кнопку подключения</b> — готово! 🎉</div>
        </li>
      </ol>
    </div>
  </div>
  <script>
    new QRCode(document.getElementById("qrcode"), {{
      text: "{vless_key}",
      width: 200, height: 200,
      colorDark: "#000000", colorLight: "#ffffff",
      correctLevel: QRCode.CorrectLevel.M
    }});
    function copyKey() {{
      navigator.clipboard.writeText(document.getElementById("vless-key").innerText).then(() => {{
        const btn = document.getElementById("copy-btn");
        btn.classList.add("copied");
        btn.innerHTML = "<span>✅</span> Скопировано!";
        setTimeout(() => {{
          btn.classList.remove("copied");
          btn.innerHTML = "<span>📋</span> Скопировать ключ";
        }}, 2000);
      }});
    }}
    function copySubUrl() {{
      navigator.clipboard.writeText(document.getElementById("sub-url").innerText)
        .then(() => alert("Ссылка подписки скопирована!"));
    }}
  </script>
</body>
</html>"""
