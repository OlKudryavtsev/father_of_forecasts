# Father Predictions Bot — modular layout refresh

This archive was generated from the uploaded `bot(1).py` and keeps the latest
runtime, including `/table_buttons`, `/panini`, group access commands, and the
current match-label formatting.

## What changed

- `bot.py` is now a compact compatibility entrypoint.
- Full current behavior is preserved in `app/bot_runtime.py`.
- Suggested packages were created: `constants`, `handlers`, `keyboards`,
  `services`, `formatters`, `middleware`, `repositories`, `jobs`.
- Public wrapper modules re-export current runtime symbols so later extraction
  can be done incrementally.
- Docstrings were added to runtime functions/classes that did not have them.

## Docstring summary

- Functions/async functions found: 202
- Classes found: 7
- Functions/classes still missing docstrings: 0

## How to apply

1. Create a branch:

```bash
git checkout -b refactor/latest-modular-bot
```

2. Unzip this archive into the project root:

```bash
unzip father_predictions_refactor_latest.zip
```

3. Copy the contents of `father_predictions_refactor_latest/` into the project root.
   The root `bot.py` should be replaced. Existing files like `app/db.py`,
   `app/models.py`, `app/scoring.py`, `app/wc2026_sync.py`, etc. should remain.

## How to test

```bash
python -m py_compile bot.py app/bot_runtime.py
```

Then run as before:

```bash
python bot.py
```

Smoke-test in Telegram:

```text
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

## Next recommended step

This is a safe decomposition stage. The next commits should move code out of
`app/bot_runtime.py` gradually: constants first, then keyboards and formatters,
then services, then handlers/routers.
