# Telegram Mini App: личный кабинет и турнирный портал

Этот документ описывает добавленную Telegram Mini App-часть проекта «Отец прогнозов».

## Что добавлено

Mini App дополняет Telegram-бота: бот остается быстрым интерфейсом для команд и уведомлений, а Mini App становится личным кабинетом и турнирным порталом.

В Mini App доступны:

- главная страница;
- ближайшие матчи;
- мои пропущенные прогнозы;
- создание и обновление прогнозов на матчи;
- прогноз на проход в плей-офф;
- турнирная таблица;
- турнирный прогноз;
- просмотр прогнозов участников на турнир;
- случайные факты о чемпионатах мира;
- быстрый квиз;
- архивные карточки прошлых «Отцов прогнозов».

## URL

Frontend Mini App доступен по адресу:

```text
/app
```

Статика обслуживается по адресу:

```text
/miniapp-static/*
```

API Mini App доступно по префиксу:

```text
/api/webapp/*
```

## Команда в боте

Добавлена команда:

```text
/app
```

Она отправляет кнопку:

```text
🚀 Открыть турнирный портал
```

Кнопка открывает Telegram Mini App через `web_app=WebAppInfo(...)`.

## Переменные окружения

Для корректной работы кнопки нужно задать публичный URL Mini App одним из способов:

```env
MINIAPP_URL=https://your-domain.up.railway.app/app
```

или:

```env
PUBLIC_BASE_URL=https://your-domain.up.railway.app
```

В Railway также можно использовать:

```env
RAILWAY_PUBLIC_DOMAIN=your-domain.up.railway.app
```

Для проверки Telegram `initData` используется:

```env
BOT_TOKEN=...
```

Для локальной отладки вне Telegram можно временно задать:

```env
MINIAPP_DEBUG_TELEGRAM_ID=123456789
MINIAPP_DEBUG_USERNAME=debug
MINIAPP_DEBUG_FIRST_NAME=Debug
MINIAPP_DEBUG_LAST_NAME=User
```

Если `MINIAPP_DEBUG_TELEGRAM_ID` задан, API разрешит запросы без `X-Telegram-Init-Data` и создаст/использует debug-пользователя.

## Авторизация

Frontend отправляет в API заголовок:

```http
X-Telegram-Init-Data: <window.Telegram.WebApp.initData>
```

Backend валидирует подпись Telegram initData через `BOT_TOKEN` и только после этого определяет пользователя.

Нельзя доверять `telegram_id`, переданному с frontend без проверки `initData`.

## API endpoints

### Пользователь

```http
GET /api/webapp/me
```

### Главная

```http
GET /api/webapp/dashboard
```

Возвращает:

- пользователя;
- текущие очки и место;
- ближайшие матчи;
- количество пропущенных прогнозов;
- превью матчей без прогноза.

### Матчи

```http
GET /api/webapp/matches?scope=nearest
GET /api/webapp/matches?scope=missing
GET /api/webapp/matches?scope=all
GET /api/webapp/matches/{match_id}
```

### Прогнозы

```http
POST /api/webapp/predictions
```

Пример body:

```json
{
  "match_id": 24,
  "pred_home": 1,
  "pred_away": 2,
  "advancement_bet_enabled": true,
  "predicted_advancing_side": "away"
}
```

### Таблица

```http
GET /api/webapp/table
```

### Турнирный прогноз

```http
GET /api/webapp/tournament-prediction/me
POST /api/webapp/tournament-prediction
GET /api/webapp/tournament-predictions
```

### Факты, квиз, архив

```http
GET /api/webapp/facts/random
GET /api/webapp/quiz/random
POST /api/webapp/quiz/answer
GET /api/webapp/archive/random
```

## Файлы

```text
app/api/auth.py
app/api/webapp.py
app/handlers/miniapp.py
app/miniapp_static/index.html
app/miniapp_static/styles.css
app/miniapp_static/app.js
```

## Что не входит в первый релиз

В первый релиз Mini App не включены:

- Panini-генерация;
- live-интерфейс quiz_battle;
- ИИ-прогнозы `/forecast`;
- WebSocket/push-обновления.

Их можно добавить следующими этапами.
