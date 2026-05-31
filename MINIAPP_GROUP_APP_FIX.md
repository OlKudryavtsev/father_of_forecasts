# Mini App group chat fix

Исправляет ошибку `/app` в групповом чате:

```text
TelegramBadRequest: Bad Request: BUTTON_TYPE_INVALID
```

## Причина

Telegram не разрешает inline-кнопки типа `web_app=WebAppInfo(...)` в групповых чатах.
Такие кнопки можно отправлять только в личном чате с ботом.

## Новая логика

### Личный чат

Команда:

```text
/app
```

Бот отправляет настоящую WebApp-кнопку:

```text
🚀 Открыть турнирный портал
```

### Групповой чат

Команда:

```text
/app
```

Бот отправляет обычную URL-кнопку:

```text
https://t.me/<BOT_USERNAME>?start=app
```

Пользователь переходит в личку с ботом, где `/start app` показывает нормальную WebApp-кнопку.

## Railway Variables

Желательно добавить:

```env
BOT_USERNAME=your_bot_username
```

Без `@`.

Если переменная не задана, бот попробует получить username через Telegram API `getMe()`.

SQL и Mini App frontend не менялись.
