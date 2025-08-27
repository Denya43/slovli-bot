# 🎮 Wordly Bot - Команды управления

## 🚀 Быстрый старт

```bash
# Автоматическая установка на VPS
curl -fsSL https://your-repo.com/install.sh | bash

# Или клонирование и ручная установка
git clone https://github.com/yourusername/wordly-bot.git
cd wordly-bot
make setup-env  # Создать .env файл
make run        # Запустить бота
```

## 🐳 Docker команды

```bash
# Запуск в фоне
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Перезапуск
docker-compose restart

# Остановка
docker-compose down

# Пересборка образа
docker-compose build --no-cache

# Статус контейнеров
docker-compose ps
```

## 📋 Makefile команды

```bash
make help        # Показать справку
make setup-env   # Создать .env файл
make build       # Собрать Docker образ
make start       # Запустить бота
make stop        # Остановить бота
make restart     # Перезапустить
make logs        # Показать логи
make status      # Статус контейнеров
make clean       # Очистить Docker ресурсы
make update      # Обновить и перезапустить
make check-env   # Проверить настройки
make run         # Проверить .env и запустить
make dev         # Запуск в режиме разработки
```

## 🔧 Системные команды

```bash
# Управление через systemd
sudo systemctl start wordly-bot     # Запуск
sudo systemctl stop wordly-bot      # Остановка  
sudo systemctl restart wordly-bot   # Перезапуск
sudo systemctl status wordly-bot    # Статус
sudo systemctl enable wordly-bot    # Автозапуск

# Мониторинг
./monitor.sh                         # Полная проверка системы
```

## 🚀 Деплой команды

```bash
# Быстрый деплой на удаленный сервер
./deploy.sh user@server.com

# Деплой с конкретными настройками
./deploy.sh root@192.168.1.100
```

## 🔍 Отладка

```bash
# Проверка конфигурации
docker-compose config

# Проверка .env файла
make check-env

# Подключение к контейнеру
docker-compose exec wordly-bot bash

# Просмотр использования ресурсов
docker stats

# Очистка всего Docker
docker system prune -a
```

## 📝 Логи и мониторинг

```bash
# Логи в реальном времени
docker-compose logs -f

# Последние 100 строк логов
docker-compose logs --tail=100

# Логи конкретного сервиса
docker-compose logs wordly-bot

# Системные логи
journalctl -u wordly-bot -f
```

## 🔄 Обновление

```bash
# Автоматическое обновление
make update

# Ручное обновление
git pull
docker-compose build --no-cache
docker-compose up -d

# Откат к предыдущей версии
git checkout HEAD~1
docker-compose build --no-cache
docker-compose up -d
```

## 🆘 Восстановление

```bash
# Полная переустановка
docker-compose down -v
docker system prune -f
git pull
docker-compose build --no-cache
docker-compose up -d

# Восстановление базы данных из бэкапа
cp backup/slovli.db data/slovli.db
docker-compose restart
```

## 📊 Полезные проверки

```bash
# Размер базы данных
du -h data/slovli.db

# Количество слов в словаре
wc -l words.txt

# Проверка портов
netstat -tlnp | grep docker

# Использование диска
df -h

# Использование памяти
free -h
```
