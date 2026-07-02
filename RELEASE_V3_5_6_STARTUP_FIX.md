# v3.5.6 — Startup recovery and quiz delivery corrections

## Critical fix
- Removes delivery handlers accidentally appended to `app/services/league_quiz.py`.
- Restores import-safe separation: core event creation stays in `league_quiz.py`; Telegram transport stays in `league_quiz_telegram.py`.

## Included delivery behavior
- Deduplicates equivalent question/round/quiz transport events.
- Suppresses start/finish round messages for one-round format and random quizzes.
- Uses open-only group deep links after a quiz begins.
- Formats Hundred-to-One answers one per line with position, value and points.

## Database
No migration is required.
