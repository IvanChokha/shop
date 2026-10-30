# Shop MVP

Минимальный интернет-магазин: каталог, карточка товара, корзина, оформление заказа (без оплаты).
**Next.js (App Router) · FastAPI · aiogram · PostgreSQL · MinIO.** Все сервисы stateless и по умолчанию
поднимаются в 2 репликах за nginx.

## Быстрый старт

```bash
cp .env.example .env        # необязательно: у всех переменных есть значения по умолчанию
docker compose up --build
```

| Что | Адрес |
|---|---|
| Сайт (2 реплики Next.js) | http://localhost:3000 |
| API + Swagger (2 реплики FastAPI) | http://localhost:8000/docs |
| MinIO (консоль) | http://localhost:9001 (`minioadmin` / `minioadmin`) |

Задача `init` один раз применяет миграции, создаёт бакет и заливает 6 демо-товаров с картинками.

### Telegram-бот

Бот — витрина в Telegram поверх того же REST API: каталог → карточка → корзина → заказ.

```bash
# в .env задайте BOT_TOKEN
docker compose --profile bot up --build                # polling, 1 реплика — для разработки

# 2+ реплики — только webhook (Telegram требует публичный https):
# BOT_MODE=webhook, WEBHOOK_BASE_URL=https://<адрес, проброшенный на nginx:8081>, WEBHOOK_SECRET=...
docker compose --profile bot up --scale bot=2
```

## Как убедиться, что это stateless

1. Обновляйте сайт: в подвале меняется имя инстанса Next.js. `curl -si localhost:8000/healthz | grep X-Served-By`

   показывает чередование реплик API.
2. Добавьте товар в корзину и обновляйте `/cart`: корзина одна и та же на любой реплике — она в PostgreSQL,

   в cookie лежит только непрозрачный ключ.
3. `docker compose up -d --scale backend=3 --scale frontend=3` — число реплик меняется без правок кода.
4. Контейнеры `backend` и `bot` запущены с `read_only: true`: писать на диск им нечем.

## Архитектура backend

```
presentation   FastAPI: роуты, схемы, DI, маппинг доменных ошибок в HTTP
     │ вызывает
application    use case'ы (catalog, cart, orders) + порты (ports.py)   ← тесты без БД
     │ зависит только от
domain         сущности и доменные ошибки

infrastructure SQLAlchemy Core, Unit of Work, адаптер  — реализуют порты application
main.py        composition root: единственное место, где слои соединяются
```

```
backend/app/{domain,application,infrastructure,presentation}   backend/migrations (Alembic)
backend/app/scripts/seed.py                                    bot/app/{main,handlers,api,config}.py
frontend/src/{app,components,lib}                              nginx/nginx.conf
```

## API

Покупатель идентифицируется заголовком `X-Cart-Key` (16–128 символов `A-Za-z0-9_-`).

| Метод | Путь | |
|---|---|---|
| GET | `/api/v1/products?limit&offset` | каталог |
| GET | `/api/v1/products/{id}` | карточка |
| GET | `/api/v1/cart` | корзина (`X-Cart-Key`) |
| POST | `/api/v1/cart/items` | `{product_id, qty}` — добавить (проверяет остаток) |
| DELETE | `/api/v1/cart/items/{product_id}` | убрать позицию |
| POST | `/api/v1/orders` | оформить заказ из корзины; опционально `Idempotency-Key` |
| GET | `/api/v1/orders/{id}` | заказ |
| POST | `/api/v1/admin/products` | создать товар (`X-Admin-Token`) |
| POST | `/api/v1/admin/products/{id}/image` | получить presigned PUT-URL для картинки (`X-Admin-Token`) |
| GET | `/healthz`, `/readyz` | liveness / readiness |

Деньги — целые числа в копейках (`price_cents`).

### Добавить товар и картинку

```bash
T=change-me     # ADMIN_TOKEN из .env
curl -s -X POST localhost:8000/api/v1/admin/products -H "X-Admin-Token: $T" -H 'Content-Type: application/json' \
  -d '{"title":"Кепка","description":"Хлопок","price_cents":99000,"stock":10}'          # → id товара
curl -s -X POST localhost:8000/api/v1/admin/products/<id>/image -H "X-Admin-Token: $T" \
  -H 'Content-Type: application/json' -d '{"content_type":"image/png"}'                # → upload_url
curl -X PUT -H 'Content-Type: image/png' --upload-file cap.png "<upload_url>"          # файл — прямо в MinIO
```

## Тесты

```bash
cd backend && python -m unittest discover -s tests -t .
```

Тесты прикладного слоя идут без БД и без сторонних пакетов — на подменённых репозиториях (в этом
и смысл портов): списание остатка, откат при нехватке товара, идемпотентность и гонка двух реплик.

## Осознанные ограничения MVP

- Нет регистрации покупателей (корзина — анонимная сессия) и оплаты; админка — только API по токену.
- MinIO — один узел (для кластера — distributed-режим или любое S3-совместимое хранилище);
версия образа закреплена. Сменить `ADMIN_TOKEN`, `CART_SECRET`, `WEBHOOK_SECRET` перед любым деплоем.
- Нет уведомлений менеджеру о новых заказах. Естественное расширение — transactional outbox в PostgreSQL
и воркер с `SELECT … FOR UPDATE SKIP LOCKED`: он тоже масштабируется в N реплик без брокера.
