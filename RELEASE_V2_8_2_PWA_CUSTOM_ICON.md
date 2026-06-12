# v2.8.2 PWA custom icon

## Изменения

1. PWA/Home Screen иконка заменена на пользовательскую иконку «ОП 2026».
2. Добавлены PNG-иконки:
   - `app/miniapp_frontend/public/icons/icon-180.png`
   - `app/miniapp_frontend/public/icons/icon-192.png`
   - `app/miniapp_frontend/public/icons/icon-512.png`
   - `app/miniapp_frontend/public/icons/icon-1024.png`
3. `manifest.webmanifest` переведен на PNG-иконки.
4. В `index.html` добавлен `apple-touch-icon` для iPhone.
5. Service Worker теперь использует PNG-иконку в push-уведомлениях.

## Важно для iPhone

iOS кэширует иконку. Чтобы увидеть новую:
1. удалить старую иконку с экрана «Домой»;
2. открыть web-ссылку заново в Safari;
3. снова нажать `Поделиться` → `На экран «Домой»`.
