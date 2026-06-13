"""Notification settings shared by Mini App API and Web Push delivery."""

NOTIFICATION_OPTIONS = [
    {
        "key": "match_reminders",
        "title": "Напоминания о прогнозах",
        "description": "Личные напоминания о матчах, где еще не сделан прогноз.",
        "default": True,
    },
    {
        "key": "group_activity",
        "title": "Активность участников",
        "description": "Новые регистрации, прогнозы на матчи и турнирные прогнозы участников.",
        "default": True,
    },
    {
        "key": "match_started",
        "title": "Старт матча",
        "description": "Уведомление о начале матча и раскрытии прогнозов участников.",
        "default": True,
    },
    {
        "key": "match_finished",
        "title": "Итоги матча",
        "description": "Уведомление после внесения финального счета и начисления очков.",
        "default": True,
    },
    {
        "key": "daily_facts",
        "title": "Ежедневная сводка / факт дня",
        "description": "Утренняя сводка игрового дня или ежедневный футбольный факт от Отца прогнозов.",
        "default": True,
    },
    {
        "key": "match_videos",
        "title": "Видео матчей",
        "description": "Уведомления, когда для матча появляется обзор, хайлайты или запись.",
        "default": True,
    },
]

NOTIFICATION_DEFAULTS = {
    option["key"]: bool(option["default"])
    for option in NOTIFICATION_OPTIONS
}

ADMIN_NOTIFICATION_SETTING_KEYS = {
    f"{option['key']}_enabled": "true"
    for option in NOTIFICATION_OPTIONS
}

ADMIN_SETTING_BY_NOTIFICATION_KEY = {
    option["key"]: f"{option['key']}_enabled"
    for option in NOTIFICATION_OPTIONS
}
