from dataclasses import dataclass

from app.predictor import TeamStats, get_outcome
from app.predictor_v2 import (
    calculate_team_strength,
    expected_goals_from_strength,
    normalize_stage,
    outcome_probabilities,
    poisson_probability,
)


@dataclass
class MatchPredictionV3:
    home_team: str
    away_team: str
    pred_home: int
    pred_away: int
    outcome: str
    confidence: float
    explanation: str


POPULAR_SCORE_BONUS = {
    (1, 0): 1.05,
    (2, 0): 1.18,
    (2, 1): 1.20,
    (3, 1): 1.10,
    (0, 1): 1.05,
    (0, 2): 1.18,
    (1, 2): 1.20,
    (1, 3): 1.10,
    (1, 1): 1.20,
    (0, 0): 0.82,
    (2, 2): 1.05,
}


def get_score_candidates(target_outcome: str) -> list[tuple[int, int]]:
    if target_outcome == "home":
        return [
            (1, 0),
            (2, 0),
            (2, 1),
            (3, 0),
            (3, 1),
            (3, 2),
        ]

    if target_outcome == "away":
        return [
            (0, 1),
            (0, 2),
            (1, 2),
            (0, 3),
            (1, 3),
            (2, 3),
        ]

    return [
        (0, 0),
        (1, 1),
        (2, 2),
    ]


def choose_typical_score(
    expected_home: float,
    expected_away: float,
    target_outcome: str,
    strength_diff: float,
    stage: str,
) -> tuple[int, int]:
    candidates = get_score_candidates(target_outcome)

    best_score = candidates[0]
    best_value = -1.0

    for home_goals, away_goals in candidates:
        probability = (
            poisson_probability(expected_home, home_goals)
            * poisson_probability(expected_away, away_goals)
        )

        value = probability

        value *= POPULAR_SCORE_BONUS.get((home_goals, away_goals), 1.0)

        total_goals = home_goals + away_goals

        # В плей-офф чуть осторожнее с очень результативными счетами.
        if stage == "playoff" and total_goals >= 4:
            value *= 0.82

        # Если разница сил заметная, не боимся 2:0 / 3:1.
        if abs(strength_diff) >= 0.9:
            if target_outcome == "home" and (home_goals - away_goals) >= 2:
                value *= 1.12
            if target_outcome == "away" and (away_goals - home_goals) >= 2:
                value *= 1.12

        # Если силы близкие, чаще допускаем 2:1 / 1:2 / 1:1.
        if abs(strength_diff) < 0.6:
            if (home_goals, away_goals) in [(2, 1), (1, 2), (1, 1)]:
                value *= 1.10

        if value > best_value:
            best_value = value
            best_score = (home_goals, away_goals)

    return best_score


def predict_match_v3(
    home_team: str,
    away_team: str,
    team_stats: dict[str, TeamStats],
    stage_or_round: str | None = None,
) -> MatchPredictionV3:
    stage = normalize_stage(stage_or_round)

    home_stats = team_stats.get(home_team, TeamStats())
    away_stats = team_stats.get(away_team, TeamStats())

    home_strength = calculate_team_strength(home_team, home_stats)
    away_strength = calculate_team_strength(away_team, away_stats)
    strength_diff = home_strength - away_strength

    expected_home, expected_away = expected_goals_from_strength(
        home_strength=home_strength,
        away_strength=away_strength,
        stage=stage,
    )

    probs = outcome_probabilities(expected_home, expected_away)

    adjusted_probs = probs.copy()

    # В v2 ничьи уже стали реже. Здесь оставим мягкий штраф.
    if stage == "group":
        adjusted_probs["draw"] *= 0.92
    else:
        adjusted_probs["draw"] *= 0.98

    target_outcome = max(adjusted_probs, key=adjusted_probs.get)

    pred_home, pred_away = choose_typical_score(
        expected_home=expected_home,
        expected_away=expected_away,
        target_outcome=target_outcome,
        strength_diff=strength_diff,
        stage=stage,
    )

    confidence = max(adjusted_probs.values())

    explanation = (
        f"Модель учитывает базовую силу команд, форму в турнире и типовые футбольные счета. "
        f"Ожидаемые голы: {home_team} {expected_home:.2f}, "
        f"{away_team} {expected_away:.2f}. "
        f"Вероятности исходов: победа первой команды {probs['home']:.0%}, "
        f"ничья {probs['draw']:.0%}, победа второй команды {probs['away']:.0%}."
    )

    return MatchPredictionV3(
        home_team=home_team,
        away_team=away_team,
        pred_home=pred_home,
        pred_away=pred_away,
        outcome=get_outcome(pred_home, pred_away),
        confidence=round(confidence, 2),
        explanation=explanation,
    )