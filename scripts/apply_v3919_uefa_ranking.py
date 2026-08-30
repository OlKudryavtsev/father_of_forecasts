from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Cannot find {label}")
    return text.replace(old, new, 1)


# 1. Tournament-aware ranking context. Keep the old public function as a
# compatibility wrapper, but make the generic builder the implementation.
path = ROOT / "app/wc2026_forecast_context.py"
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "from app.fifa_rankings import FifaRankingsStore\n",
    "from app.fifa_rankings import FifaRankingsStore\nfrom app.uefa_club_rankings import UefaClubRankingsStore\n",
    "UEFA ranking import",
)
start = text.index("def build_wc2026_openai_context")
prefix = text[:start]
new_tail = r'''def is_ucl_forecast_match(match) -> bool:
    code = str(getattr(match, "tournament_code", "") or "").strip().lower()
    return code.startswith("ucl_") or code.startswith("ucl-")


def build_team_strength_ranking_context(
    match,
    home_api_name: str,
    away_api_name: str,
) -> dict[str, Any]:
    """Return the correct strength-ranking source for the tournament."""
    if is_ucl_forecast_match(match):
        store = UefaClubRankingsStore()
        rankings = {
            home_api_name: store.get_context(home_api_name),
            away_api_name: store.get_context(away_api_name),
        }
        return {
            "type": "uefa_club_coefficient",
            "display_label": "Клубный рейтинг UEFA",
            "source": "UEFA.com",
            "source_url": store.data.get("source_url"),
            "reference_period": store.data.get("reference_period"),
            "lower_rank_is_stronger": True,
            "rankings": rankings,
            "note": (
                "Use the official UEFA club coefficient ranking snapshot at the end of 2025/26. "
                "Lower rank number means stronger club. If rank is null with ranking_status=not_ranked, "
                "the club is known but UEFA listed its coefficient ranking as N/A."
            ),
        }

    store = FifaRankingsStore()
    rankings = {
        home_api_name: store.get_context(home_api_name),
        away_api_name: store.get_context(away_api_name),
    }
    return {
        "type": "fifa_national_team",
        "display_label": "FIFA ranking",
        "source": "sofascore",
        "source_url": None,
        "reference_period": None,
        "lower_rank_is_stronger": True,
        "rankings": rankings,
        "note": (
            "For FIFA ranking, if total_points is null, use rank only. "
            "Lower rank number means stronger national team. "
            "Do not treat missing points as missing ranking if rank is available."
        ),
    }


def build_openai_forecast_context(db, match) -> dict[str, Any]:
    api_client = ApiFootballClient()

    before_date = match.starts_at
    if before_date.tzinfo is None:
        before_date = before_date.replace(tzinfo=timezone.utc)

    home_api_name = match.home_team_api_name or match.home_team
    away_api_name = match.away_team_api_name or match.away_team
    ranking_context = build_team_strength_ranking_context(match, home_api_name, away_api_name)

    home_recent = []
    away_recent = []

    if match.home_external_team_id:
        home_recent = build_recent_matches_context(
            api_client=api_client,
            team_id=match.home_external_team_id,
            before_date=before_date,
        )

    if match.away_external_team_id:
        away_recent = build_recent_matches_context(
            api_client=api_client,
            team_id=match.away_external_team_id,
            before_date=before_date,
        )

    h2h_rows = build_h2h_context(
        api_client=api_client,
        home_team_id=match.home_external_team_id,
        away_team_id=match.away_external_team_id,
        before_date=before_date,
        limit=5,
    )

    external_context = build_optional_external_forecast_context(
        api_client=api_client,
        match=match,
    )

    return {
        "fixture": {
            "internal_match_id": match.id,
            "external_fixture_id": match.external_fixture_id,
            "date": match.starts_at.isoformat(),
            "stage": match.stage,
            "match_round": match.match_round,
            "group_code": match.group_code,
            "home_team_display": match.home_team,
            "away_team_display": match.away_team,
            "home_team_api_name": home_api_name,
            "away_team_api_name": away_api_name,
        },
        "ranking_context": ranking_context,
        "team_strength_rankings": ranking_context["rankings"],
        # Compatibility for older consumers. UCL never receives FIFA values.
        "fifa_rankings_sofascore": (
            ranking_context["rankings"]
            if ranking_context["type"] == "fifa_national_team"
            else {}
        ),
        "recent_matches_before_fixture": {
            home_api_name: home_recent,
            away_api_name: away_recent,
        },
        "recent_matches_short": {
            home_api_name: compact_match_rows(home_recent, limit=3),
            away_api_name: compact_match_rows(away_recent, limit=3),
        },
        "recent_form_stats": {
            home_api_name: calculate_basic_stats(home_recent, home_api_name),
            away_api_name: calculate_basic_stats(away_recent, away_api_name),
        },
        "head_to_head": {
            "matches": h2h_rows,
            "matches_short": compact_match_rows(h2h_rows, limit=5),
        },
        "external_context": external_context,
        "note": ranking_context["note"],
    }


def build_wc2026_openai_context(db, match) -> dict[str, Any]:
    """Backward-compatible alias for legacy imports."""
    return build_openai_forecast_context(db, match)
'''
path.write_text(prefix + new_tail, encoding="utf-8")


