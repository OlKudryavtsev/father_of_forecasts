# v3.5.5 — Quiz delivery and 100-to-1 refinements

## Telegram quiz flow

- Repeated logical quiz events are ignored before notification dispatch, preventing duplicate question messages.
- A one-round quiz (single format or random question) skips standalone round-start and round-finish notifications.
- Group links for an already-running or finished quiz use an open-only deep link; they no longer attempt late registration.

## 100-to-1

- Reveals use a readable ranked layout: place, answer, factual value, and awarded points.
- The companion `World_Cup_Hundred_to_One_20_v2_all_ties.json` uses a legacy-text key. Importing it updates the earlier 20 questions in place (rather than adding duplicates) and returns them to draft for review/approval.
