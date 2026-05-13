import math
from dataclasses import dataclass

from app.predictor import TeamStats, get_outcome
from app.team_ratings import get_team_rating


@dataclass
class MatchPredictionV2:
    home_team: str
    away_team: str
    pred_home: int
    pred_away: int
    outcome: str
    confidence: float
    explanation: str


def poisson_probability(lmbda: float, goals: int) -> float:
    return math.exp(-lmbda) * (lmbda ** goals) / math.factorial(goals)


def normalize_stage(stage_or_round: str | None) -> str:
    if not stage_or_round:
        return "group"

    value = stage_or_round.lower()

    if "final" in value or "quarter" in value or "semi" in value or "round" in value:
        return "playoff"

    return "group"


def calculate_team_strength(team: str, stats: TeamStats) -> float:
    base_rating = get_team_rating(team)

    # переводим рейтинг 60-95 примерно в диапазон -1.5 ... +2.0
    base_strength = (base_rating - 75) / 10

    if stats.played == 0:
        return base_strength

    form_strength = (
        0.45 * stats.points_per_game
        + 0.35 * stats.goal_diff_per_game
        + 0.20 * (stats.goals_for_per_game - stats.goals_against_per_game)
    )

    # На ранних матчах сильнее доверяем базовому рейтингу.
    # Чем больше матчей сыграно, тем больше вес формы.
    form_weight = min(0.55, stats.played * 0.18)
    base_weight = 1 - form_weight

    return base_weight * base_strength + form_weight * form_strength


def expected_goals_from_strength(
    home_strength: float,
    away_strength: float,
    stage: str,
) -> tuple[float, float]:
    diff = home_strength - away_strength

    # На плей-офф чуть ниже результативность.
    base_total = 2.55 if stage == "group" else 2.25

    home_share = 0.50 + max(-0.22, min(0.22, diff * 0.08))

    expected_home = base_total * home_share
    expected_away = base_total * (1 - home_share)

    expected_home = max(0.35, min(expected_home, 3.2))
    expected_away = max(0.35, min(expected_away, 3.2))

    return expected_home, expected_away


def outcome_probabilities(expected_home: float, expected_away: float) -> dict:
    probs = {
        "home": 0.0,
        "draw": 0.0,
        "away": 0.0,
    }

    for home_goals in range(0, 7):
        for away_goals in range(0, 7):
            prob = (
                poisson_probability(expected_home, home_goals)
                * poisson_probability(expected_away, away_goals)
            )

            outcome = get_outcome(home_goals, away_goals)
            probs[outcome] += prob

    return probs


def choose_score_for_outcome(
    expected_home: float,
    expected_away: float,
    target_outcome: str,
) -> tuple[int, int]:
    best_score = (1, 1)
    best_prob = -1.0

    for home_goals in range(0, 6):
        for away_goals in range(0, 6):
            if get_outcome(home_goals, away_goals) != target_outcome:
                continue

            prob = (
                poisson_probability(expected_home, home_goals)
                * poisson_probability(expected_away, away_goals)
            )

            # Небольшая эвристика: 0:0 редко хороший прогноз для дружеского scoring,
            # поэтому чуть штрафуем его.
            if home_goals == 0 and away_goals == 0:
                prob *= 0.75

            if prob > best_prob:
                best_prob = prob
                best_score = (home_goals, away_goals)

    return best_score


def predict_match_v2(
    home_team: str,
    away_team: str,
    team_stats: dict[str, TeamStats],
    stage_or_round: str | None = None,
) -> MatchPredictionV2:
    stage = normalize_stage(stage_or_round)

    home_stats = team_stats.get(home_team, TeamStats())
    away_stats = team_stats.get(away_team, TeamStats())

    home_strength = calculate_team_strength(home_team, home_stats)
    away_strength = calculate_team_strength(away_team, away_stats)

    expected_home, expected_away = expected_goals_from_strength(
        home_strength=home_strength,
        away_strength=away_strength,
        stage=stage,
    )

    probs = outcome_probabilities(expected_home, expected_away)

    # Чуть уменьшаем ничью в группах, потому что по системе очков лучше чаще
    # пытаться взять исход, чем постоянно ставить 1:1.
    adjusted_probs = probs.copy()

    if stage == "group":
        adjusted_probs["draw"] *= 0.88
    else:
        adjusted_probs["draw"] *= 0.95

    target_outcome = max(adjusted_probs, key=adjusted_probs.get)

    pred_home, pred_away = choose_score_for_outcome(
        expected_home=expected_home,
        expected_away=expected_away,
        target_outcome=target_outcome,
    )

    confidence = max(adjusted_probs.values())

    explanation = (
        f"Модель учитывает базовую силу команд и форму по уже сыгранным матчам. "
        f"Ожидаемые голы: {home_team} {expected_home:.2f}, "
        f"{away_team} {expected_away:.2f}. "
        f"Вероятности исходов: победа первой команды {probs['home']:.0%}, "
        f"ничья {probs['draw']:.0%}, победа второй команды {probs['away']:.0%}."
    )

    return MatchPredictionV2(
        home_team=home_team,
        away_team=away_team,
        pred_home=pred_home,
        pred_away=pred_away,
        outcome=target_outcome,
        confidence=round(confidence, 2),
        explanation=explanation,
    )