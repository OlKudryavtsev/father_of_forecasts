def get_outcome(home: int, away: int) -> str:
    if home > away:
        return "home"
    if away > home:
        return "away"
    return "draw"


def score_match_result_points(
    pred_home: int,
    pred_away: int,
    actual_home: int,
    actual_away: int,
) -> int:
    """
    3 очка — точный счет
    1 очко — угаданный исход
    0 очков — иначе
    """

    if pred_home == actual_home and pred_away == actual_away:
        return 3

    if get_outcome(pred_home, pred_away) == get_outcome(actual_home, actual_away):
        return 1

    return 0


def score_advancement_points(
    advancement_bet_enabled: bool,
    predicted_advancing_side: str | None,
    actual_winner_side: str | None,
) -> int:
    """
    Плей-офф:
    если участник НЕ ставил на проход — 0
    если ставил и угадал — +1
    если ставил и не угадал — -1
    """

    # ``predicted_advancing_side`` is the authoritative user choice.  Early
    # playoff rows created during the rollout can contain the side while the
    # auxiliary Boolean remains false; treating those as “no bet” silently
    # drops a deserved +1 / -1 during recalculation.
    has_advancement_pick = bool(advancement_bet_enabled) or predicted_advancing_side in {"home", "away"}

    if not has_advancement_pick:
        return 0

    if predicted_advancing_side not in {"home", "away"} or actual_winner_side not in {"home", "away"}:
        return 0

    if predicted_advancing_side == actual_winner_side:
        return 1

    return -1


def score_match_prediction(
    pred_home: int,
    pred_away: int,
    actual_home: int,
    actual_away: int,
    advancement_bet_enabled: bool = False,
    predicted_advancing_side: str | None = None,
    actual_winner_side: str | None = None,
) -> dict:
    score_points = score_match_result_points(
        pred_home=pred_home,
        pred_away=pred_away,
        actual_home=actual_home,
        actual_away=actual_away,
    )

    advancement_points = score_advancement_points(
        advancement_bet_enabled=advancement_bet_enabled,
        predicted_advancing_side=predicted_advancing_side,
        actual_winner_side=actual_winner_side,
    )

    return {
        "score_points": score_points,
        "advancement_points": advancement_points,
        "total_points": score_points + advancement_points,
    }

def normalize_text(value: str) -> str:
    return value.strip().lower().replace("ё", "е")


def score_tournament_prediction(
    pred_champion: str,
    pred_runner_up: str,
    pred_third_place: str,
    pred_top_scorer: str,
    actual_champion: str,
    actual_runner_up: str,
    actual_third_place: str,
    actual_top_scorer: str,
) -> dict:
    champion_points = 0
    runner_up_points = 0
    third_place_points = 0
    top_scorer_points = 0

    if normalize_text(pred_champion) == normalize_text(actual_champion):
        champion_points = 15

    if normalize_text(pred_runner_up) == normalize_text(actual_runner_up):
        runner_up_points = 10

    if normalize_text(pred_third_place) == normalize_text(actual_third_place):
        third_place_points = 5

    if normalize_text(pred_top_scorer) == normalize_text(actual_top_scorer):
        top_scorer_points = 15

    total_points = (
        champion_points
        + runner_up_points
        + third_place_points
        + top_scorer_points
    )

    return {
        "champion_points": champion_points,
        "runner_up_points": runner_up_points,
        "third_place_points": third_place_points,
        "top_scorer_points": top_scorer_points,
        "total_points": total_points,
    }