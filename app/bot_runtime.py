"""Application bootstrap for the modular Father Predictions bot.

This module imports domain modules, injects shared symbols for backward-compatible
function lookup, registers middleware and starts polling.
"""

import asyncio
import importlib

from app.runtime import bot, dp, DAILY_FACTS_ENABLED
from app.middleware.access import (
    CommandLoggingMiddleware,
    GroupCallbackAccessMiddleware,
    GroupCommandAccessMiddleware,
)

MODULE_NAMES = [
    "app.constants.categories",
    "app.constants.commands",
    "app.constants.teams",
    "app.constants.texts",
    "app.formatters.admin",
    "app.formatters.archive",
    "app.formatters.facts",
    "app.formatters.forecast",
    "app.formatters.matches",
    "app.formatters.misc",
    "app.formatters.predictions",
    "app.formatters.quiz",
    "app.formatters.table",
    "app.jobs.daily_facts",
    "app.jobs.misc",
    "app.jobs.reminders",
    "app.keyboards.admin",
    "app.keyboards.archive",
    "app.keyboards.facts",
    "app.keyboards.matches",
    "app.keyboards.panini",
    "app.keyboards.predictions",
    "app.keyboards.quiz",
    "app.keyboards.table",
    "app.middleware.access",
    "app.repositories.archive",
    "app.repositories.facts",
    "app.repositories.matches",
    "app.repositories.predictions",
    "app.repositories.quiz",
    "app.repositories.tournament",
    "app.repositories.users",
    "app.services.admin",
    "app.services.archive",
    "app.services.facts",
    "app.services.forecast",
    "app.services.matches",
    "app.services.misc",
    "app.services.notifications",
    "app.services.panini",
    "app.services.predictions",
    "app.services.quiz",
    "app.services.table",
    "app.services.tournament",
    "app.services.users",
    "app.states",
    "app.handlers.admin",
    "app.handlers.archive",
    "app.handlers.facts",
    "app.handlers.forecast",
    "app.handlers.help",
    "app.handlers.matches",
    "app.handlers.misc",
    "app.handlers.panini",
    "app.handlers.predictions",
    "app.handlers.quiz",
    "app.handlers.start",
    "app.handlers.table",
    "app.handlers.tournament",
]

_modules = [importlib.import_module(name) for name in MODULE_NAMES]

# Backward-compatible symbol injection: extracted functions keep their original
# bodies and can resolve helpers that now live in neighboring modules.
_public_symbols = {}
for _module in _modules:
    for _name, _value in vars(_module).items():
        if not _name.startswith("_"):
            _public_symbols[_name] = _value

for _module in _modules:
    vars(_module).update(_public_symbols)

# Make symbols available from app.bot_runtime for legacy imports, if any.
globals().update(_public_symbols)

dp.message.middleware(GroupCommandAccessMiddleware())
dp.message.middleware(CommandLoggingMiddleware())
dp.callback_query.middleware(GroupCallbackAccessMiddleware())


def _cb_startswith(prefix: str):
    """Build a callback-data prefix filter for manual handler registration."""
    return lambda callback: (callback.data or "").startswith(prefix)


def _cb_equals(value: str):
    """Build a callback-data equality filter for manual handler registration."""
    return lambda callback: (callback.data or "") == value


