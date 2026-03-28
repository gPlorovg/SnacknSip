# USER GUIDE: SnacknSip

Практическое руководство для:
- **конечных пользователей** (Гость, Персонал точки),
- **организаторов мероприятий**,
- **администраторов сервиса**.

Гайд собран на основе материалов из `task/` и текущей конфигурации проекта.

---

## 1. Быстрый старт

### Вариант A: Production-стек ("в один клик" через Docker Compose)

Подходит для быстрого запуска полного окружения: `web`, `nginx`, `worker`, `beat`, `db`, `redis`, `minio`.

```bash
cp .env.prod.example .env.prod
```

Отредактируйте `.env.prod` (минимум: `SECRET_KEY`, `ALLOWED_HOSTS`, пароли).

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up --build -d
```

Проверка:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

После запуска:
- API Docs (Swagger): `http://<host>/api/docs/`
- Django Admin: `http://<host>/admin/`

Создание администратора:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

### Вариант B: Локальная разработка

В этом режиме Docker поднимает инфраструктуру (`db`, `redis`, `minio`), а Django запускается локально.

```bash
cp .env.example .env
```

```bash
docker compose up -d
```

```bash
cd src
python manage.py migrate
python manage.py runserver
```

Доступ:
- API Docs: `http://localhost:8000/api/docs/`
- Admin: `http://localhost:8000/admin/`

---

## 2. Настройка

### Ключевые файлы конфигурации

- `.env.example` - шаблон переменных для локальной разработки.
- `.env.prod.example` - шаблон переменных для production.
- `.env` / `.env.prod` - ваши реальные значения (не коммитятся в git).
- `docker-compose.yml` - dev-инфраструктура.
- `docker-compose.prod.yml` - полный production-стек.
- `src/config/settings/base.py`, `src/config/settings/prod.py` - настройки Django.

### Обязательные переменные окружения

#### Безопасность и домен
- `SECRET_KEY` - обязательный секрет Django.
- `DEBUG` - `True` для локалки, `False` для production.
- `ALLOWED_HOSTS` - список доменов/IP через запятую.
- `WEB_BASE_URL` - базовый URL веб-интерфейса (prod).

#### База данных
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`

> Важно: в локальном `.env` обычно `DB_HOST=127.0.0.1`, в `.env.prod` - `DB_HOST=db`.

#### Redis / Celery
- `REDIS_URL` - брокер/кеш (пример: `redis://redis:6379/0` в prod).

#### MinIO / S3
- `MINIO_URL`
- `MINIO_BUCKET` (обычно `menu-images`)
- `MINIO_USER`
- `MINIO_PASSWORD`

#### Telegram и криптография
- `BOT_SECRET_TOKEN` - обязателен для Telegram login (`X-Bot-Token`).
- `FERNET_KEY` - ключ шифрования паролей/секретов в системе.

Генерация `FERNET_KEY`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 3. Руководство по использованию

### 3.1 Где работать с системой

- **Гость / Персонал**: через клиент (Web/Telegram), который ходит в API.
- **Организатор**: через API и/или Django Admin.
- **Суперадмин**: через Django Admin (`/admin/`).
- Интерактивное тестирование API: Swagger (`/api/docs/`).

### 3.2 Авторизация

Основной формат:
- Заголовок: `Authorization: Bearer <access_token>`

Получение токенов:
- `POST /api/auth/login/` - логин для ролей по логину/паролю.
- `POST /api/auth/telegram/` - Telegram login (нужен заголовок `X-Bot-Token`).
- `POST /api/auth/refresh/` - обновить access token.
- `POST /api/auth/logout/` - инвалидировать refresh token.

### 3.3 Сценарий Гостя

Типовой путь:
1. Войти в систему.
2. Проверить доступные лимиты: `GET /api/me/limits/`.
3. Посмотреть точки и меню: `GET /api/stalls/`.
4. Создать заказ: `POST /api/orders/`.
5. Отслеживать статусы заказа: `GET /api/orders/`.
6. Получать уведомления о готовности: `GET /api/notifications/`.

Пример тела заказа:

```json
{
  "stall_id": 1,
  "items": [
    { "menu_item_id": 5, "quantity": 1 }
  ]
}
```

Если превышен лимит или позиция в стоп-листе, API вернет `400 Bad Request`.

