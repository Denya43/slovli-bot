#!/bin/bash

# Цвета для красивого вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
RESET='\033[0m'

# Функция для красивого вывода
log() {
    echo -e "${GREEN}[INFO]${RESET} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${RESET} $1"
}

error() {
    echo -e "${RED}[ERROR]${RESET} $1"
}

info() {
    echo -e "${BLUE}[INFO]${RESET} $1"
}

# Проверяем, что скрипт запущен от root
if [[ $EUID -ne 0 ]]; then
   error "Этот скрипт должен запускаться от root!"
   exit 1
fi

# Настройки по умолчанию
USERNAME="wordly"
PROJECT_DIR="/home/$USERNAME/slovli-bot"
GITHUB_REPO="https://github.com/Denya43/slovli-bot.git"

log "🚀 Автоматическая установка Slovli Bot от root"
log "Создаем пользователя и устанавливаем бота..."

# Проверяем наличие необходимых пакетов
log "📦 Проверяем необходимые пакеты..."
if ! command -v git &> /dev/null; then
    log "Устанавливаем git..."
    apt-get update && apt-get install -y git
fi

if ! command -v curl &> /dev/null; then
    log "Устанавливаем curl..."
    apt-get install -y curl
fi

# Создаем пользователя
log "👤 Создаем пользователя $USERNAME..."
if id "$USERNAME" &>/dev/null; then
    warn "Пользователь $USERNAME уже существует"
else
    adduser --disabled-password --gecos "" "$USERNAME"
    log "Пользователь $USERNAME создан"
fi

# Устанавливаем Docker если его нет
if ! command -v docker &> /dev/null; then
    log "🐳 Устанавливаем Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
fi

# Добавляем пользователя в группу docker
usermod -aG docker "$USERNAME"

# Клонируем репозиторий
log "📥 Клонируем репозиторий..."
if [ -d "$PROJECT_DIR" ]; then
    warn "Директория $PROJECT_DIR уже существует, обновляем..."
    rm -rf "$PROJECT_DIR"
fi

git clone "$GITHUB_REPO" "$PROJECT_DIR"

# Устанавливаем правильные права
log "🔐 Устанавливаем права доступа..."
chown -R "$USERNAME:$USERNAME" "$PROJECT_DIR"
chmod +x "$PROJECT_DIR"/*.sh 2>/dev/null || true

# Создаем .env файл если его нет
ENV_FILE="$PROJECT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    log "⚙️ Создаем .env файл..."
    cat > "$ENV_FILE" << EOF
# Telegram Bot Token (получите у @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# ID администратора (ваш Telegram ID, получите у @userinfobot)
SLOVLI_ADMIN_USER_ID=your_admin_id_here

# Файлы (не изменяйте, если не знаете что делаете)
SLOVLI_WORDS_FILE=words.txt
SLOVLI_DB_FILE=/app/data/slovli.db
EOF
    chown "$USERNAME:$USERNAME" "$ENV_FILE"
    warn "⚠️  Отредактируйте файл $ENV_FILE перед запуском!"
fi

# Создаем systemd сервис
log "🔧 Создаем systemd сервис..."
SERVICE_FILE="/etc/systemd/system/wordly-bot.service"
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Slovli Telegram Bot
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0
User=$USERNAME
Group=$USERNAME

[Install]
WantedBy=multi-user.target
EOF

# Перезагружаем systemd и включаем сервис
systemctl daemon-reload
systemctl enable wordly-bot

# Устанавливаем Docker Compose если его нет
if ! command -v docker-compose &> /dev/null; then
    log "🐳 Устанавливаем Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Создаем скрипт для управления
MANAGE_SCRIPT="$PROJECT_DIR/manage.sh"
cat > "$MANAGE_SCRIPT" << 'EOF'
#!/bin/bash

# Цвета для красивого вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
RESET='\033[0m'

log() {
    echo -e "${GREEN}[INFO]${RESET} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${RESET} $1"
}

error() {
    echo -e "${RED}[ERROR]${RESET} $1"
}

show_help() {
    echo -e "${BLUE}📋 Slovli Bot - Управление${RESET}"
    echo
    echo "Использование: $0 [КОМАНДА]"
    echo
    echo "Команды:"
    echo "  start     - Запустить бота"
    echo "  stop      - Остановить бота"
    echo "  restart   - Перезапустить бота"
    echo "  status    - Статус бота"
    echo "  logs      - Показать логи"
    echo "  update    - Обновить бота"
    echo "  help      - Показать эту справку"
    echo
    echo "Примеры:"
    echo "  $0 start     # Запустить бота"
    echo "  $0 logs      # Показать логи"
}

ACTION=${1:-help}

case $ACTION in
    start)
        log "🚀 Запускаем бота..."
        docker-compose up -d
        systemctl start wordly-bot
        log "✅ Бот запущен!"
        ;;
    
    stop)
        log "⏹️ Останавливаем бота..."
        docker-compose down
        systemctl stop wordly-bot
        log "✅ Бот остановлен!"
        ;;
    
    restart)
        log "🔄 Перезапускаем бота..."
        docker-compose down
        docker-compose up -d
        systemctl restart wordly-bot
        log "✅ Бот перезапущен!"
        ;;
    
    status)
        log "📊 Статус бота..."
        systemctl status wordly-bot --no-pager
        echo
        docker-compose ps
        ;;
    
    logs)
        log "📜 Показываем логи..."
        docker-compose logs -f --tail=50
        ;;
    
    update)
        log "📥 Обновляем бота..."
        git pull origin main
        docker-compose down
        docker-compose build --no-cache
        docker-compose up -d
        log "✅ Бот обновлен!"
        ;;
    
    help|h|--help)
        show_help
        ;;
    
    *)
        error "Неизвестная команда: $ACTION"
        echo
        show_help
        exit 1
        ;;
esac
EOF

chmod +x "$MANAGE_SCRIPT"
chown "$USERNAME:$USERNAME" "$MANAGE_SCRIPT"

# Финальные инструкции
log "🎉 Установка завершена!"
echo
info "📋 Что дальше:"
echo "1. Отредактируйте файл $ENV_FILE:"
echo "   - Установите TELEGRAM_BOT_TOKEN"
echo "   - Установите SLOVLI_ADMIN_USER_ID"
echo
echo "2. Запустите бота:"
echo "   sudo systemctl start wordly-bot"
echo "   или"
echo "   su - $USERNAME"
echo "   cd slovli-bot"
echo "   ./manage.sh start"
echo
echo "3. Управление ботом:"
echo "   su - $USERNAME"
echo "   cd slovli-bot"
echo "   ./manage.sh [команда]"
echo
echo "4. Просмотр логов:"
echo "   ./manage.sh logs"
echo
warn "⚠️  ВАЖНО: Отредактируйте .env файл перед запуском!"
log "✅ Установка завершена успешно!"
