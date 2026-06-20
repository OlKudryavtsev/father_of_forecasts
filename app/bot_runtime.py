"""Application bootstrap for the modular Father Predictions bot.

This module wires middleware, registers handlers explicitly, starts background
jobs and runs aiogram polling. It intentionally does not perform dynamic symbol
injection between modules.
"""

import asyncio

from aiogram import F
from aiogram.filters import Command

from app.runtime import DAILY_FACTS_ENABLED, bot, dp
from app.middleware.access import (
    CommandLoggingMiddleware,
    UserAccessStatusMiddleware,
    GroupCallbackAccessMiddleware,
    GroupCommandAccessMiddleware,
)
from app.states import (
    AdminResultForm,
    MatchPredictionForm,
    PaniniForm,
    TournamentPredictionForm,
)
from app.handlers.admin import (
    admin_api_coverage_handler,
    admin_archive_count_handler,
    admin_command_stats_handler,
    admin_command_stats_user_handler,
    admin_daily_fact_preview_handler,
    admin_delete_match_handler,
    admin_edit_match_handler,
    admin_facts_count_handler,
    admin_force_delete_match_handler,
    admin_handler,
    admin_import_archive_handler,
    admin_import_facts_handler,
    admin_import_matches_handler,
    admin_import_quiz_handler,
    admin_matches_all_handler,
    admin_matches_handler,
    admin_notify_test_handler,
    admin_quiz_stats_handler,
    admin_release_handler,
    admin_rankings_check_handler,
    admin_recalculate_handler,
    admin_reminders_status_handler,
    admin_result_custom_callback,
    admin_result_custom_score_handler,
    admin_result_match_callback,
    admin_result_score_callback,
    admin_result_winner_callback,
    admin_send_daily_fact_group_handler,
    admin_set_result_handler,
    admin_set_tournament_result_handler,
    admin_sync_results_handler,
    admin_sync_wc2026_schedule_handler,
    admin_tournament_recalculate_handler,
)
from app.handlers.archive import archive_handler
from app.handlers.facts import fact_category_callback, fact_handler
from app.handlers.forecast import forecast_handler, forecast_match_callback
from app.handlers.help import help_handler, rules_handler
from app.handlers.matches import match_card_callback, match_handler, matches_all_handler, matches_handler
from app.handlers.misc import cancel_handler, match_custom_score_handler
from app.handlers.miniapp import miniapp_handler
from app.handlers.panini import panini_handler, panini_photo_handler, panini_photo_invalid_handler, panini_team_callback
from app.handlers.predictions import (
    missing_all_handler,
    missing_handler,
    mybets_handler,
    predict_advancement_callback,
    predict_all_handler,
    predict_custom_callback,
    predict_handler,
    predict_match_callback,
    predict_score_callback,
    predictions_handler,
    predictions_match_callback,
)
from app.handlers.quiz import (
    group_quiz_answer_callback,
    group_quiz_finish_handler,
    group_quiz_table_handler,
    quiz_answer_callback,
    quiz_category_callback,
    quiz_battle_answer_callback,
    quiz_battle_handler,
    quiz_battle_size_callback,
    quiz_handler,
    quiz_stats_handler,
)
from app.handlers.start import chat_id_handler, start_handler, access_approve_callback, access_reject_callback
from app.handlers.table import ai_summary_handler, summary_handler, table_buttons_handler, table_handler, table_noop_callback
from app.handlers.tournament import (
    tournament_champion_handler,
    tournament_forecast_handler,
    tournament_handler,
    tournament_predictions_handler,
    tournament_runner_up_handler,
    tournament_set_handler,
    tournament_third_place_handler,
    tournament_top_scorer_handler,
)
from app.jobs.reminders import reminders_enabled, reminders_loop
from app.services.facts import daily_facts_loop
from app.services.matchtv_videos import sync_matchtv_videos
from app.services.api_football_auto_sync import auto_sync_results_and_fantasy
from app.services.match_details import sync_active_match_details
from app.services.tournament_hub import sync_tournament_hub_cache
from app.db import SessionLocal
import os

