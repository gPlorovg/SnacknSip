# SnacknSip Architecture

Документ фиксирует целевую архитектуру системы SnacknSip, где Django API является ядром и обслуживает два независимых канала: Web Frontend и Telegram Bot.

## 0) Scope и допущения

- Источники: `README.md`, `task/API.md`, `task/DEPLOYMENT.md`, `docker-compose.prod.yml`, `src/config/settings/base.py`, `src/apps/api/views/auth.py`.
- В проде backend запускается в Docker Compose: `nginx`, `web` (Gunicorn + Django WSGI), `worker`, `beat`, `db`, `redis`, `minio`, `minio_init`.
- `Web App` и `Telegram Bot Service` логически отдельные контейнеры приложения и могут деплоиться независимо от backend-стека.
- S3-совместимое хранилище реализовано через `MinIO` на нашем сервере (через Docker Compose).

---

## 1) C4 Context Diagram (Level 1)

```mermaid
flowchart LR
    siteUser["Пользователь сайта\n(Guest/Staff/Organizer)"]
    tgUser["Пользователь Telegram\n(Guest через Bot/WebApp)"]

    subgraph snacknsip["SnacknSip System"]
        core["SnacknSip Backend Core\nDjango REST API"]
    end

    webFE["Web Frontend\n(внешний клиент системы)"]
    tgBot["Telegram Bot Service\n(внешний клиент системы)"]
    tgPlatform["Telegram Platform API\n(Bot API / WebApp initData)"]

    siteUser -->|HTTPS/JSON| webFE
    webFE -->|REST API + JWT| core

    tgUser -->|Telegram chat/WebApp| tgPlatform
    tgPlatform -->|Bot updates / WebApp context| tgBot
    tgBot -->|REST API + JWT + X-Bot-Token| core

    core -->|Валидация initData / bot flow| tgPlatform
```

**Легенда**
- `Пользователь` - человек, взаимодействующий с каналом.
- `Web Frontend` и `Telegram Bot Service` - внешние по отношению к backend системные клиенты.
- `SnacknSip Backend Core` - единая бизнес-логика и API-контракт.
- `Telegram Platform API` - внешняя зависимость для Telegram-сценария.

**Почему такое разделение**
- Каналы Web и Telegram независимы по UX/релизам, но используют единое ядро правил заказа, лимитов и ролей.
- Telegram требует отдельной интеграции (Bot API, WebApp `initData`, `X-Bot-Token`), поэтому вынесен как внешний системный участник.

---

## 2) C4 Container Diagram (Level 2)

```mermaid
flowchart LR
    siteUser["Пользователь сайта"]
    tgUser["Пользователь Telegram"]

    subgraph clients["Client Channel Layer"]
        webApp["Web App\nSPA/SSR UI"]
        tgSvc["Telegram Bot Service\nBot/WebApp backend"]
    end

    subgraph core["SnacknSip Backend System"]
        nginx["Nginx\nReverse proxy + static"]
        djangoAPI["Django API (web)\nGunicorn + WSGI\nDRF + JWT"]
        celeryW["Celery Worker\nasync tasks"]
        celeryB["Celery Beat\nscheduler"]
        db[("PostgreSQL\nprimary DB")]
        redis[("Redis\ncache + broker/result backend")]
        minio[("MinIO (S3)\nmenu images")]
    end

    tgPlatform["Telegram API"]

    siteUser --> webApp
    tgUser --> tgPlatform
    tgPlatform --> tgSvc

    webApp -->|"HTTPS REST, Bearer JWT"| nginx
    tgSvc -->|"HTTPS REST, Bearer JWT"| nginx
    tgSvc -->|"X-Bot-Token, initData login"| djangoAPI

    nginx --> djangoAPI

    djangoAPI -->|"ORM/SQL"| db
    djangoAPI -->|"cache, Celery broker/result"| redis
    djangoAPI -->|"S3 API (media)"| minio
    djangoAPI -->|"verify Telegram context"| tgPlatform

    celeryW -->|"consume tasks"| redis
    celeryW -->|"read/write domain data"| db
    celeryW -->|"create/read media refs"| minio

    celeryB -->|"publish periodic tasks"| redis
    celeryB -->|"event checks"| db

    classDef app fill:#E8F0FE,stroke:#1A73E8,color:#0B1F44;
    classDef infra fill:#E6F4EA,stroke:#188038,color:#0D2B12;
    classDef ext fill:#FFF4E5,stroke:#FA7B17,color:#5C2B00;

    class webApp,tgSvc,djangoAPI,celeryW,celeryB app;
    class nginx,db,redis,minio infra;
    class tgPlatform ext;
```

