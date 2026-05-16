# Cleanup audit

This archive is a cleaned version of the submitted project. It removes files that are not used by the production bot runtime, Railway/Docker entrypoints, or the currently kept manual maintenance script.

## Production entrypoints checked

- `bot.py` imports and runs `app.bot_runtime.main`.
- `Dockerfile` runs `python bot.py` and `uvicorn app.main:app`.
- `docker-compose.yml` builds the same image and does not reference extra scripts directly.
- `app/main.py` is kept because it is referenced by the Dockerfile as the FastAPI/health endpoint.
- `app/bot_runtime.py` is kept because it registers middleware, handlers and background loops.
- `app/runtime.py` is kept because handlers/services import shared runtime objects from it.

## Kept manual script

- `scripts/import_world_cup_facts.py` is kept as a manual maintenance/import utility. It is not part of the production startup path.

## Removed groups

### IDE/cache artifacts

- `.idea/`
- `__pycache__/`
- `app/**/__pycache__/`
- `*.pyc`

### Refactoring documentation artifacts

- `README_COMPATIBILITY_REMOVED.md`
- `README_REFACTORING.md`
- `STRUCTURE.txt`

### Manual MVP import artifacts from the project root

- `wc2026_group_stage_import.csv`
- `wc2026_group_stage_import_ru.csv`
- `*.docx`

### Unused compatibility/reserved modules

- `app/bot_main.py`
- `app/constants/settings_aliases.py`
- `app/formatters/common.py`
- `app/formatters/forecast.py`
- `app/formatters/panini.py`
- `app/jobs/daily_facts.py`
- `app/jobs/misc.py`
- `app/keyboards/archive.py`
- `app/middleware/command_logging.py`
- `app/middleware/common.py`
- `app/middleware/group_access.py`
- `app/repositories/`
- `app/services/command_stats.py`
- `app/services/common.py`
- `app/services/reminders.py`
- `app/services/table.py`

### Old MVP forecasting/backtest modules

These were used by historical backtest scripts and old forecast experiments, not by the current bot runtime:

- `app/predictor.py`
- `app/predictor_v2.py`
- `app/predictor_v3.py`
- `app/team_ratings.py`
- `app/elo_rankings_client.py`
- `app/fifa_rankings_client.py`
- `app/openai_context_builder.py`
- `app/pre_tournament_context.py`
- `scripts/backtest_openai_wc2022.py`
- `scripts/backtest_wc2022.py`
- `scripts/data/`

### Unsafe/dev-only API test

- `app/test_api_foolball_wc2026.py`

Reason: not imported by production code, located inside `app`, typo in filename, and contained a hardcoded API key.

## Validation performed

After cleanup:

```bash
python -m py_compile bot.py app/*.py app/*/*.py scripts/*.py
```

The project compiles successfully.

The cleaned AST import graph has no unused `app.*` modules, excluding explicit entrypoints.

## Suggested git commands

```bash
git rm -r .idea __pycache__ app/__pycache__
find app -type d -name "__pycache__" -prune -exec git rm -r {} +

git rm README_COMPATIBILITY_REMOVED.md README_REFACTORING.md STRUCTURE.txt

git rm wc2026_group_stage_import.csv wc2026_group_stage_import_ru.csv
git rm "*.docx"

git rm app/bot_main.py app/constants/settings_aliases.py

git rm app/formatters/common.py app/formatters/forecast.py app/formatters/panini.py

git rm app/jobs/daily_facts.py app/jobs/misc.py

git rm app/keyboards/archive.py

git rm app/middleware/command_logging.py app/middleware/common.py app/middleware/group_access.py

git rm -r app/repositories

git rm app/services/command_stats.py app/services/common.py app/services/reminders.py app/services/table.py

git rm app/test_api_foolball_wc2026.py

git rm scripts/backtest_openai_wc2022.py scripts/backtest_wc2022.py
git rm -r scripts/data

git rm app/predictor.py app/predictor_v2.py app/predictor_v3.py
git rm app/team_ratings.py app/elo_rankings_client.py app/fifa_rankings_client.py
git rm app/openai_context_builder.py app/pre_tournament_context.py
```

If the shell does not expand `*.docx` for tracked files, run `git rm -- '*.docx'` or remove the specific filename shown by `git ls-files '*.docx'`.
