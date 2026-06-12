# v2.8 Web/PWA mode

## Что добавлено

### 1. Web/PWA-режим через вариант A

Пользователь сначала открывает Mini App внутри Telegram.
После этого в профиле в секции `Настройки` появляется блок `Web/PWA на iPhone`.

Сценарий:

1. Открыть Mini App в Telegram.
2. Профиль → Настройки → `Создать ссылку`.
3. Открыть ссылку в Safari.
4. Добавить страницу на экран «Домой».
5. В web/PWA-версии нажать `Включить уведомления`.

Связка с Telegram сохраняется через:

```text
telegram_user_id -> users.id -> web_sessions.token_hash
```

### 2. Browser auth/session layer

Добавлены таблицы:

- `web_sessions`
- `push_subscriptions`

Добавлены endpoints:

```http
POST /api/webapp/web-session/create
GET  /api/webapp/web-session/status
POST /api/webapp/web-session/logout
GET  /api/webapp/push/public-key
POST /api/webapp/push/subscribe
POST /api/webapp/push/unsubscribe
```

Backend теперь принимает два способа авторизации:

- Telegram Mini App `X-Telegram-Init-Data`
- browser/PWA token `X-Web-Session-Token`

### 3. PWA

Добавлены:

```text
app/miniapp_frontend/public/manifest.webmanifest
app/miniapp_frontend/public/sw.js
app/miniapp_frontend/public/icons/icon-192.svg
app/miniapp_frontend/public/icons/icon-512.svg
```

### 4. Web Push

Добавлен optional Web Push service:

```text
app/services/web_push.py
```

Групповые уведомления Telegram теперь дополнительно пробуют отправляться в Web Push подписки.
Если Web Push не настроен, приложение не падает.

## Переменные окружения

Для browser-session желательно задать:

```text
WEB_SESSION_SECRET=<длинная случайная строка>
WEB_SESSION_TTL_DAYS=180
```

Для Web Push нужно задать:

```text
VAPID_PUBLIC_KEY=<public key>
VAPID_PRIVATE_KEY=<private key>
VAPID_SUBJECT=mailto:your-email@example.com
```

## SQL

Нужно выполнить миграцию:

```bash
psql "$DATABASE_URL" -f db/migrations/007_add_web_sessions_push_subscriptions.sql
```

## Зависимости

Добавлена зависимость:

```text
pywebpush
```

После деплоя на Railway лучше сделать rebuild без cache.
