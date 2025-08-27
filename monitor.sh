#!/bin/bash

# Скрипт мониторинга Wordly Bot
# Использование: ./monitor.sh

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Функции
log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }

# Заголовок
echo -e "${BLUE}╔══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           Wordly Bot Monitor         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════╝${NC}"
echo

# Проверяем Docker
info "🐳 Проверка Docker..."
if ! command -v docker &> /dev/null; then
    error "Docker не установлен!"
    exit 1
else
    DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | cut -d',' -f1)
    log "Docker версия: $DOCKER_VERSION"
fi

# Проверяем Docker Compose
if ! command -v docker-compose &> /dev/null; then
    error "Docker Compose не установлен!"
    exit 1
else
    COMPOSE_VERSION=$(docker-compose --version | cut -d' ' -f4 | cut -d',' -f1)
    log "Docker Compose версия: $COMPOSE_VERSION"
fi

echo

# Статус контейнеров
info "📦 Статус контейнеров:"
docker-compose ps

echo

# Использование ресурсов
info "💻 Использование ресурсов:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"

echo

# Логи (последние 10 строк)
info "📝 Последние логи:"
docker-compose logs --tail=10

echo

# Проверка .env файла
info "⚙️  Проверка конфигурации:"
if [ ! -f .env ]; then
    error "Файл .env не найден!"
else
    if grep -q "your_bot_token_here" .env; then
        error "Токен бота не настроен в .env"
    else
        log "Токен бота настроен"
    fi
    
    if grep -q "SLOVLI_ADMIN_USER_ID=0" .env; then
        error "ID администратора не настроен в .env"
    else
        log "ID администратора настроен"
    fi
fi

echo

# Проверка базы данных
info "🗄️  Проверка базы данных:"
if [ -f "data/slovli.db" ]; then
    DB_SIZE=$(du -h data/slovli.db | cut -f1)
    log "База данных: $DB_SIZE"
else
    warn "База данных не найдена (будет создана при первом запуске)"
fi

# Проверка словаря
if [ -f "words.txt" ]; then
    WORD_COUNT=$(wc -l < words.txt)
    log "Словарь содержит: $WORD_COUNT слов"
else
    error "Файл словаря words.txt не найден!"
fi

echo

# Системная информация
info "🖥️  Системная информация:"
echo "   Время работы: $(uptime -p 2>/dev/null || uptime)"
echo "   Свободная память: $(free -h | awk '/^Mem:/ {print $7}' 2>/dev/null || echo 'N/A')"
echo "   Свободное место: $(df -h . | awk 'NR==2 {print $4}')"

echo

# Проверка systemd сервиса
info "🔧 Проверка systemd сервиса:"
if systemctl is-active --quiet wordly-bot 2>/dev/null; then
    log "Сервис wordly-bot активен"
else
    warn "Сервис wordly-bot неактивен или не настроен"
fi

if systemctl is-enabled --quiet wordly-bot 2>/dev/null; then
    log "Автозапуск включен"
else
    warn "Автозапуск отключен"
fi

echo

# Полезные команды
info "🔧 Полезные команды:"
echo "   Логи в реальном времени: docker-compose logs -f"
echo "   Перезапуск бота:         docker-compose restart"
echo "   Остановка бота:          docker-compose down"
echo "   Обновление проекта:      git pull && docker-compose build --no-cache"
echo "   Проверка конфигурации:   docker-compose config"
