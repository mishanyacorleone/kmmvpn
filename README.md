# VPN Bot

Telegram бот для управления VPN подписками на базе 3x-ui (VLESS + Reality).

## Стек

- Python 3.10+
- aiogram 3.x
- PostgreSQL + SQLAlchemy async
- 3x-ui (VLESS + Reality)
- ЮКасса (с заглушкой для тестов)

## Структура проекта

```
vpn-bot/
├── main.py                        # точка входа
├── config.py                      # настройки из .env
├── database.py                    # async engine + middleware
├── models/database.py             # SQLAlchemy модели
├── infrastructure/xui_client.py   # HTTP клиент к 3x-ui API
├── repositories/                  # CRUD: user, server, connection
├── services/                      # бизнес-логика
└── bot/
    ├── keyboards/                 # inline клавиатуры
    └── routers/                   # хэндлеры
```

## Быстрый старт

### 1. Клонируй репозиторий

```bash
git clone <repo_url>
cd vpn-bot
```

### 2. Создай виртуальное окружение

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 3. Установи зависимости

```bash
pip install -r requirements.txt
```

### 4. Настрой окружение

```bash
cp .env.example .env
```

Заполни `.env`:

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен бота от @BotFather |
| `BOT_USERNAME` | Username бота без @ |
| `ADMIN_IDS` | Список telegram_id админов, например `[123456789]` |
| `DATABASE_URL` | Строка подключения к PostgreSQL |
| `USE_STUB_PAYMENTS` | `true` для тестов, `false` для ЮКассы |
| `YUKASSA_SHOP_ID` | ID магазина ЮКассы (если `USE_STUB_PAYMENTS=false`) |
| `YUKASSA_SECRET_KEY` | Секретный ключ ЮКассы |
| `SUBSCRIPTION_PRICE_RUB` | Цена подписки в рублях |
| `SUBSCRIPTION_DURATION_DAYS` | Длительность подписки в днях |

### 5. Запусти бота

```bash
python main.py
```

## Управление серверами

Серверы добавляются через админ-панель бота командой `/admin`.

При добавлении сервера потребуется:
- IP адрес VPS
- Порт панели 3x-ui
- Логин и пароль от панели
- ID inbound в панели (видно в списке Inbounds)
- Максимальное количество клиентов

## Переключение на ЮКассу

Когда будешь готов подключить реальную оплату:

1. Зарегистрируй магазин на [yookassa.ru](https://yookassa.ru)
2. Получи `Shop ID` и `Secret Key`
3. В `.env` замени:
```
USE_STUB_PAYMENTS=false
YUKASSA_SHOP_ID=your_shop_id
YUKASSA_SECRET_KEY=your_secret_key
```

## Команды бота

| Команда | Описание |
|---|---|
| `/start` | Главное меню |
| `/admin` | Панель администратора (только для админов) |