# 2. The model prompt must follow ranking_context instead of assuming FIFA.
path = ROOT / "app/openai_forecaster.py"
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "2. Сначала оцени базовую силу команд по FIFA ranking.",
    "2. Сначала оцени базовую силу команд по ranking_context. Используй ровно указанный там тип рейтинга: FIFA для сборных и UEFA club coefficient для клубных турниров; не подменяй один рейтинг другим.",
    "generic ranking prompt",
)
text = replace_once(
    text,
    "3. Затем оцени форму по последним матчам и H2H.",
    "3. Если ranking_context.rankings содержит rank=null и ranking_status=not_ranked, считай клуб известным, но без числовой позиции; не выдумывай рейтинг. Затем оцени форму по последним матчам и H2H.",
    "unranked club prompt",
)
path.write_text(text, encoding="utf-8")


# 3. User-facing forecast heading and versioned UCL AI method.
path = ROOT / "app/services/forecast.py"
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "from typing import Any\n",
    "from datetime import datetime, timezone\nfrom typing import Any\n",
    "forecast datetime import",
)
text = replace_once(
    text,
    "from app.runtime import Match, User, build_wc2026_openai_context, generate_openai_forecast\n",
    "from app.runtime import Match, User, generate_openai_forecast\nfrom app.wc2026_forecast_context import build_openai_forecast_context\n",
    "generic context import",
)
text = replace_once(
    text,
    "from app.constants.categories import PLAYOFF_STAGES\n\n\n",
    '''from app.constants.categories import PLAYOFF_STAGES


UCL_FORECAST_SOURCE = "ai-uefa-v1"


def _is_ucl_match(match: Match) -> bool:
    code = str(getattr(match, "tournament_code", "") or "").strip().lower()
    return code.startswith("ucl_") or code.startswith("ucl-")


def forecast_source_for_match(match: Match) -> str:
    return UCL_FORECAST_SOURCE if _is_ucl_match(match) else "ai"


def should_refresh_father_forecast(existing, match: Match, now: datetime | None = None) -> bool:
    """Refresh stale future UCL AI forecasts exactly once after this method upgrade."""
    if not _is_ucl_match(match) or getattr(match, "is_finished", False):
        return False

    desired_source = forecast_source_for_match(match)
    current_source = str(getattr(existing, "source", "") or "")
    if current_source == desired_source:
        return False
    if current_source != "ai" and not current_source.startswith("ai-"):
        return False

    starts_at = getattr(match, "starts_at", None)
    if starts_at is None:
        return False
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    return starts_at > current_time


''',
    "forecast source helpers",
)
text = replace_once(
    text,
    "    context = build_wc2026_openai_context(db, match)",
    "    context = build_openai_forecast_context(db, match)",
    "generic forecast builder",
)
text = replace_once(
    text,
    '    rankings = context.get("fifa_rankings_sofascore") or {}\n',
    '    ranking_context = context.get("ranking_context") or {}\n    rankings = ranking_context.get("rankings") or context.get("fifa_rankings_sofascore") or {}\n    ranking_label = ranking_context.get("display_label") or "FIFA ranking"\n',
    "ranking context reader",
)
text = replace_once(
    text,
    '        "FIFA ranking:\\n"\n',
    '        f"{ranking_label}:\\n"\n',
    "dynamic ranking heading",
)
path.write_text(text, encoding="utf-8")


# 4. A known UEFA N/A is different from a missing lookup.
path = ROOT / "app/formatters/matches.py"
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    rank = ranking.get("rank")
    total_points = ranking.get("total_points")

    if total_points is not None:
        return f"{team_name}: #{rank}, {total_points} очк."

    return f"{team_name}: #{rank}"
''',
    '''    rank = ranking.get("rank")
    total_points = ranking.get("total_points")

    if rank is None:
        if ranking.get("ranking_status") == "not_ranked":
            return f"{team_name}: позиция не присвоена (N/A)"
        return f"{team_name}: рейтинг не найден"

    if total_points is not None:
        return f"{team_name}: #{rank}, {total_points} очк."

    return f"{team_name}: #{rank}"
