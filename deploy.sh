#!/bin/bash
set -e

echo "🚀 Деплой vpn-bot..."

# Подтягиваем изменения с GitHub
echo "📥 git pull..."
git pull origin main

# Пересобираем и перезапускаем контейнеры
# --build - пересобрать образ, если изменился код
# --no_deps - не трогать зависимые сервисы (postgres)
# -d - в фоне
echo "🐳 Пересобираем app контейнер..."
docker compose up -d --build app

# Перезагружаем nginx если изменился конфиг
echo "🔄 Перезагружаем nginx..."
docker compose exec nginx nginx -s reload 2>/dev/null || true

# Показываем статус
echo ""
echo "✅ Деплой завершён!"
echo ""
docker compose ps
