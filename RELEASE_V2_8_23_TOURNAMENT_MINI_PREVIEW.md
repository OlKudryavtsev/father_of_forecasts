# v2.8.23 — Tournament prediction mini preview

- Added collapse/expand support for the Match Center "Прогнозы на турнир" block, similar to Profile collapsible sections.
- Added compact selected-team flags in the tournament prediction block header.
- Added selected top scorer photo in the tournament prediction block header when a stored player photo is available; falls back to initials.
- Enriched tournament prediction API payloads with team flag codes and top scorer photo metadata.
- Updated PWA version to 2.8.23.
- The tournament prediction block now treats late-entry users with `can_submit=true` as editable even after tournament start.
