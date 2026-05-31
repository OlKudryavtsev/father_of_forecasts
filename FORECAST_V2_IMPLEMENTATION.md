# Forecast v2 implementation

## Что добавлено

### 1. Улучшенная структура `/forecast`

Прогноз теперь содержит:

- прогноз счета;
- исход;
- уверенность;
- качество данных;
- краткую логику;
- ключевые факторы;
- базовый и альтернативный сценарий;
- риски прогноза;
- факты перед матчем.

### 2. Optional-каркас odds/lineups

В `app/wc2026_forecast_context.py` добавлен `external_context`.

Он пытается получить из API-Football:

- `/odds?fixture=...`;
- `/fixtures/lineups?fixture=...`.

Если данных нет, они не показываются пользователю и не ломают прогноз.

Переменная окружения:

```env
FORECAST_EXTERNAL_CONTEXT_ENABLED=true
```

Чтобы временно отключить дополнительные запросы API-Football:

```env
FORECAST_EXTERNAL_CONTEXT_ENABLED=false
```

### 3. Мониторинг API-Football

Добавлена админская команда:

```text
/admin_api_coverage 10
```

Проверяет ближайшие N матчей и показывает наличие:

- fixture;
- odds;
- lineups;
- predictions;
- injuries.

### 4. Обновленный скрипт проверки

```text
scripts/check_api_football_wc2026_coverage.py
```

Теперь проверяет fixture-level и tournament-level endpoints.

## SQL

SQL менять не нужно. Новые таблицы не добавлялись.

## Проверка

```bash
python -m py_compile bot.py app/*.py app/*/*.py scripts/*.py
```

В Telegram:

```text
/forecast
/admin_api_coverage 10
```
