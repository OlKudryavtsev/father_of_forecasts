# v3.9.5 — UCL UI polish

Hotfix for the Champions League 2026/27 Mini App UI after production verification.

## Scope

- Replace country flags in the large "Нужен прогноз" hero card with club logos/monograms.
- Keep country flags next to club names.
- Use the England flag for English clubs instead of the UK flag or black fallback.
- Reduce the risk of the Match Center → Tournament tab freezing by replacing the previous heavy UCL DOM patch with a lighter, debounced patch.
- Keep Match Center → Tournament and Match Center → Бомбардиры UCL-specific.
- Redesign the header controls into separate compact blocks: tournament, league, stage, points, rank.
- Bump app/PWA version to 3.9.5.

## Notes

This is still a frontend compatibility patch. The cleaner next step is to move UCL club metadata, club logos, country flags, league-phase standings, and scorer data into backend API responses instead of patching the UI in the browser.

## Manual verification after deploy

1. Open Mini App and update to v3.9.5.
2. Select `ЛЧ 2026/27`.
3. Check the yellow "Нужен прогноз" card: large icons should be club logos/monograms, not country flags.
4. Check match cards: club logo above, country flag next to club name.
5. Check English clubs: flag should be England `🏴󠁧󠁢󠁥󠁮󠁧󠁿`.
6. Open Match Center → Tournament: app should not freeze.
7. Open Match Center → Бомбардиры: it should not show WC2026 scorers.
8. Check the header on Telegram Web and iPhone.

Do not merge automatically.
