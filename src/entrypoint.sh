#!/bin/sh

set -e

# Даем базе секунду-другую на полное поднятие
sleep 3

echo "🚀 Запускаем миграции БД..."
python manage.py migrate --noinput

echo "📦 Собираем статические файлы..."
python manage.py collectstatic --noinput

echo "✅ Стартуем основной процесс: $@"
exec "$@"
