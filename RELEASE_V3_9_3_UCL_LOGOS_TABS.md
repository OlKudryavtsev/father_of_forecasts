# v3.9.3 — UCL club logos and tournament tabs

Release v3.9.3 improves the Champions League 2026/27 Mini App UI after the clean league-phase import.

## Scope

- Show club emblems in the large team icon area for UCL match cards.
- Keep country flags next to club names.
- Make the Match Center → Tournament tab UCL-specific instead of showing WC2026 groups.
- Make the Match Center → Top scorers tab UCL-specific instead of showing WC2026 scorers.
- Keep third-place prediction hidden for UCL.
- Keep the UCL manual top-scorer input behavior.
- Bump app/PWA version to 3.9.3.

## Notes

- The UCL tournament overview is currently a lightweight frontend compatibility layer: it shows the 36 clubs in the league phase with zeroed standings until real UCL match statistics are available.
- Top scorers for UCL intentionally show an empty state until UCL match events/statistics are available.
- Club emblems use remote logo URLs and fall back to country flags if an image cannot load.

## After deploy

Open the Mini App, switch to `ЛЧ 2026/27`, then check:

1. Match cards: club emblem above, country flag next to club name.
2. Match Center → Tournament: no WC2026 groups; UCL league-phase table is shown.
3. Match Center → Top scorers: no WC2026 scorers; empty UCL-specific state before goals.
