"""FSM state classes used by bot handlers."""


from app.runtime import State, StatesGroup

class TournamentPredictionForm(StatesGroup):
    """Defines TournamentPredictionForm for the Telegram bot runtime."""
    champion = State()
    runner_up = State()
    third_place = State()
    top_scorer = State()


class MatchPredictionForm(StatesGroup):
    """Defines MatchPredictionForm for the Telegram bot runtime."""
    custom_score = State()


class AdminResultForm(StatesGroup):
    """Defines AdminResultForm for the Telegram bot runtime."""
    custom_score = State()


class PaniniForm(StatesGroup):
    """Defines PaniniForm for the Telegram bot runtime."""
    waiting_for_photo = State()
    waiting_for_team = State()



class LeagueQuizTextAnswerForm(StatesGroup):
    """Captures one text response in a private Telegram chat."""

    waiting_for_answer = State()
