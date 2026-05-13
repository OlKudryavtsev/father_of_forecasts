import math
from dataclasses import dataclass, field


@dataclass
class TeamStats:
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0

    @property
    def points(self) -> int:
        return self.wins * 3 + self.draws

    @property
    def points_per_game(self) -> float:
        if self.played == 0:
            return 1.0
        return self.points / self.played

    @property
    def goal_diff_per_game(self) -> float:
        if self.played == 0:
            return 0.0
        return (self.goals_for - self.goals_against) / self.played

    @property
    def goals_for_per_game(self) -> float:
        if self.played == 0:
            return 1.2
        return self.goals_for / self.played

    @property
    def goals_against_per_game(self) -> float:
        if self.played == 0:
            return 1.2
        return self.goals_against / self.played


@dataclass
class MatchPrediction:
    home_team: str
    away_team: str
    pred_home: int
    pred_away: int
    outcome: str
    confidence: float
    explanation: str


def get_outcome(home: int, away: int) -> str:
    if home > away:
        return "home"
    if away > home:
        return "away"
    return "draw"


def poisson_probability(lmbda: float, goals: int) -> float:
    return math.exp(-lmbda) * (lmbda ** goals) / math.factorial(goals)


def most_likely_score(expected_home: float, expected_away: float) -> tuple[int, int]:
    best_score = (1, 1)
    best_prob = -1.0

    for home_goals in range(0, 6):
        for away_goals in range(0, 6):
            probability = (
                poisson_probability(expected_home, home_goals)
                * poisson_probability(expected_away, away_goals)
            )

            if probability > best_prob:
                best_prob = probability
                best_score = (home_goals, away_goals)

    return best_score


def predict_match(
    home_team: str,
    away_team: str,
    team_stats: dict[str, TeamStats],
) -> MatchPrediction:
    home = team_stats.get(home_team, TeamStats())
    away = team_stats.get(away_team, TeamStats())

    ppg_diff = home.points_per_game - away.points_per_game
    gd_diff = home.goal_diff_per_game - away.goal_diff_per_game

    strength_diff = 0.65 * ppg_diff + 0.35 * gd_diff

    base_goals = 1.2

    expected_home = (
        base_goals
        + 0.25 * strength_diff
        + 0.15 * home.goals_for_per_game
        - 0.10 * away.goals_against_per_game
    )

    expected_away = (
        base_goals
        - 0.25 * strength_diff
        + 0.15 * away.goals_for_per_game
        - 0.10 * home.goals_against_per_game
    )

    expected_home = max(0.3, min(expected_home, 3.5))
    expected_away = max(0.3, min(expected_away, 3.5))

    pred_home, pred_away = most_likely_score(expected_home, expected_away)

    outcome = get_outcome(pred_home, pred_away)

    confidence = min(
        0.75,
        0.45 + abs(strength_diff) * 0.08,
    )

    explanation = (
        f"Оценка основана на форме команд в уже сыгранных матчах турнира. "
        f"{home_team}: {home.points_per_game:.2f} очка/матч, "
        f"разница мячей {home.goal_diff_per_game:.2f} за матч. "
        f"{away_team}: {away.points_per_game:.2f} очка/матч, "
        f"разница мячей {away.goal_diff_per_game:.2f} за матч."
    )

    return MatchPrediction(
        home_team=home_team,
        away_team=away_team,
        pred_home=pred_home,
        pred_away=pred_away,
        outcome=outcome,
        confidence=round(confidence, 2),
        explanation=explanation,
    )


def update_team_stats(
    team_stats: dict[str, TeamStats],
    home_team: str,
    away_team: str,
    score_home: int,
    score_away: int,
):
    home = team_stats.setdefault(home_team, TeamStats())
    away = team_stats.setdefault(away_team, TeamStats())

    home.played += 1
    away.played += 1

    home.goals_for += score_home
    home.goals_against += score_away

    away.goals_for += score_away
    away.goals_against += score_home

    if score_home > score_away:
        home.wins += 1
        away.losses += 1
    elif score_away > score_home:
        away.wins += 1
        home.losses += 1
    else:
        home.draws += 1
        away.draws += 1