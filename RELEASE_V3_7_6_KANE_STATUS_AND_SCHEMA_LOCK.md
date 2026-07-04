# v3.7.6 — Kane status and safe startup schema lock

## Fixed
- Normalized player aliases using the same Unicode pipeline as user input, fixing Russian names with `й` such as `Харри Кейн`.
- Tournament-prediction statuses and standings long-term checks now use the curated national-team hint if the provider scorer cache is incomplete. Harry Kane remains active while England is alive.
- Bumped league win-model cache schema version so the background model rebuilds scenarios after deployment.
- Serialized SQLAlchemy `create_all` under a PostgreSQL advisory lock to avoid concurrent bot/Uvicorn startup table-creation races.

## Database
No new migration is required. Existing `league_win_model_cache` rows are reused and regenerated in the background.
