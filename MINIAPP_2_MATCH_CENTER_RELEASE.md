# Mini App 2.0 — Match Center Release 1

Добавлен первый релиз Mini App 2.0 на React.

## Что входит

- Новый верхний блок приложения в стиле спортивного match center.
- Новый раздел `Матчи`:
  - все матчи турнира;
  - фильтр `Результаты`;
  - фильтры по группам;
  - карточки матчей с флагами, временем, группой и кнопкой прогноза;
  - распределение прогнозов участников: П1 / X / П2.
- Турнирные таблицы групп:
  - считаются из результатов матчей в БД;
  - 1–2 место отмечены как прямой выход;
  - 3 место отмечено как зона плей-офф/лучшие третьи места.
- Новый экран `Прогнозы`:
  - матчи без прогноза;
  - все будущие матчи;
  - быстрый выбор счета.
- Новый экран `Рейтинг`.
- Упрощенные экраны `Турнир` и `Еще`.
- React/Vite frontend в `app/miniapp_frontend`.

## Backend API

Добавлен endpoint:

```http
GET /api/webapp/match-center?scope=all|results&group_code=A
```

Ответ включает:

- `matches`;
- `groups`;
- `standings`;
- `prediction_distribution` по каждому матчу.

## Сборка

Dockerfile теперь собирает React frontend через Node stage и копирует `dist` в `app/miniapp_static`.

## SQL

Новые таблицы не добавлялись. Миграции не нужны.


## Локальная ручная сборка frontend без Docker

Если нужно собрать статику вручную:

```bash
cd app/miniapp_frontend
npm install
npm run build

cd ../..
rm -rf app/miniapp_static/*
cp -R app/miniapp_frontend/dist/* app/miniapp_static/
```

После этого `/app` будет отдавать уже собранный React frontend.

## Важно

В `vite.config.js` установлен `base: '/miniapp-static/'`, потому что FastAPI отдает assets из `/miniapp-static`, а сам HTML — по `/app`.
