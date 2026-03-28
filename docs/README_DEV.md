# README_DEV.md

Технический гайд для backend/frontend/бот-разработчиков SnacknSip.

## 1. Обзор архитектуры

### 1.1 Технологический стек

- **Backend:** Django 5 + Django REST Framework.
- **Auth:** JWT (`djangorestframework-simplejwt`) + Telegram flow с `X-Bot-Token`.
- **DB:** PostgreSQL 16.
- **Очереди и фоновые задачи:** Celery + Redis.
- **Хранилище медиа:** MinIO (S3-compatible, `django-storages`).
- **API docs:** drf-spectacular (`/api/docs/`, `/api/schema/`).
- **Prod web runtime:** Gunicorn + Django WSGI behind Nginx.

### 1.2 Логическая модель системы

SnacknSip строится вокруг одного backend-ядра (Django API), к которому подключены два независимых клиента:

1. **Web Frontend** (веб-сайт).
2. **Telegram Bot / WebApp**.

Оба канала используют единые бизнес-правила (лимиты, статусы заказов, роли, перераспределение заказов).

### 1.3 Внешние сервисы

- **Telegram API**: для Telegram login и bot-сценариев.

---

## 2. Описание API

### 2.1 Базовые правила аутентификации

- Все защищенные ручки требуют заголовок:

```http
Authorization: Bearer <access_token>
```

- Обновление токена:
  - `POST /api/auth/refresh/`
- Выход (blacklist refresh):
  - `POST /api/auth/logout/`

### 2.2 Логика логина

#### Универсальный логин (web и часть staff/organizer flow)

- `POST /api/auth/login/`
- С `event_code` -> авторизация EventUser (guest/staff).
- Без `event_code` -> авторизация Django User (organizer).

#### Telegram логин

- `POST /api/auth/telegram/`
- Обязателен заголовок `X-Bot-Token`.
- Основной сценарий:
  1. Поиск по `telegram_id`.
  2. Если нет, поиск по `telegram_username` + привязка `telegram_id`.

> Примечание: в `task/API.md` может встречаться старое имя ручки `/api/auth/telegram/login/`; актуальный путь в OpenAPI и `urls.py` — `/api/auth/telegram/`.

### 2.3 Ключевые эндпоинты по ролям

#### Guest

- `GET /api/me/limits/` - текущие лимиты гостя.
- `GET /api/stalls/` - список открытых точек.
- `GET /api/stalls/{id}/` - меню точки (с учетом стоп-листа).
- `POST /api/orders/` - создать заказ.
- `GET /api/orders/` - мои заказы.
- `GET /api/orders/{id}/status/` - polling статуса заказа.
- `GET /api/notifications/` - список уведомлений.
- `POST /api/notifications/{id}/read/` - отметить уведомление прочитанным.

#### Staff

- `GET /api/staff/stall/` - моя точка.
- `POST /api/staff/stall/open/` - открыть точку.
- `POST /api/staff/stall/close/` - закрыть точку.
- `GET /api/staff/menu/` - меню точки для стоп-листа.
- `PATCH /api/staff/menu/{item_id}/` - изменить доступность позиции.
- `GET /api/staff/orders/` - заказы точки.
- `PATCH /api/staff/orders/{id}/` - смена статуса (`created -> preparing -> ready -> completed`, отмена с `cancel_note`).
- `POST /api/staff/orders/redistribute/` - авто-перераспределение заказов закрытой точки.
- `POST /api/staff/orders/{id}/redistribute/` - ручное перераспределение.
- `POST /api/staff/orders/cancel-all/` - массовая отмена.

#### Organizer

- `GET/POST /api/org/events/` - список/создание мероприятий.
- `GET/PATCH /api/org/events/{event_id}/` - детали/обновление мероприятия.
- `POST /api/org/events/{event_id}/open/` и `/close/` - управление состоянием мероприятия.
- `GET/POST /api/org/events/{event_id}/stalls/` - управление точками.
- `GET/POST /api/org/events/{event_id}/menus/` - управление меню.
- `POST /api/org/events/{event_id}/menus/{menu_id}/items/` - добавить item.
- `PATCH/DELETE /api/org/events/{event_id}/menus/{menu_id}/items/{item_id}/` - изменить/удалить item.
- `GET/POST /api/org/events/{event_id}/users/` - пользователи мероприятия.
- `GET/PATCH/DELETE /api/org/events/{event_id}/users/{user_id}/` - детали/блокировка/удаление.
- `GET/POST /api/org/events/{event_id}/roles/` - роли гостей.
- `POST /api/org/events/{event_id}/roles/{role_id}/items/` - лимиты роли.
- `POST /api/org/events/{event_id}/roles/assign/` - назначить роль.
- `GET /api/org/events/{event_id}/orders/` - заказы мероприятия.

### 2.4 Бизнес-сценарии

#### Сценарий гостя

1. Логин -> получение JWT.
2. Запрос лимитов и доступных точек.
3. Создание заказа.
4. Polling статуса и чтение уведомлений о готовности.

#### Сценарий персонала

1. Открытие точки.
2. Работа с очередью заказов и статусами.
3. Стоп-лист по закончившимся позициям.
4. При закрытии точки - перераспределение или массовая отмена.

#### Сценарий организатора

1. Создание мероприятия.
2. Конфигурация меню/точек/ролей/пользователей.
3. Открытие/закрытие мероприятия.
4. Мониторинг заказов и контроль блокировок пользователей.

### 2.5 Примеры curl

#### Логин гостя

