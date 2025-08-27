#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверяем, что скрипт запущен с правами root
if [[ $EUID -eq 0 ]]; then
   error "Этот скрипт не должен запускаться от root!"
   exit 1
fi

log "🚀 Установка Wordly Bot на VPS"
echo

# Проверяем наличие git
if ! command -v git &> /dev/null; then
    error "Git не установлен. Установите git и повторите попытку."
    exit 1
fi

# Проверяем наличие docker
if ! command -v docker &> /dev/null; then
    warn "Docker не найден. Устанавливаем Docker..."
    
    # Обновляем пакеты
    sudo apt-get update
    
    # Устанавливаем зависимости
    sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
    
    # Добавляем официальный GPG ключ Docker
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    
    # Добавляем репозиторий Docker
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Обновляем пакеты и устанавливаем Docker
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io
    
    # Добавляем пользователя в группу docker
    sudo usermod -aG docker $USER
    
    log "Docker установлен успешно!"
else
    log "Docker уже установлен"
fi

# Проверяем наличие docker-compose
if ! command -v docker-compose &> /dev/null; then
    warn "Docker Compose не найден. Устанавливаем..."
    
    # Скачиваем последнюю версию docker-compose
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.21.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    
    # Делаем файл исполняемым
    sudo chmod +x /usr/local/bin/docker-compose
    
    log "Docker Compose установлен успешно!"
else
    log "Docker Compose уже установлен"
fi

# Определяем директорию для установки (домашняя директория пользователя)
INSTALL_DIR="$HOME"
TEMP_DIR="/tmp/wordly-bot-install"

# Клонируем репозиторий во временную директорию
if [ -d "$TEMP_DIR" ]; then
    rm -rf "$TEMP_DIR"
fi

log "Клонируем репозиторий..."
git clone https://github.com/Denya43/slovli-bot.git "$TEMP_DIR"

# Копируем все файлы проекта в домашнюю директорию
log "Копируем файлы проекта в $INSTALL_DIR..."
cd "$TEMP_DIR"

# Копируем все файлы кроме .git
cp -r wordly_bot/ "$INSTALL_DIR/"
cp requirements.txt "$INSTALL_DIR/"
cp words.txt "$INSTALL_DIR/"
cp docker-compose.yml "$INSTALL_DIR/"
cp Dockerfile "$INSTALL_DIR/"
cp Makefile "$INSTALL_DIR/"
cp .dockerignore "$INSTALL_DIR/"
cp wordly-bot.service "$INSTALL_DIR/"

# Переходим в домашнюю директорию
cd "$INSTALL_DIR"

# Создаем директорию для данных
mkdir -p data

# Удаляем временную директорию
rm -rf "$TEMP_DIR"

# Создаем .env файл если его нет
if [ ! -f ".env" ]; then
    log "Создаем файл конфигурации .env..."
    cat > .env << 'EOF'
# Telegram Bot Token (получите у @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# ID администратора (ваш Telegram ID, получите у @userinfobot)
SLOVLI_ADMIN_USER_ID=0

# Файлы (не изменяйте, если не знаете что делаете)
SLOVLI_WORDS_FILE=words.txt
SLOVLI_DB_FILE=/app/data/slovli.db
EOF
    
    warn "⚠️  ВАЖНО: Отредактируйте файл .env и укажите ваш токен бота и ID администратора!"
    echo "   Файл находится в: $INSTALL_DIR/.env"
    echo
    echo "   1. Получите токен бота у @BotFather в Telegram"
    echo "   2. Получите ваш ID у @userinfobot в Telegram"
    echo "   3. Замените значения в файле .env"
    echo
else
    log "Файл .env уже существует"
fi

# Создаем systemd сервис
log "Создаем systemd сервис..."
DOCKER_COMPOSE_PATH=$(which docker-compose || echo "/usr/local/bin/docker-compose")
sudo tee /etc/systemd/system/wordly-bot.service > /dev/null << EOF
[Unit]
Description=Wordly Telegram Bot
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$INSTALL_DIR
ExecStart=$DOCKER_COMPOSE_PATH up -d
ExecStop=$DOCKER_COMPOSE_PATH down
TimeoutStartSec=0
User=$USER
Group=$USER

[Install]
WantedBy=multi-user.target
EOF

# Перезагружаем systemd
sudo systemctl daemon-reload

# Включаем автозапуск
sudo systemctl enable wordly-bot.service

log "✅ Установка завершена!"
echo
echo "📝 Следующие шаги:"
echo "1. Отредактируйте файл ~/.env"
echo "2. Запустите бота: sudo systemctl start wordly-bot"
echo "3. Проверьте статус: sudo systemctl status wordly-bot"
echo "4. Просмотр логов: docker-compose logs -f"
echo
echo "🔧 Полезные команды:"
echo "   Запуск:     sudo systemctl start wordly-bot"
echo "   Остановка:  sudo systemctl stop wordly-bot"
echo "   Перезапуск: sudo systemctl restart wordly-bot"
echo "   Логи:       docker-compose logs -f"
echo "   Обновление: curl -fsSL https://raw.githubusercontent.com/Denya43/slovli-bot/main/install.sh | bash"
echo
echo "📁 Все файлы установлены в домашнюю директорию: $HOME"
echo

if [ ! -f ".env" ] || grep -q "your_bot_token_here" .env; then
    error "⚠️  НЕ ЗАБУДЬТЕ настроить .env файл перед запуском!"
    echo "   Выполните: nano ~/.env"
fi
