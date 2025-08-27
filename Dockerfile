# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаем пользователя для запуска приложения (безопасность)
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Открываем порт (если понадобится для webhook)
EXPOSE 8080

# Команда по умолчанию
CMD ["python", "-m", "wordly_bot.main"]
