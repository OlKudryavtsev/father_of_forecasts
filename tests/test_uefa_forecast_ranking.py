from pathlib import Path

from app.uefa_club_rankings import UefaClubRankingsStore


ROOT = Path(__file__).resolve().parents[1]


def test_uefa_snapshot_contains_all_ucl_league_phase_clubs():
    store = UefaClubRankingsStore()
    rows = store.data["rankings"]
    assert len(rows) == 36
    assert sum(row.get("rank") is not None for row in rows) == 35
    assert store.data["source"] == "UEFA.com"
    assert store.data["reference_period"] == "end_of_2025_26"


def test_uefa_rankings_resolve_provider_and_display_aliases():
    store = UefaClubRankingsStore()
    assert store.get_context("VfB Stuttgart")["rank"] == 80
    assert store.get_context("Штутгарт")["rank"] == 80
    assert store.get_context("Viking FK")["rank"] == 202
    assert store.get_context("Викинг")["rank"] == 202
    assert store.get_context("Sabah FA")["rank"] == 244
    assert store.get_context("Сабах")["rank"] == 244


def test_como_is_known_but_officially_unranked():
    context = UefaClubRankingsStore().get_context("Como 1907")
    assert context is not None
    assert context["rank"] is None
    assert context["rank_available"] is False
    assert context["ranking_status"] == "not_ranked"


def test_forecast_sources_use_generic_ranking_context_and_version_ucl_ai():
    context_source = (ROOT / "app/wc2026_forecast_context.py").read_text(encoding="utf-8")
    prompt_source = (ROOT / "app/openai_forecaster.py").read_text(encoding="utf-8")
    forecast_source = (ROOT / "app/services/forecast.py").read_text(encoding="utf-8")
    webapp_source = (ROOT / "app/api/webapp.py").read_text(encoding="utf-8")

    assert "build_team_strength_ranking_context" in context_source
    assert '"ranking_context"' in context_source
    assert "UefaClubRankingsStore" in context_source
    assert "по ranking_context" in prompt_source
    assert "по FIFA ranking" not in prompt_source
    assert "ranking_context.get(\"rankings\")" in forecast_source
    assert 'UCL_FORECAST_SOURCE = "ai-uefa-v1"' in forecast_source
    assert "should_refresh_father_forecast" in webapp_source
    assert "forecast_source_for_match(match)" in webapp_source
