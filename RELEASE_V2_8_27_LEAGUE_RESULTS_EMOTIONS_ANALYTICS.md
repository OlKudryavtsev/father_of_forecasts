# v2.8.27 — League result emotions and rating analytics

## Personal post-match notifications
- Match-finish notifications are now sent separately for every league the user was already in when the match started.
- Each message uses the same league-filtered match breakdown as the relevant group chat: final score, exact scores, correct outcomes and misses.
- A personal block adds the user's result, current league position, movement versus the pre-match table and a successful-prediction streak.
- Existing legacy `private_match_finished:<match_id>` keys suppress replaying historical notifications immediately after deployment.

## Daily summaries
- Private daily summaries are scoped to each recipient's active league(s), rather than always using the `Отец прогнозов` league.
- Users who have not yet joined any league are not sent a misleading league-specific daily table.

## Rating analytics
- The Rating screen now includes a league-scoped "Аналитика матчей" block.
- It presents top 10 finished matches by number of exact-score predictions (3 points) and by correct-outcome predictions (1 point).
- Results use the selected league's scoring start and active-at-kickoff membership rules.

## Compatibility
- No database migration required.
- PWA version: 2.8.27.
