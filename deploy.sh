#!/bin/bash

# Быстрый деплой на VPS
# Использование: ./deploy.sh [user@server]

set -e

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Проверяем параметры
if [ $# -eq 0 ]; then
    error "Использование: $0 user@server"
    echo "Пример: $0 root@192.168.1.100"
    exit 1
fi

SERVER="$1"
REMOTE_DIR="wordly-bot"

log "🚀 Деплой Wordly Bot на $SERVER"

# Проверяем подключение к серверу
if ! ssh -o ConnectTimeout=5 "$SERVER" exit 2>/dev/null; then
    error "Не удается подключиться к серверу $SERVER"
    exit 1
fi

log "📦 Копируем файлы на сервер..."

# Создаем директорию на сервере
ssh "$SERVER" "mkdir -p $REMOTE_DIR"

# Копируем необходимые файлы
rsync -avz --progress \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='slovli.db' \
    --exclude='data/' \
    ./ "$SERVER:$REMOTE_DIR/"

log "⚙️  Настройка на сервере..."

# Выполняем команды на сервере
ssh "$SERVER" << 'ENDSSH'
cd wordly-bot

# Проверяем Docker
if ! command -v docker &> /dev/null; then
    echo "Устанавливаем Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    usermod -aG docker $USER
fi

# Проверяем docker-compose
if ! command -v docker-compose &> /dev/null; then
    echo "Устанавливаем Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/download/v2.21.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Создаем .env если его нет
if [ ! -f .env ]; then
    echo "Создаем .env файл..."
    cp env.example .env
    echo "⚠️  ВАЖНО: Отредактируйте .env файл!"
fi

# Создаем директорию для данных
mkdir -p data

# Останавливаем старую версию если запущена
docker-compose down 2>/dev/null || true

# Собираем и запускаем
echo "Сборка и запуск..."
docker-compose build --no-cache
docker-compose up -d

# Создаем systemd сервис
echo "Создаем systemd сервис..."
sudo cp wordly-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wordly-bot

echo "✅ Деплой завершен!"
ENDSSH

log "🎉 Деплой успешно завершен!"
echo
echo "📝 Следующие шаги на сервере $SERVER:"
echo "1. Отредактируйте файл .env: nano ~/wordly-bot/.env"
echo "2. Перезапустите бота: cd ~/wordly-bot && docker-compose restart"
echo "3. Проверьте логи: cd ~/wordly-bot && docker-compose logs -f"
echo
echo "🔧 SSH команды для управления:"
echo "   ssh $SERVER 'cd wordly-bot && docker-compose logs -f'"
echo "   ssh $SERVER 'cd wordly-bot && docker-compose restart'"
echo "   ssh $SERVER 'systemctl status wordly-bot'"
