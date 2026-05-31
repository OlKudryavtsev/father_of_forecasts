# Telegram Mini App implementation

Добавлен первый релиз Telegram Mini App — личный кабинет и турнирный портал.

## Новые файлы

```text
app/api/__init__.py
app/api/auth.py
app/api/webapp.py
app/handlers/miniapp.py
app/miniapp_static/index.html
app/miniapp_static/styles.css
app/miniapp_static/app.js
docs/telegram_miniapp.md
```

## Измененные файлы

```text
app/main.py
app/bot_runtime.py
app/constants/commands.py
app/constants/texts.py
README.md
```

## Новая команда

```text
/app
```

Команда отправляет Telegram WebApp-кнопку, которая открывает `/app`.

## Новые API endpoints

```text
GET  /api/webapp/me
GET  /api/webapp/dashboard
GET  /api/webapp/matches?scope=nearest|missing|all
GET  /api/webapp/matches/{match_id}
POST /api/webapp/predictions
GET  /api/webapp/table
GET  /api/webapp/tournament-prediction/me
POST /api/webapp/tournament-prediction
GET  /api/webapp/tournament-predictions
GET  /api/webapp/facts/random
GET  /api/webapp/quiz/random
POST /api/webapp/quiz/answer
GET  /api/webapp/archive/random
```

## Авторизация

Mini App frontend отправляет Telegram initData в заголовке:

```http
X-Telegram-Init-Data: <window.Telegram.WebApp.initData>
```

Backend проверяет подпись через `BOT_TOKEN`.

## Настройки

```env
MINIAPP_URL=https://your-domain.up.railway.app/app
```

или:

```env
PUBLIC_BASE_URL=https://your-domain.up.railway.app
```

Для локальной отладки вне Telegram:

```env
MINIAPP_DEBUG_TELEGRAM_ID=123456789
```
