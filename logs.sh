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

# Функция показа помощи
show_help() {
    echo -e "${BLUE}📋 Wordly Bot - Просмотр логов${RESET}"
    echo
    echo "Использование: $0 [ОПЦИЯ]"
    echo
    echo "Опции:"
    echo "  live      - Следить за логами в реальном времени (по умолчанию)"
    echo "  all       - Показать все логи"
    echo "  tail      - Показать последние 50 строк"
    echo "  today     - Логи за сегодня"
    echo "  errors    - Только ошибки"
    echo "  system    - Системные логи (systemctl)"
    echo "  docker    - Статус Docker контейнеров"
    echo "  help      - Показать эту справку"
    echo
    echo "Примеры:"
    echo "  $0 live     # Следить за логами"
    echo "  $0 errors   # Показать только ошибки"
    echo "  $0 system   # Системные логи"
}

# Проверяем наличие docker-compose
if ! command -v docker-compose &> /dev/null; then
    error "docker-compose не найден!"
    exit 1
fi

# Проверяем наличие docker-compose.yml
if [ ! -f "docker-compose.yml" ]; then
    error "Файл docker-compose.yml не найден!"
    echo "Убедитесь, что вы находитесь в директории проекта."
    exit 1
fi

# Получаем параметр
ACTION=${1:-live}

case $ACTION in
    live|follow|f)
        log "📺 Следим за логами в реальном времени (Ctrl+C для выхода)..."
        docker-compose logs -f --tail=20
        ;;
    
    all|full)
        log "📜 Показываем все логи..."
        docker-compose logs
        ;;
    
    tail|last)
        log "📋 Последние 50 строк логов..."
        docker-compose logs --tail=50
        ;;
    
    today)
        log "📅 Логи за сегодня..."
        TODAY=$(date +%Y-%m-%d)
        docker-compose logs --since="$TODAY"
        ;;
    
    errors|err)
        log "🚨 Показываем только ошибки..."
        docker-compose logs 2>/dev/null | grep -i -E "(error|exception|traceback|failed|critical)" --color=always
        ;;
    
    system|systemctl)
        log "🔧 Системные логи бота..."
        if systemctl is-active --quiet wordly-bot; then
            echo -e "${GREEN}✅ Сервис активен${RESET}"
        else
            echo -e "${RED}❌ Сервис неактивен${RESET}"
        fi
        echo
        echo "Статус сервиса:"
        systemctl status wordly-bot --no-pager
        echo
        echo "Последние логи systemd:"
        journalctl -u wordly-bot --no-pager -n 20
        ;;
    
    docker|status)
        log "🐳 Статус Docker контейнеров..."
        echo "Контейнеры:"
        docker-compose ps
        echo
        echo "Использование ресурсов:"
        docker stats --no-stream wordly-bot 2>/dev/null || echo "Контейнер не запущен"
        ;;
    
    help|h|--help)
        show_help
        ;;
    
    *)
        error "Неизвестная опция: $ACTION"
        echo
        show_help
        exit 1
        ;;
esac
