# v2.8.26 — League chat_id fix

Исправлена ошибка reminder loop при настроенных лигах и колонке `leagues.chat_id` типа BIGINT в production-БД.

## Что изменено

- Убрано SQL-сравнение `leagues.chat_id != ''`, которое ломалось на PostgreSQL для BIGINT.
- `chat_id` теперь нормализуется в строку только в Python-коде перед отправкой сообщения.
- Пустые значения `chat_id` нормализуются в `NULL`.
- Добавлена миграция для приведения `leagues.chat_id` к TEXT, чтобы модель и БД были согласованы.
- PWA-версия обновлена до `2.8.26`.

## Миграция

```bash
psql "$DATABASE_URL" -f db/migrations/015_fix_league_chat_id_type.sql
```
