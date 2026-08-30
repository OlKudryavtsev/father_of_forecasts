# v3.9.6 — UCL header and tournament table

## Fixes

- Reworked the UCL header into compact separate areas: tournament, league, stage, points and rank. The admin control is a compact icon instead of a tall block.
- Club country flags are now rendered in the same row, immediately to the left of the club name.
- English clubs use the England flag emoji.
- UCL match cards and the `Нужен прогноз` hero continue to use club emblems as the large visual.
- Match Center → Tournament no longer exposes the WC2026 group tables while `ЛЧ 2026/27` is selected. A dedicated 36-club league-phase table is rendered instead.
- Match Center → Scorers remains isolated from WC2026 data until UCL scorer statistics are available.

## Deployment

No DB migration and no API-Football re-sync are required.

After deployment, update the Mini App to v3.9.6 and verify the header, `Нужен прогноз`, match cards and Match Center → Tournament on iPhone and Telegram Web.