**Легенда**
- `app` (синий) - прикладные контейнеры с бизнес-логикой или клиентским каналом.
- `infra` (зеленый) - инфраструктурные контейнеры хранения/сети.
- `ext` (оранжевый) - внешние платформенные зависимости.

**Почему такое разделение**
- `Django API` изолирован как ядро синхронного HTTP API (Gunicorn + WSGI) и доменной логики.
- `Celery Worker/Beat` вынесены отдельно для фоновых/периодических задач (уведомления, авто-закрытие событий, очистка токенов).
- `PostgreSQL`, `Redis`, `MinIO` выделены как независимые stateful сервисы с разным профилем нагрузки и отказоустойчивости.
- `Web App` и `Telegram Bot Service` показаны отдельными контейнерами, т.к. это два независимых клиента одного API.

---

## 3) Deployment Diagram

```mermaid
flowchart TB
    internet["Internet Users"]
    tgCloud["Telegram Cloud API"]

    subgraph webHost["Host A (опционально): Web Frontend Runtime"]
        webDeploy["Web App container/service"]
    end

    subgraph botHost["Host B (опционально): Telegram Bot Runtime"]
        botDeploy["Telegram Bot Service container/service"]
    end

    subgraph vps["VPS (Ubuntu 22.04/24.04) - docker compose -f docker-compose.prod.yml"]
        subgraph net["Docker Network"]
            nginxD["nginx:1.25-alpine\n:80 exposed"]
            webD["web (Django + Gunicorn)\nconfig.wsgi:application\n:8000 internal"]
            workerD["worker (Celery)"]
            beatD["beat (Celery Beat)"]
            dbD[("db (PostgreSQL 16)")]
            redisD[("redis 7")]
            minioD[("minio S3\n:9000 API, :9001 console")]
            minioInit["minio_init job\ncreate bucket menu-images"]
            staticVol[("static_volume")]
            pgVol[("postgres_prod_data")]
            redisVol[("redis_prod_data")]
            minioVol[("minio_prod_data")]
        end
    end

    internet --> webDeploy
    internet --> botDeploy
    internet -->|HTTP/HTTPS| nginxD

    webDeploy -->|HTTPS REST/JWT| nginxD
    botDeploy -->|HTTPS REST/JWT| nginxD
    botDeploy -->|Bot API/WebApp| tgCloud

    nginxD --> webD
    webD --> dbD
    webD --> redisD
    webD --> minioD
    webD --> tgCloud

    workerD --> redisD
    workerD --> dbD
    workerD --> minioD

    beatD --> redisD
    beatD --> dbD

    minioInit --> minioD

    webD --- staticVol
    nginxD --- staticVol
    dbD --- pgVol
    redisD --- redisVol
    minioD --- minioVol
```

**Легенда**
- `VPS` - подтвержденный production-контур из `task/DEPLOYMENT.md` и `docker-compose.prod.yml`.
- `Host A/Host B` - независимые рантаймы для Web и Telegram каналов (могут быть выделены отдельно для независимого релизного цикла).
- `minio_init` - одноразовый init-job для создания бакета и публичной политики.
- Именованные volumes - постоянное хранение состояния БД/кеша/объектов и статики.

**Почему такое разделение**
- Backend и stateful-сервисы собраны на одном VPS для простого и быстрого запуска.
- Отдельный Nginx фронтирует Django-контейнер и раздает статику.
- Клиентские каналы вынесены в отдельные deployment-юниты, чтобы не блокировать релизы друг друга и backend.
- MinIO размещен на нашем сервере в том же compose-стеке, как требовалось.

---

## 4) Технологические акценты Django

- Текущий runtime API в проде - **WSGI через Gunicorn** (`config.wsgi:application`).
- Асинхронная обработка - через **Celery Worker + Redis**, планировщик - **Celery Beat**.
- Аутентификация - JWT (`Bearer`) + отдельный Telegram login flow с `X-Bot-Token`.
- API документация - `drf-spectacular` (`/api/docs/`).
- Медиа (изображения меню) - S3 API через MinIO (`storages.backends.s3boto3`).