''',
    "N/A ranking formatter",
)
path.write_text(text, encoding="utf-8")


# 5. Future UCL forecasts created with the old method get regenerated on the
# next read; started/finished forecasts remain frozen for fairness.
path = ROOT / "app/api/webapp.py"
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "from app.services.forecast import build_forecast_text\n",
    "from app.services.forecast import build_forecast_text, forecast_source_for_match, should_refresh_father_forecast\n",
    "forecast refresh imports",
)
function_start = text.index("def _ensure_father_match_prediction")
function_end = text.index("\ndef _prediction_by_match_id", function_start)
new_function = r'''def _ensure_father_match_prediction(db: Session, match: Match, allow_ai: bool = True) -> FatherMatchPrediction:
    existing = db.query(FatherMatchPrediction).filter(FatherMatchPrediction.match_id == match.id).first()
    if existing:
        if allow_ai and should_refresh_father_forecast(existing, match):
            try:
                refreshed_text = build_forecast_text(db, match)
                refreshed_home, refreshed_away = _parse_father_score_from_text(refreshed_text)
                enabled, side = _father_advancement_from_text(
                    refreshed_text,
                    match,
                    refreshed_home,
                    refreshed_away,
                )
                existing.pred_home = refreshed_home
                existing.pred_away = refreshed_away
                existing.outcome = _score_outcome(refreshed_home, refreshed_away)
                existing.advancement_bet_enabled = enabled
                existing.predicted_advancing_side = side
                existing.source = forecast_source_for_match(match)
                existing.forecast_text = refreshed_text
                db.commit()
                db.refresh(existing)
            except Exception as error:
                # Preserve the old frozen row if an external provider/OpenAI is
                # temporarily unavailable during the one-time method migration.
                print(f"Failed to refresh UCL Father forecast {match.id}: {error}")

        # Safety for databases where the schema migration is applied after this
        # code: infer a legacy pick only when no explicit playoff marker existed.
        if is_playoff_match(match) and not existing.advancement_bet_enabled and not existing.predicted_advancing_side:
            enabled, side = _father_advancement_from_text(
                existing.forecast_text,
                match,
                existing.pred_home,
                existing.pred_away,
            )
            if enabled:
                existing.advancement_bet_enabled = True
                existing.predicted_advancing_side = side
                db.commit()
                db.refresh(existing)
        return existing

    score = _father_builtin_score(db, match)
    source = "seed"
    text = None

    if score is None and allow_ai:
        try:
            text = build_forecast_text(db, match)
            score = _parse_father_score_from_text(text)
            source = forecast_source_for_match(match)
        except Exception as error:
            text = f"Прогноз Отца временно недоступен, использован осторожный fallback 1:1. Ошибка: {error}"
            score = (1, 1)
            source = "fallback"

    if score is None:
        score = (1, 1)
        source = "fallback"
        text = "Прогноз Отца: 1:1. Осторожная ничья, потому что Отец сегодня без хрустального мяча."

    pred_home, pred_away = score
    if text is None:
        text = (
            "🤖 Прогноз Отца прогнозов\n\n"
            f"{match.home_team} — {match.away_team}\n"
            f"Прогноз счета: {pred_home}:{pred_away}\n\n"
            "Зафиксировано автоматически и больше не меняется после старта матча."
        )

    advancement_bet_enabled, predicted_advancing_side = _father_advancement_from_text(
        text,
        match,
        pred_home,
        pred_away,
    )

    prediction = FatherMatchPrediction(
        match_id=match.id,
        pred_home=pred_home,
        pred_away=pred_away,
        outcome=_score_outcome(pred_home, pred_away),
        advancement_bet_enabled=advancement_bet_enabled,
        predicted_advancing_side=predicted_advancing_side,
        confidence=None,
        source=source,
        forecast_text=text,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction
'''
text = text[:function_start] + new_function + text[function_end:]
path.write_text(text, encoding="utf-8")


# 6. Pure selector regression plus release version.
path = ROOT / "tests/test_uefa_forecast_ranking.py"
text = path.read_text(encoding="utf-8")
if "test_ucl_context_selector_uses_uefa_not_fifa" not in text:
    text += '''\n\ndef test_ucl_context_selector_uses_uefa_not_fifa():
    from types import SimpleNamespace
    from app.wc2026_forecast_context import build_team_strength_ranking_context

    match = SimpleNamespace(tournament_code="ucl_2026_2027")
    context = build_team_strength_ranking_context(match, "VfB Stuttgart", "Viking FK")
    assert context["type"] == "uefa_club_coefficient"
    assert context["display_label"] == "Клубный рейтинг UEFA"
    assert context["rankings"]["VfB Stuttgart"]["rank"] == 80
    assert context["rankings"]["Viking FK"]["rank"] == 202
'''
path.write_text(text, encoding="utf-8")

package_path = ROOT / "app/miniapp_frontend/package.json"
package = json.loads(package_path.read_text(encoding="utf-8"))
if package.get("version") != "3.9.18":
    raise SystemExit(f"Unexpected package version {package.get('version')}")
package["version"] = "3.9.19"
package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

lock_path = ROOT / "app/miniapp_frontend/package-lock.json"
lock = json.loads(lock_path.read_text(encoding="utf-8"))
lock["version"] = "3.9.19"
if "" in lock.get("packages", {}):
    lock["packages"][""]["version"] = "3.9.19"
lock_path.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
