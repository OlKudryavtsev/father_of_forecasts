# v3.6.1 — Host dashboard and history selector hotfix

## Fixed

1. **Host dashboard 500 error**
   - `app/api/webapp.py` now imports `build_host_dashboard_v360`, `preflight_bank_import_v360`, and `host_resend_v360` from `league_quiz_content`.
   - This fixes the `NameError` triggered by `GET /api/webapp/quizzes/{session_id}/host-dashboard`.

2. **History selector readability**
   - The history dropdown now uses explicit dark and light theme colors.
   - The collapsed control and the opened native option list keep readable foreground/background contrast.

## Deployment

No database migration is required. Replace the source with this archive and redeploy the Railway service.