def register_handlers():
    """Register message and callback handlers extracted from the original monolith.

    The full modular split keeps handler implementations in app.handlers.* modules.
    Because decorators were removed during extraction, this bootstrap registers the
    handlers explicitly against the shared aiogram Dispatcher.
    """
    from aiogram import F
    from aiogram.filters import Command
    from app.states import (
        AdminResultForm,
        MatchPredictionForm,
        PaniniForm,
        TournamentPredictionForm,
    )

    if getattr(register_handlers, "_registered", False):
        return

    register_handlers._registered = True

    # Commands / message handlers.
    dp.message.register(_public_symbols["start_handler"], Command("start"))
    dp.message.register(_public_symbols["matches_handler"], Command("matches"))
    dp.message.register(_public_symbols["predict_handler"], Command("predict"))
    dp.message.register(_public_symbols["forecast_handler"], Command("forecast"))
    dp.message.register(_public_symbols["mybets_handler"], Command("mybets"))
    dp.message.register(_public_symbols["predictions_handler"], Command("predictions"))
    dp.message.register(_public_symbols["table_handler"], Command("table"))
    dp.message.register(_public_symbols["rules_handler"], Command("rules"))
    dp.message.register(_public_symbols["tournament_set_handler"], Command("tournament_set"))
    dp.message.register(_public_symbols["tournament_handler"], Command("tournament"))
    dp.message.register(_public_symbols["tournament_predictions_handler"], Command("tournament_predictions"))
    dp.message.register(_public_symbols["admin_handler"], Command("admin"))
    dp.message.register(_public_symbols["match_handler"], Command("match"))
    dp.message.register(_public_symbols["admin_set_result_handler"], Command("admin_set_result"))
    dp.message.register(_public_symbols["admin_recalculate_handler"], Command("admin_recalculate"))
    dp.message.register(_public_symbols["admin_set_tournament_result_handler"], Command("admin_set_tournament_result"))
    dp.message.register(_public_symbols["admin_tournament_recalculate_handler"], Command("admin_tournament_recalculate"))
    dp.message.register(_public_symbols["admin_matches_handler"], Command("admin_matches"))
    dp.message.register(_public_symbols["admin_matches_all_handler"], Command("admin_matches_all"))
    dp.message.register(_public_symbols["admin_edit_match_handler"], Command("admin_edit_match"))
    dp.message.register(_public_symbols["admin_delete_match_handler"], Command("admin_delete_match"))
    dp.message.register(_public_symbols["admin_force_delete_match_handler"], Command("admin_force_delete_match"))

    dp.message.register(_public_symbols["tournament_champion_handler"], TournamentPredictionForm.champion)
    dp.message.register(_public_symbols["tournament_runner_up_handler"], TournamentPredictionForm.runner_up)
    dp.message.register(_public_symbols["tournament_third_place_handler"], TournamentPredictionForm.third_place)
    dp.message.register(_public_symbols["tournament_top_scorer_handler"], TournamentPredictionForm.top_scorer)
    dp.message.register(_public_symbols["cancel_handler"], Command("cancel"))
    dp.message.register(_public_symbols["match_custom_score_handler"], MatchPredictionForm.custom_score)

    dp.message.register(_public_symbols["matches_all_handler"], Command("matches_all"))
    dp.message.register(_public_symbols["predict_all_handler"], Command("predict_all"))
    dp.message.register(_public_symbols["admin_import_matches_handler"], Command("admin_import_matches"))
    dp.message.register(_public_symbols["missing_handler"], Command("missing"))
    dp.message.register(_public_symbols["missing_all_handler"], Command("missing_all"))
    dp.message.register(_public_symbols["admin_reminders_status_handler"], Command("admin_reminders_status"))
    dp.message.register(_public_symbols["summary_handler"], Command("summary"))
    dp.message.register(_public_symbols["admin_result_custom_score_handler"], AdminResultForm.custom_score)
    dp.message.register(_public_symbols["help_handler"], Command("help"))
    dp.message.register(_public_symbols["ai_summary_handler"], Command("ai_summary"))
    dp.message.register(_public_symbols["admin_sync_wc2026_schedule_handler"], Command("admin_sync_wc2026_schedule"))
    dp.message.register(_public_symbols["admin_sync_results_handler"], Command("admin_sync_results"))
    dp.message.register(_public_symbols["admin_rankings_check_handler"], Command("admin_rankings_check"))
    dp.message.register(_public_symbols["admin_notify_test_handler"], Command("admin_notify_test"))
    dp.message.register(_public_symbols["admin_command_stats_handler"], Command("admin_command_stats"))
    dp.message.register(_public_symbols["admin_command_stats_user_handler"], Command("admin_command_stats_user"))
    dp.message.register(_public_symbols["fact_handler"], Command("fact"))
    dp.message.register(_public_symbols["admin_facts_count_handler"], Command("admin_facts_count"))
    dp.message.register(_public_symbols["admin_import_facts_handler"], Command("admin_import_facts"))
    dp.message.register(_public_symbols["admin_daily_fact_preview_handler"], Command("admin_daily_fact_preview"))
    dp.message.register(_public_symbols["quiz_handler"], Command("quiz"))
    dp.message.register(_public_symbols["admin_import_quiz_handler"], Command("admin_import_quiz"))
    dp.message.register(_public_symbols["quiz_stats_handler"], Command("quiz_stats"))
    dp.message.register(_public_symbols["admin_quiz_stats_handler"], Command("admin_quiz_stats"))
    dp.message.register(_public_symbols["admin_import_archive_handler"], Command("admin_import_archive"))
    dp.message.register(_public_symbols["archive_handler"], Command("archive"))
    dp.message.register(_public_symbols["admin_archive_count_handler"], Command("admin_archive_count"))
    dp.message.register(_public_symbols["panini_handler"], Command("panini"))
    dp.message.register(_public_symbols["chat_id_handler"], Command("chat_id"))
    dp.message.register(_public_symbols["group_quiz_finish_handler"], Command("quiz_finish"))
    dp.message.register(_public_symbols["group_quiz_table_handler"], Command("quiz_table"))
    dp.message.register(_public_symbols["admin_send_daily_fact_group_handler"], Command("admin_send_daily_fact_group"))
    dp.message.register(_public_symbols["panini_photo_handler"], PaniniForm.waiting_for_photo, F.photo)
    dp.message.register(_public_symbols["panini_photo_invalid_handler"], PaniniForm.waiting_for_photo)
    dp.message.register(_public_symbols["table_buttons_handler"], Command("table_buttons"))

    # Callback handlers.
    dp.callback_query.register(_public_symbols["predict_match_callback"], _cb_startswith("predict_match:"))
    dp.callback_query.register(_public_symbols["predict_score_callback"], _cb_startswith("predict_score:"))
    dp.callback_query.register(_public_symbols["predict_advancement_callback"], _cb_startswith("predict_adv:"))
    dp.callback_query.register(_public_symbols["predict_custom_callback"], _cb_startswith("predict_custom:"))
    dp.callback_query.register(_public_symbols["admin_result_match_callback"], _cb_startswith("admin_result_match:"))
    dp.callback_query.register(_public_symbols["admin_result_score_callback"], _cb_startswith("admin_result_score:"))
    dp.callback_query.register(_public_symbols["admin_result_winner_callback"], _cb_startswith("admin_result_winner:"))
    dp.callback_query.register(_public_symbols["admin_result_custom_callback"], _cb_startswith("admin_result_custom:"))
    dp.callback_query.register(_public_symbols["predictions_match_callback"], _cb_startswith("predictions_match:"))
    dp.callback_query.register(_public_symbols["match_card_callback"], _cb_startswith("match_card:"))
    dp.callback_query.register(_public_symbols["forecast_match_callback"], _cb_startswith("forecast_match:"))
    dp.callback_query.register(_public_symbols["quiz_answer_callback"], _cb_startswith("quiz_answer:"))
    dp.callback_query.register(_public_symbols["fact_category_callback"], _cb_startswith("fact_category:"))
    dp.callback_query.register(_public_symbols["quiz_category_callback"], _cb_startswith("quiz_category:"))
    dp.callback_query.register(_public_symbols["group_quiz_answer_callback"], _cb_startswith("group_quiz_answer:"))
    dp.callback_query.register(_public_symbols["panini_team_callback"], PaniniForm.waiting_for_team, _cb_startswith("panini_team:"))
    dp.callback_query.register(_public_symbols["table_noop_callback"], _cb_equals("table_noop"))


register_handlers()


async def main():
    """Start background jobs and run aiogram polling."""
    if _public_symbols["reminders_enabled"]():
        asyncio.create_task(_public_symbols["reminders_loop"]())

    if DAILY_FACTS_ENABLED:
        asyncio.create_task(_public_symbols["daily_facts_loop"]())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
