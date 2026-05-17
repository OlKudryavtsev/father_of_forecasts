# База данных проекта «Отец прогнозов»

В этой папке лежит актуальная bootstrap-схема БД.

## Файлы

```text
db/schema.sql      # SQL-схема PostgreSQL для создания таблиц с нуля
docs/database.md   # описание таблиц, связей и ER-диаграмма
scripts/init_db.py # создание таблиц через SQLAlchemy metadata
scripts/check_db_schema.py # проверка, что в БД есть таблицы/колонки из app/models.py
```

## Важное предупреждение

`db/schema.sql` — это **не Alembic-миграция**, а bootstrap-файл.

Его безопасно применять к новой пустой БД.  
Для существующей production-БД Railway сначала сделайте backup и выполните проверку:

```bash
python scripts/check_db_schema.py
```

## Создание таблиц через SQLAlchemy

Если нужно создать таблицы по текущим моделям:

```bash
DATABASE_URL=postgresql://user:password@host:5432/dbname python scripts/init_db.py
```

Скрипт использует:

```python
Base.metadata.create_all(bind=engine)
```

То есть он создает только отсутствующие таблицы, но не выполняет полноценные миграции существующих колонок.

## Проверка схемы

```bash
DATABASE_URL=postgresql://user:password@host:5432/dbname python scripts/check_db_schema.py
```

Если все хорошо, увидите:

```text
DB schema check passed.
```

Если чего-то не хватает, скрипт выведет список отсутствующих таблиц или колонок.

## Railway

В Railway можно выполнить SQL вручную:

1. Открыть PostgreSQL service.
2. Перейти в Query.
3. Вставить содержимое `db/schema.sql`.
4. Выполнить.

Для production-БД лучше не применять весь файл повторно, а использовать его как справочник и применять только нужные `ALTER TABLE ... ADD COLUMN ...`.

## Рекомендация на будущее

Следующий зрелый шаг — подключить Alembic:

```bash
pip install alembic
alembic init alembic
```

И дальше вести изменения схемы через миграции:

```text
alembic/versions/001_initial_schema.py
alembic/versions/002_add_image_generation_logs.py
...
```


## Миграции

Для существующей БД добавлен SQL-скрипт:

```text
db/migrations/001_add_quiz_battle.sql
```

Он создает таблицы для серии группового квиза с таймером:

```text
group_quiz_games
group_quiz_game_questions
group_quiz_game_answers
```

Применение в Railway PostgreSQL: открыть Query, вставить содержимое файла и выполнить.
Перед применением на production-БД рекомендуется сделать backup.
