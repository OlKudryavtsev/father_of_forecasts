# Forecast v2: структура прогноза и мониторинг API-Football

Обновление улучшает команду `/forecast` без зависимости от пока недоступных данных API-Football.

## Что изменено

### 1. Структура ИИ-прогноза

`/forecast` теперь выводит прогноз более структурировано:

- прогноз счета;
- исход;
- уверенность;
- качество данных;
- логика прогноза;
- ключевые факторы;
- базовый и альтернативный сценарий;
- риски прогноза;
- факты перед матчем.

### 2. Optional-каркас для odds и lineups

В контекст OpenAI добавлен блок `external_context`.

Он умеет принимать:

- котировки букмекеров;
- официальные составы.

Если API-Football пока возвращает пусто, эти блоки не выводятся пользователю и не засоряют прогноз.

Переменная:

```env
FORECAST_EXTERNAL_CONTEXT_ENABLED=true
```

Если поставить `false`, бот не будет делать дополнительные вызовы API-Football для odds/lineups при `/forecast`.

### 3. Мониторинг появления данных

Добавлена админская команда:

```text
/admin_api_coverage 10
```

Она проверяет ближайшие N матчей и показывает наличие:

- fixture;
- odds;
- lineups;
- predictions;
- injuries.

Пример:

```text
📡 API-Football coverage WC2026

Проверено матчей: 10

Fixtures: 10/10
Odds: 0/10
Lineups: 0/10
Predictions: 10/10
Injuries: 0/10

Вывод:
Расширенный forecast по odds/lineups пока включать как обязательный фактор рано.
```

### 4. Скрипт проверки покрытия

Обновлен скрипт:

```text
scripts/check_api_football_wc2026_coverage.py
```

Он проверяет fixture-level и tournament-level endpoints:

- `/leagues?id=1&season=2026`;
- `/fixtures?league=1&season=2026`;
- `/odds?league=1&season=2026`;
- `/odds?league=1&season=2026&date=YYYY-MM-DD`;
- `/bookmakers`;
- `/bets`;
- `/odds?fixture=...`;
- `/fixtures/lineups?fixture=...`.

## Почему odds/lineups не выводятся пустыми

Сейчас API-Football по будущим матчам WC2026 может возвращать пустые odds и lineups.
Чтобы не ухудшать UX, прогноз не показывает блоки:

```text
Котировки недоступны
Составы недоступны
```

Эти данные появятся в выводе только когда API реально вернет содержимое.

## Проверка

```bash
python -m py_compile bot.py app/*.py app/*/*.py scripts/*.py
```

В Telegram:

```text
/forecast
/admin_api_coverage 10
```