dp.message.middleware(GroupCommandAccessMiddleware())
dp.message.middleware(CommandLoggingMiddleware())
dp.message.middleware(UserAccessStatusMiddleware())
dp.callback_query.middleware(UserAccessStatusMiddleware())
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
    if getattr(register_handlers, "_registered", False):
        return

    register_handlers._registered = True

    # Commands / message handlers.
    dp.message.register(start_handler, Command("start"))
    dp.message.register(matches_handler, Command("matches"))
    dp.message.register(predict_handler, Command("predict"))
    dp.message.register(forecast_handler, Command("forecast"))
    dp.message.register(mybets_handler, Command("mybets"))
    dp.message.register(predictions_handler, Command("predictions"))
    dp.message.register(table_handler, Command("table"))
    dp.message.register(rules_handler, Command("rules"))
    dp.message.register(tournament_set_handler, Command("tournament_set"))
    dp.message.register(tournament_handler, Command("tournament"))
    dp.message.register(tournament_forecast_handler, Command("tournament_forecast"))
    dp.message.register(tournament_predictions_handler, Command("tournament_predictions"))
    dp.message.register(admin_handler, Command("admin"))
    dp.message.register(match_handler, Command("match"))
    dp.message.register(admin_set_result_handler, Command("admin_set_result"))
    dp.message.register(admin_recalculate_handler, Command("admin_recalculate"))
    dp.message.register(admin_set_tournament_result_handler, Command("admin_set_tournament_result"))
    dp.message.register(admin_tournament_recalculate_handler, Command("admin_tournament_recalculate"))
    dp.message.register(admin_matches_handler, Command("admin_matches"))
    dp.message.register(admin_matches_all_handler, Command("admin_matches_all"))
    dp.message.register(admin_edit_match_handler, Command("admin_edit_match"))
    dp.message.register(admin_delete_match_handler, Command("admin_delete_match"))
    dp.message.register(admin_force_delete_match_handler, Command("admin_force_delete_match"))

    dp.message.register(tournament_champion_handler, TournamentPredictionForm.champion)
    dp.message.register(tournament_runner_up_handler, TournamentPredictionForm.runner_up)
    dp.message.register(tournament_third_place_handler, TournamentPredictionForm.third_place)
    dp.message.register(tournament_top_scorer_handler, TournamentPredictionForm.top_scorer)
    dp.message.register(cancel_handler, Command("cancel"))
    dp.message.register(match_custom_score_handler, MatchPredictionForm.custom_score)

    dp.message.register(matches_all_handler, Command("matches_all"))
    dp.message.register(predict_all_handler, Command("predict_all"))
    dp.message.register(admin_import_matches_handler, Command("admin_import_matches"))
    dp.message.register(missing_handler, Command("missing"))
    dp.message.register(missing_all_handler, Command("missing_all"))
    dp.message.register(admin_reminders_status_handler, Command("admin_reminders_status"))
    dp.message.register(summary_handler, Command("summary"))
    dp.message.register(admin_result_custom_score_handler, AdminResultForm.custom_score)
    dp.message.register(help_handler, Command("help"))
    dp.message.register(miniapp_handler, Command("app"))
    dp.message.register(ai_summary_handler, Command("ai_summary"))
    dp.message.register(admin_sync_wc2026_schedule_handler, Command("admin_sync_wc2026_schedule"))
    dp.message.register(admin_sync_results_handler, Command("admin_sync_results"))
    dp.message.register(admin_rankings_check_handler, Command("admin_rankings_check"))
    dp.message.register(admin_api_coverage_handler, Command("admin_api_coverage"))
    dp.message.register(admin_notify_test_handler, Command("admin_notify_test"))
    dp.message.register(admin_release_handler, Command("admin_release"))
    dp.message.register(admin_command_stats_handler, Command("admin_command_stats"))
    dp.message.register(admin_command_stats_user_handler, Command("admin_command_stats_user"))
    dp.message.register(fact_handler, Command("fact"))
    dp.message.register(admin_facts_count_handler, Command("admin_facts_count"))
    dp.message.register(admin_import_facts_handler, Command("admin_import_facts"))
    dp.message.register(admin_daily_fact_preview_handler, Command("admin_daily_fact_preview"))
    dp.message.register(quiz_handler, Command("quiz"))
    dp.message.register(quiz_battle_handler, Command("quiz_battle"))
    dp.message.register(admin_import_quiz_handler, Command("admin_import_quiz"))
    dp.message.register(quiz_stats_handler, Command("quiz_stats"))
    dp.message.register(admin_quiz_stats_handler, Command("admin_quiz_stats"))
    dp.message.register(admin_import_archive_handler, Command("admin_import_archive"))
    dp.message.register(archive_handler, Command("archive"))
    dp.message.register(admin_archive_count_handler, Command("admin_archive_count"))
    dp.message.register(panini_handler, Command("panini"))
    dp.message.register(chat_id_handler, Command("chat_id"))
    dp.message.register(group_quiz_finish_handler, Command("quiz_finish"))
    dp.message.register(group_quiz_table_handler, Command("quiz_table"))
    dp.message.register(admin_send_daily_fact_group_handler, Command("admin_send_daily_fact_group"))
    dp.message.register(panini_photo_handler, PaniniForm.waiting_for_photo, F.photo)
    dp.message.register(panini_photo_invalid_handler, PaniniForm.waiting_for_photo)
    dp.message.register(table_buttons_handler, Command("table_buttons"))

    # Callback handlers.
    dp.callback_query.register(predict_match_callback, _cb_startswith("predict_match:"))
    dp.callback_query.register(predict_score_callback, _cb_startswith("predict_score:"))
    dp.callback_query.register(predict_advancement_callback, _cb_startswith("predict_adv:"))
    dp.callback_query.register(predict_custom_callback, _cb_startswith("predict_custom:"))
    dp.callback_query.register(admin_result_match_callback, _cb_startswith("admin_result_match:"))
    dp.callback_query.register(admin_result_score_callback, _cb_startswith("admin_result_score:"))
    dp.callback_query.register(admin_result_winner_callback, _cb_startswith("admin_result_winner:"))
    dp.callback_query.register(admin_result_custom_callback, _cb_startswith("admin_result_custom:"))
    dp.callback_query.register(predictions_match_callback, _cb_startswith("predictions_match:"))
    dp.callback_query.register(match_card_callback, _cb_startswith("match_card:"))
    dp.callback_query.register(forecast_match_callback, _cb_startswith("forecast_match:"))
    dp.callback_query.register(quiz_answer_callback, _cb_startswith("quiz_answer:"))
    dp.callback_query.register(fact_category_callback, _cb_startswith("fact_category:"))
    dp.callback_query.register(quiz_category_callback, _cb_startswith("quiz_category:"))
    dp.callback_query.register(group_quiz_answer_callback, _cb_startswith("group_quiz_answer:"))
    dp.callback_query.register(quiz_battle_size_callback, _cb_startswith("quiz_battle_size:"))
    dp.callback_query.register(quiz_battle_answer_callback, _cb_startswith("quiz_battle_answer:"))
    dp.callback_query.register(panini_team_callback, PaniniForm.waiting_for_team, _cb_startswith("panini_team:"))
    dp.callback_query.register(access_approve_callback, _cb_startswith("access_approve:"))
    dp.callback_query.register(access_reject_callback, _cb_startswith("access_reject:"))
    dp.callback_query.register(table_noop_callback, _cb_equals("table_noop"))


