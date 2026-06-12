# v2.8.1 PWA cookie session fix

## Зачем

На iPhone при добавлении web-версии на экран «Домой» PWA стартует с `manifest.start_url` (`/app`).
Из-за этого URL-параметр `web_token` может не попасть в запуск из иконки, а localStorage Safari может не быть доступен в standalone PWA-контейнере.

Симптом:

```text
ссылка открывается в браузере,
но после «Поделиться» → «Добавить на экран Домой»
иконка открывает экран с инструкцией зайти через Telegram
```

## Исправление

1. `/app?web_token=...` теперь сохраняет токен еще и в cookie `ff_web_session`.
2. Backend auth читает токен не только из:
   - `X-Web-Session-Token`
   - `Authorization: Bearer ...`

   но и из cookie:
   - `ff_web_session`
3. Frontend при старте PWA считает пользователя авторизованным, если токен найден в cookie.
4. Logout из web-версии очищает cookie.

## SQL

Новых миграций нет. Используется миграция v2.8:

```bash
psql "$DATABASE_URL" -f db/migrations/007_add_web_sessions_push_subscriptions.sql
```
