"""Compatibility exports for the target module layout.

The executable implementations are currently re-exported from `app.bot_runtime`
to preserve behavior exactly. Move implementations from `app.bot_runtime` into
this module during the next refactoring iteration.
"""

from app.bot_runtime import tournament_set_handler, tournament_handler, tournament_predictions_handler, admin_set_tournament_result_handler, admin_tournament_recalculate_handler, tournament_champion_handler, tournament_runner_up_handler, tournament_third_place_handler, tournament_top_scorer_handler  # noqa: F401
