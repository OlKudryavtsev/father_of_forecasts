# Release v2.8.5 — Match TV autodiscovery and PWA update protection

## Added

- Автопоиск официальных видео Match TV для ближайших матчей ЧМ.
- Автоматическое связывание найденных карточек видео с матчами по русским названиям и алиасам команд.
- Метаданные `discovery_status`, `confidence`, `external_id`, `discovered_at` для `match_videos`.
- Админская кнопка “Найти видео Match TV” в блоке “Видео матча”.
- Опциональный фоновый sync Match TV каждые 30 минут (`MATCHTV_VIDEO_AUTOSYNC_ENABLED=true`).
- Версионирование PWA: backend `/api/webapp/app-version`, frontend banner “Доступна новая версия”, кнопка “Обновить”.
- `/app` теперь отдается с no-store/no-cache заголовками, чтобы ярлык на iPhone быстрее подтягивал свежий frontend.

## Migration

```bash
psql "$DATABASE_URL" -f db/migrations/009_matchtv_video_autodiscovery_and_pwa_version.sql
```

## Notes

Интеграция хранит только официальные ссылки на страницы Match TV. Видео не скачивается, не проксируется и не встраивается через чужие HLS-потоки.
