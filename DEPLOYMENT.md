# 🚀 Быстрое развертывание Wordly Bot на VPS

## Метод 1: Автоматическая установка (1 команда)

```bash
curl -fsSL https://raw.githubusercontent.com/yourusername/wordly-bot/main/install.sh | bash
```

## Метод 2: Быстрый деплой с локальной машины

```bash
# Клонируйте репозиторий локально
git clone https://github.com/yourusername/wordly-bot.git
cd wordly-bot

# Деплой на сервер одной командой
./deploy.sh user@your-server.com
```

## Метод 3: Пошаговая установка

### На сервере выполните:

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/yourusername/wordly-bot.git
cd wordly-bot

# 2. Создайте настройки
cp env.example .env
nano .env  # Укажите токен бота и ID администратора

# 3. Запустите
docker-compose up -d
```

## ⚙️ Настройка .env файла

Обязательно настройте эти параметры:

```bash
# Получите токен у @BotFather в Telegram
TELEGRAM_BOT_TOKEN=1234567890:AAAA-your-bot-token-here

# Получите ваш ID у @userinfobot в Telegram  
SLOVLI_ADMIN_USER_ID=123456789
```

## 🔧 Управление ботом

```bash
# Просмотр логов
docker-compose logs -f

# Перезапуск
docker-compose restart

# Остановка
docker-compose down

# Обновление
git pull && docker-compose build --no-cache && docker-compose up -d
```

## 🆘 Решение проблем

### Бот не отвечает
```bash
# Проверьте логи
docker-compose logs

# Проверьте статус контейнера
docker-compose ps
```

### Ошибка токена
```bash
# Проверьте .env файл
cat .env

# Убедитесь что токен правильный
# Получите новый токен у @BotFather если нужно
```

### Проблемы с правами
```bash
# Убедитесь что пользователь в группе docker
sudo usermod -aG docker $USER

# Перелогиньтесь или выполните
newgrp docker
```

## 📋 Минимальные требования

- **VPS:** 512MB RAM, 2GB диск
- **ОС:** Ubuntu 20.04+ / Debian 10+  
- **Docker:** Устанавливается автоматически
- **Порты:** Не требуются (только исходящие для Telegram API)

## 🎉 После установки

1. Напишите боту `/start`
2. Добавьте модераторов: `/addmoderator @username`
3. Настройте длину слов: `/length 5`
4. Начните игру: `/new`

**Готово! Ваш бот работает на VPS! 🎮**
