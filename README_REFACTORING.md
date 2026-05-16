# Father Predictions bot — modular refactoring package

This archive contains a safe, behavior-preserving split scaffold for the current `bot.py`.

## What is inside

- `bot.py` — small executable compatibility entrypoint.
- `app/bot_runtime.py` — current working implementation from the uploaded `bot.py`, with generated docstrings added to functions/classes that did not have them.
- `app/handlers/*`, `app/services/*`, `app/keyboards/*`, `app/formatters/*`, `app/constants/*`, `app/middleware/*`, `app/jobs/*`, `app/repositories/*` — target structure modules. They currently re-export implementations from `app.bot_runtime` so behavior does not change.

This approach avoids a risky one-shot rewrite of an 8k+ line production bot. The next safe step is to move implementations from `app.bot_runtime.py` into the target modules one domain at a time.

## How to replace

1. Make a backup or create a branch:

```bash
git checkout -b refactor/modular-bot
```

2. Unpack the archive into the project root.

3. Let the new root `bot.py` replace the old root `bot.py`.

4. Copy the new `app/*` files into your existing `app/` directory. The package intentionally does **not** overwrite your existing `app/db.py`, `app/models.py`, `app/main.py`, `app/scoring.py`, etc.

## How to test

```bash
python -m py_compile bot.py app/bot_runtime.py
python bot.py
```

Then in Telegram check the main flows:

```text
/start
/help
/table
/table_buttons
/matches_all
/forecast
/fact
/quiz
/archive
/panini
```

## Important

This archive adds no new business functionality, checks, or protections. It only prepares the codebase for modularization while preserving current behavior.
