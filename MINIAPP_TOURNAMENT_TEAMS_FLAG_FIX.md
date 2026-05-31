# Mini App tournament teams flag fix

Исправляет ошибку на вкладке Mini App «Турнир»:

```text
TypeError: get_team_flag() takes from 1 to 2 positional arguments but 3 were given
```

## Причина

В endpoint `/api/webapp/tournament-teams` функция `get_team_flag(...)` вызывалась с тремя аргументами:

```python
get_team_flag(name, api_name, display_name)
```

А в текущем проекте сигнатура функции принимает один или два аргумента.

## Исправление

Вызов заменен на:

```python
get_team_flag(name, api_name or display_name)
```

SQL менять не нужно.
