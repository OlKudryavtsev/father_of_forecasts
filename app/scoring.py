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

    if not advancement_bet_enabled:
        return 0

    if not predicted_advancing_side or not actual_winner_side:
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