# Compatibility layer removed

This build removes the dynamic compatibility layer from `app/bot_runtime.py`.

What changed:

- Removed runtime symbol collection/injection via `_public_symbols`, `vars(module).update(...)`, and `globals().update(...)`.
- Replaced module-level `from app.runtime import *` imports with explicit imports.
- Registered handlers in `app/bot_runtime.py` with explicit function imports.
- Broke top-level circular imports by moving several cross-domain imports into function scope where needed.
- Kept the existing runtime behavior and command set unchanged.

Validation performed:

```bash
python -m py_compile bot.py app/*.py app/*/*.py
```

Expected smoke-test commands:

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
/predict
/tournament_set
```
