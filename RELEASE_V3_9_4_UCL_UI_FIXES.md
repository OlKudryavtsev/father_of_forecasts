# v3.9.4 — UCL UI fixes

Fixes for Champions League 2026/27 Mini App after v3.9.3 verification.

## Scope

- Replace large country flags on UCL match cards with club-logo blocks.
- Keep country flags next to club names.
- Use normal country flags for English clubs instead of the black subdivision flag fallback.
- Stop the UCL compatibility patch from translating arbitrary `name` fields, so league selection is not polluted by club names.
- Keep Match Center → Tournament UCL-specific and improve the 36-club league-phase table layout with horizontal scrolling.
- Keep Match Center → Scorers UCL-specific and empty until UCL goals/statistics are available.
- Add a compact, two-row-friendly header layout for tournament/league/stage/points on narrow screens.
- Bump app/PWA version to 3.9.4.

## Notes

- Club logos are loaded from API-Sports CDN where a known team id is available.
- If a logo fails to load or a club id is unknown, the UI falls back to a club monogram instead of showing a large country flag.
- This is still a frontend compatibility patch. A cleaner future step is to move club metadata/logo URLs into backend API responses.

## After merge/deploy

1. Open Mini App and update to v3.9.4.
2. Switch to `ЛЧ 2026/27`.
3. Check match cards: large icon should be a club emblem/monogram, and the country flag should stay next to the club name.
4. Check English clubs: country flag should not be black.
5. Check the league selector: it should show leagues, not club names.
6. Check Match Center → Tournament: the table should be horizontally scrollable and not broken.
7. Check Match Center → Scorers: it should not show WC2026 scorers.