### 3.4 Сценарий Персонала точки

Основные действия:
- Открыть/закрыть точку:
  - `POST /api/staff/stall/open/`
  - `POST /api/staff/stall/close/`
- Смотреть активные заказы:
  - `GET /api/staff/orders/`
- Менять статус заказа:
  - `PATCH /api/staff/orders/{id}/`
- Управлять стоп-листом:
  - `GET /api/staff/menu/`
  - `PATCH /api/staff/menu/{item_id}/` (например, `{ "is_available": false }`)

Жизненный цикл заказа обычно идет через статусы:
`created -> preparing -> ready -> completed`.

### 3.5 Сценарий Организатора

Организатор управляет мероприятием, точками, меню, гостями и ролями.

Ключевые API-группы:
- События: `GET/POST /api/org/events/`, `.../open/`, `.../close/`
- Точки: `GET/POST /api/org/events/{event_id}/stalls/`
- Меню и позиции: `GET/POST /api/org/events/{event_id}/menus/` и `.../items/`
- Пользователи: `GET/POST /api/org/events/{event_id}/users/`
- Роли и лимиты: `GET/POST /api/org/events/{event_id}/roles/`, `.../assign/`
- Заказы события: `GET /api/org/events/{event_id}/orders/`

По user stories организаторские операции также доступны через Django Admin (удобно для импорта/ручного управления).

### 3.6 Сценарий администратора сервиса

- Создает мероприятия.
- Выдает права организаторам.
- Контролирует данные через Django Admin.
- Проводит первичную настройку окружения и пользователей.

---

## 4. Troubleshooting

### Ошибка: `could not translate host name "db"` или `Connection Refused` к PostgreSQL

Причина:
- База не запущена, либо `DB_HOST` не соответствует режиму запуска.

Решение:
- Для dev: поднимите инфраструктуру `docker compose up -d`.
- Проверьте `.env`:
  - локально: `DB_HOST=127.0.0.1`
  - в prod-контейнерах: `DB_HOST=db`

### Ошибка: `PermissionError` при `collectstatic` (`/app/staticfiles`)

Причина:
- Проблема прав в volume (обычно старый volume после смены образа/пользователя).

Решение:

```bash
docker compose -f docker-compose.prod.yml down -v
docker compose --env-file .env.prod -f docker-compose.prod.yml up --build -d
```

### `403 Forbidden` на `/api/auth/telegram/`

Причина:
- Неверный `X-Bot-Token` или не совпадает с `BOT_SECRET_TOKEN`.

Решение:
- Проверьте значение `BOT_SECRET_TOKEN` в `.env/.env.prod`.
- Передавайте точно такой же токен в заголовке `X-Bot-Token`.

### `503 Telegram login is not configured on this server`

Причина:
- На сервере не задан `BOT_SECRET_TOKEN`.

Решение:
- Добавьте `BOT_SECRET_TOKEN` в env-файл.
- Перезапустите сервисы.

### Не загружаются изображения меню

Причина:
- Неверные параметры MinIO (`MINIO_URL`, `MINIO_*`) или бакет не создан.

Решение:
- Проверьте переменные MinIO в env-файле.
- Убедитесь, что сервис `minio_init` отработал и создал `menu-images`.

### `401 Unauthorized` на защищенных эндпоинтах

Причина:
- Access token истек или не передается в заголовке.

Решение:
- Используйте `POST /api/auth/refresh/`.
- Передавайте заголовок: `Authorization: Bearer <access_token>`.

### `400 Bad Request` при создании заказа

Причина:
- Превышены лимиты гостя, позиция в стоп-листе или переданы некорректные `menu_item_id`/`stall_id`.

Решение:
- Проверьте `GET /api/me/limits/` и `GET /api/stalls/` перед отправкой заказа.
- В ответе API используйте поле ошибки для точной диагностики.

---

## 5. Полезные команды для администрирования

Проверка статуса контейнеров:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

Логи всего проекта:

```bash
docker compose -f docker-compose.prod.yml logs -f
```

Логи только worker:

```bash
docker compose -f docker-compose.prod.yml logs -f worker
```

Быстрый backup PostgreSQL:

```bash
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U snacknsip snacknsip > backup_$(date +%F).sql
```

---
