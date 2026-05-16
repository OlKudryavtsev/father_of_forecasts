# Import graph

Generated from the cleaned project using Python AST import parsing.

## Entry points

- `bot.py` → `app.bot_runtime.main`
- `Dockerfile` → `python bot.py` and `uvicorn app.main:app`
- `scripts/import_world_cup_facts.py` is a manual utility, not a production entrypoint.

## Edges

- `app.bot_runtime` → `app`
- `app.constants.commands` → `app`
- `app.formatters.admin` → `app`
- `app.formatters.archive` → `app`
- `app.formatters.facts` → `app`
- `app.formatters.matches` → `app`
- `app.formatters.misc` → `app`
- `app.formatters.predictions` → `app`
- `app.formatters.quiz` → `app`
- `app.handlers.admin` → `app`
- `app.handlers.archive` → `app`
- `app.handlers.facts` → `app`
- `app.handlers.forecast` → `app`
- `app.handlers.help` → `app`
- `app.handlers.matches` → `app`
- `app.handlers.misc` → `app`
- `app.handlers.panini` → `app`
- `app.handlers.predictions` → `app`
- `app.handlers.quiz` → `app`
- `app.handlers.start` → `app`
- `app.handlers.table` → `app`
- `app.handlers.tournament` → `app`
- `app.jobs.reminders` → `app`
- `app.keyboards.admin` → `app`
- `app.keyboards.facts` → `app`
- `app.keyboards.matches` → `app`
- `app.keyboards.panini` → `app`
- `app.keyboards.predictions` → `app`
- `app.keyboards.quiz` → `app`
- `app.keyboards.table` → `app`
- `app.main` → `app`
- `app.middleware.access` → `app`
- `app.models` → `app`
- `app.runtime` → `app`
- `app.services.admin` → `app`
- `app.services.archive` → `app`
- `app.services.facts` → `app`
- `app.services.forecast` → `app`
- `app.services.matches` → `app`
- `app.services.misc` → `app`
- `app.services.notifications` → `app`
- `app.services.panini` → `app`
- `app.services.predictions` → `app`
- `app.services.quiz` → `app`
- `app.services.tournament` → `app`
- `app.services.users` → `app`
- `app.states` → `app`
- `app.wc2026_forecast_context` → `app`
- `app.wc2026_sync` → `app`
- `bot` → `app`
- `scripts.import_world_cup_facts` → `app`