```bash
curl -X POST "http://localhost:8000/api/auth/login/" \
  -H "Content-Type: application/json" \
  -d '{
    "login": "guest@example.com",
    "password": "secret123",
    "event_code": "TECH24"
  }'
```

#### Telegram логин

```bash
curl -X POST "http://localhost:8000/api/auth/telegram/" \
  -H "Content-Type: application/json" \
  -H "X-Bot-Token: <bot_secret_token>" \
  -d '{
    "event_code": "TECH24",
    "telegram_id": 123456789,
    "telegram_username": "durov"
  }'
```

#### Создание заказа

```bash
curl -X POST "http://localhost:8000/api/orders/" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "stall_id": 1,
    "items": [
      {"menu_item_id": 5, "quantity": 1},
      {"menu_item_id": 7, "quantity": 2}
    ]
  }'
```

#### Staff: перевести заказ в ready

```bash
curl -X PATCH "http://localhost:8000/api/staff/orders/42/" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "ready"
  }'
```

---

## 3. Процесс развертывания (Production)

Источник: `task/DEPLOYMENT.md`.

### 3.1 Что разворачивается

Через `docker-compose.prod.yml` поднимаются контейнеры:

- `nginx`
- `web` (Django + Gunicorn)
- `worker` (Celery)
- `beat` (Celery Beat)
- `db` (PostgreSQL)
- `redis`
- `minio`
- `minio_init` (инициализация бакета)

### 3.2 Пошаговый деплой на VPS

1. Подготовить сервер (Ubuntu 22.04/24.04): Docker, Docker Compose, UFW.
2. Открыть порты: `22`, `80`, `443`, `9000`.
3. Клонировать репозиторий и настроить `.env.prod`.
4. Запустить compose с билдом.
5. Проверить статус контейнеров.
6. Создать суперпользователя в контейнере `web`.

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up --build -d
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
docker compose --env-file .env.prod -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

### 3.3 Что делает `entrypoint.sh`

Перед стартом `gunicorn` контейнер `web` автоматически:

1. Выполняет `python manage.py migrate --noinput`.
2. Выполняет `python manage.py collectstatic --noinput`.
3. Запускает основной процесс.

### 3.4 Обновление продакшна

```bash
cd /var/www/SnacknSip
git pull origin
docker compose --env-file .env.prod -f docker-compose.prod.yml up --build -d
```

### 3.5 Логи и обслуживание

```bash
docker compose -f docker-compose.prod.yml logs -f
docker compose -f docker-compose.prod.yml logs -f worker
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U snacknsip snacknsip > backup_$(date +%F).sql
```

---

## 4. CI/CD: текущая логика и целевая схема

### 4.1 Текущее состояние (as-is)

В репозитории нет явного pipeline-файла (`.github/workflows`, `.gitlab-ci.yml`, `Jenkinsfile`).

Фактическая модель:

- **CI локально/в PR дисциплине:** `pre-commit`, `ruff`, `pytest`.
- **CD вручную:** `git pull` на сервере + `docker compose up --build -d`.

### 4.2 Рекомендуемая целевая схема

1. **CI (на каждый PR/commit):**
   - `uv sync`
   - `ruff check`
   - `ruff format --check`
   - `pytest apps/api/tests/ -v`
   - (опционально) smoke build Docker image.
2. **CD (на merge в main/release):**
   - build image;
   - push в registry;
   - deploy на VPS (pull + restart stack);
   - post-deploy smoke (например `/api/schema/`).

Пример минимального CI-скрипта команд:

```bash
uv sync
pre-commit run --all-files
cd src
pytest apps/api/tests/ -v
```

---

## 5. Стандарты кода

### 5.1 Структура папок

```text
src/
  config/
    settings/
      base.py
      local.py
      prod.py
    urls.py
    wsgi.py
    celery.py
  apps/api/
    auth/
    models/
    serializers/
    views/
    tasks/
    tests/
    migrations/
```

### 5.2 Нейминг и стиль

- Следуем PEP8 и ограничениям Ruff (`line-length = 88`).
- Модули/файлы: `snake_case`.
- Классы: `PascalCase`.
- Функции/переменные: `snake_case`.
- Константы: `UPPER_SNAKE_CASE`.
- Для API-слоя придерживаемся разделения по ролям:
  - `views/guest.py`, `views/staff.py`, `views/organizer.py`.

### 5.3 Линтинг и pre-commit

Используется `.pre-commit-config.yaml`:

- `uv-lock`, `uv-export`
- `ruff-check --fix`
- `ruff-format`
- базовые хуки (`check-yaml`, `check-toml`, и т.д.)

Перед коммитом рекомендуется:

```bash
pre-commit install
pre-commit run --all-files
```

### 5.4 Работа с миграциями

Правила:

1. Одна логическая задача -> отдельная миграция.
2. Не редактировать уже примененные миграции в shared-ветке.
3. Проверять forward/backward совместимость.
4. Для сложных изменений использовать data migration отдельно от schema migration.

Базовые команды:

```bash
cd src
python manage.py makemigrations
python manage.py migrate
python manage.py showmigrations
```

Проверка в PR:

- миграции соответствуют изменениям моделей;
- отсутствуют конфликтные migration heads;
- тесты бизнес-логики проходят после миграций.

---

## 6. Полезные ссылки

- API docs (Swagger): `/api/docs/`
- OpenAPI schema: `/api/schema/`
- ReDoc: `/api/redoc/`
- Источники требований: `task/API.md`, `task/SnacknSip API.yaml`, `task/DEPLOYMENT.md`
