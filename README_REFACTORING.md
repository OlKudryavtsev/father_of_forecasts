# Modular refactor

This archive uses the latest `bot(1).py` as the source and moves real function/class implementations into domain modules.

## Run

```bash
python -m py_compile bot.py app/bot_runtime.py
python bot.py
```

## Notes

- `bot.py` is now a compact entrypoint.
- `app/runtime.py` contains shared runtime objects, imports and env-derived settings.
- Constants, keyboards, formatters, services, middleware, jobs, states and handlers contain actual extracted implementation.
- `app/bot_runtime.py` imports all modules and injects public symbols to preserve cross-function lookup from the former monolith.
