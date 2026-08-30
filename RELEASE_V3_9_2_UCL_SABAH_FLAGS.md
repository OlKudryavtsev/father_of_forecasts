# v3.9.2 — ЛЧ: Sabah FA и флаги клубов

## Что исправлено

- Добавлен provider alias `Sabah FA → Sabah`, чтобы 8 матчей ЛЧ с участием Sabah FA сопоставлялись с официальным календарём общего этапа.
- Скрипт `python scripts/sync_ucl_2026_2027.py` теперь выполняет порядок:
  1. синхронизация API-Football;
  2. нормализация provider aliases;
  3. очистка qualifying/play-off qualification;
  4. нормализация 144 матчей league phase.
- В вывод скрипта добавлен блок `provider_aliases`.
- Для Mini App усилен UCL frontend patch:
  - добавлен alias `Sabah FA`;
  - русские названия клубов распознаются так же, как английские/API-названия;
  - флаги клубов дополнительно вставляются в видимые названия команд, даже если базовый компонент `TeamFlag` не отрисовал изображение.
- Версия PWA поднята до `3.9.2`, чтобы клиенты увидели обновление.

## Проверка после deploy

```bash
python scripts/sync_ucl_2026_2027.py
```

Ожидаемо:

```text
league_phase_cleanup.remaining_matches = 144
league_phase_cleanup.unmatched_kept_count = 0
provider_aliases.changed_matches = 8
```

После обновления Mini App в ЛЧ должны отображаться русские названия клубов и флаги стран клубов.
