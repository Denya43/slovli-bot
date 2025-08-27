# Wordly Bot Management

.PHONY: help build start stop restart logs status clean install update

# Цвета для красивого вывода
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

help: ## Показать справку
	@echo "$(GREEN)Wordly Bot - Команды управления$(RESET)"
	@echo
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "$(YELLOW)%-12s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Собрать Docker образ
	@echo "$(GREEN)Сборка Docker образа...$(RESET)"
	docker-compose build --no-cache

start: ## Запустить бота
	@echo "$(GREEN)Запуск бота...$(RESET)"
	docker-compose up -d

stop: ## Остановить бота
	@echo "$(YELLOW)Остановка бота...$(RESET)"
	docker-compose down

restart: stop start ## Перезапустить бота

logs: ## Показать логи (следить за новыми)
	@echo "$(GREEN)Логи бота (Ctrl+C для выхода):$(RESET)"
	docker-compose logs -f

logs-all: ## Показать все логи
	@echo "$(GREEN)Все логи бота:$(RESET)"
	docker-compose logs

logs-tail: ## Показать последние 50 строк логов
	@echo "$(GREEN)Последние 50 строк логов:$(RESET)"
	docker-compose logs --tail=50

logs-today: ## Показать логи за сегодня
	@echo "$(GREEN)Логи за сегодня:$(RESET)"
	docker-compose logs --since="$(shell date +%Y-%m-%d)"

logs-errors: ## Показать только ошибки
	@echo "$(GREEN)Логи с ошибками:$(RESET)"
	docker-compose logs | grep -i "error\|exception\|traceback\|failed"

status: ## Показать статус контейнеров
	@echo "$(GREEN)Статус контейнеров:$(RESET)"
	docker-compose ps

clean: ## Очистить неиспользуемые Docker ресурсы
	@echo "$(YELLOW)Очистка Docker ресурсов...$(RESET)"
	docker system prune -f
	docker volume prune -f

install: ## Установить зависимости локально
	@echo "$(GREEN)Установка зависимостей...$(RESET)"
	pip install -r requirements.txt

update: ## Обновить проект и перезапустить
	@echo "$(GREEN)Обновление проекта...$(RESET)"
	git pull
	$(MAKE) build
	$(MAKE) restart
	@echo "$(GREEN)Обновление завершено!$(RESET)"

setup-env: ## Создать .env файл из примера
	@if [ ! -f .env ]; then \
		echo "$(GREEN)Создание .env файла...$(RESET)"; \
		cp env.example .env; \
		echo "$(YELLOW)⚠️  Отредактируйте .env файл перед запуском!$(RESET)"; \
	else \
		echo "$(RED)Файл .env уже существует$(RESET)"; \
	fi

check-env: ## Проверить настройки .env
	@if [ ! -f .env ]; then \
		echo "$(RED)❌ Файл .env не найден! Выполните: make setup-env$(RESET)"; \
		exit 1; \
	fi
	@if grep -q "your_bot_token_here" .env; then \
		echo "$(RED)❌ Не настроен TELEGRAM_BOT_TOKEN в .env$(RESET)"; \
		exit 1; \
	fi
	@if grep -q "SLOVLI_ADMIN_USER_ID=0" .env; then \
		echo "$(RED)❌ Не настроен SLOVLI_ADMIN_USER_ID в .env$(RESET)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✅ Настройки .env корректны$(RESET)"

run: check-env start ## Проверить настройки и запустить

dev: ## Запустить в режиме разработки (локально)
	@echo "$(GREEN)Запуск в режиме разработки...$(RESET)"
	python -m wordly_bot.main
