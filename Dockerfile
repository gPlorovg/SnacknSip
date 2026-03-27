# Устанавливаем официальный образ с 'uv' для быстрой сборки
FROM ghcr.io/astral-sh/uv:python3.12-alpine AS builder

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app

# Копируем файлы зависимостей (uv.lock если есть)
COPY pyproject.toml uv.lock* ./

# Устанавливаем зависимости (без самого проекта и dev-пакетов)
RUN uv sync --no-install-project --no-dev

# ========================================================
# Финальный легковесный образ
FROM python:3.12-alpine

# Настраиваем окружение
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings.prod

WORKDIR /app

# Копируем готовое виртуальное окружение
COPY --from=builder /app/.venv /app/.venv

# Добавляем .venv в PATH
ENV PATH="/app/.venv/bin:$PATH"

# Копируем исходники проекта (из папки src)
COPY src/ /app/

# Создаём директорию для статики (чтобы Docker не создавал её с root-правами при монтировании тома)
RUN mkdir -p /app/staticfiles

# Делаем скрипт исполняемым
RUN chmod +x /app/entrypoint.sh

# Создаём пользователя без root-прав
RUN addgroup -S appgroup && adduser -S appuser -G appgroup \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

# Для локальной проверки, в docker-compose мы переопределим CMD под Nginx/Celery
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