register_handlers()


async def matchtv_videos_loop():
    """Periodically discover official Match TV video links for nearby matches."""
    enabled = os.getenv("MATCHTV_VIDEO_AUTOSYNC_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return

    interval_seconds = int(os.getenv("MATCHTV_VIDEO_AUTOSYNC_INTERVAL_SECONDS", "1800"))

    while True:
        db = SessionLocal()
        try:
            result = sync_matchtv_videos(db)
            print(f"Match TV video sync: {result}")
        except Exception as error:
            print(f"Match TV video sync failed: {error}")
        finally:
            db.close()

        await asyncio.sleep(interval_seconds)


async def match_details_cache_loop():
    """Warm cached events, lineups and statistics for live/nearby fixtures."""
    enabled = os.getenv("MATCH_DETAILS_AUTOSYNC_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return

    interval_seconds = max(45, int(os.getenv("MATCH_DETAILS_AUTOSYNC_INTERVAL_SECONDS", "90")))
    while True:
        db = SessionLocal()
        try:
            result = sync_active_match_details(db)
            print(f"Match details cache sync: {result}")
        except Exception as error:
            print(f"Match details cache sync failed: {error}")
        finally:
            db.close()
        await asyncio.sleep(interval_seconds)


async def tournament_hub_cache_loop():
    """Warm shared tournament data (currently the top-scorer table)."""
    enabled = os.getenv("TOURNAMENT_HUB_AUTOSYNC_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return

    interval_seconds = max(300, int(os.getenv("TOURNAMENT_HUB_AUTOSYNC_INTERVAL_SECONDS", "900")))
    while True:
        db = SessionLocal()
        try:
            result = sync_tournament_hub_cache(db)
            print(f"Tournament hub cache sync: {result}")
        except Exception as error:
            print(f"Tournament hub cache sync failed: {error}")
        finally:
            db.close()
        await asyncio.sleep(interval_seconds)


async def api_football_auto_sync_loop():
    """Periodically update recently finished match results and Fantasy stats."""
    enabled = os.getenv("API_FOOTBALL_AUTOSYNC_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return

    interval_seconds = int(os.getenv("API_FOOTBALL_AUTOSYNC_INTERVAL_SECONDS", "600"))

    while True:
        db = SessionLocal()
        try:
            result = auto_sync_results_and_fantasy(db)
            print(f"API-Football auto sync: {result}")
        except Exception as error:
            print(f"API-Football auto sync failed: {error}")
        finally:
            db.close()

        await asyncio.sleep(interval_seconds)


async def main():
    """Start background jobs and run aiogram polling."""
    if reminders_enabled():
        asyncio.create_task(reminders_loop())

    if DAILY_FACTS_ENABLED:
        asyncio.create_task(daily_facts_loop())

    asyncio.create_task(matchtv_videos_loop())
    asyncio.create_task(api_football_auto_sync_loop())
    asyncio.create_task(match_details_cache_loop())
    asyncio.create_task(tournament_hub_cache_loop())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
