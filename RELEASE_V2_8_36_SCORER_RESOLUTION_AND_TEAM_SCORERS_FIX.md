# v2.8.36 — Scorer resolution and team scorer cache fix

## Fixes
- Tournament prediction scorer names now resolve through Fantasy roster, cached scorer data and known Russian/English aliases.
- «Эрлинг Холанд» resolves to Norway even before he scores, so the prediction card shows the national-team status instead of «Статус уточняется» and keeps the player profile link available.
- Team pages backfill missing finished-match detail caches when first opened.
- Team scorers merge API-Football leaderboard data with locally cached goal events, so teams such as Brazil display their scorers after already played matches.
- Own goals and missed penalties are excluded from scorer ranking.
- The background tournament cache gradually fills missing finished-match event data after deployment.
- A partially successful API-Football detail response is cached as fresh, preventing repeated slow retries when optional statistics/lineups are unavailable.

## Database
No migration is required.
