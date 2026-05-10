from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel

from app.db import Base, SessionLocal, engine
from app.models import Match, Prediction, User

app = FastAPI(title="Отец прогнозов")

Base.metadata.create_all(bind=engine)


class MatchCreate(BaseModel):
    home_team: str
    away_team: str
    starts_at: datetime
    stage: str = "group"
    tournament_code: str = "wc2026"


@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"health": "green"}


@app.get("/users")
def get_users():
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.id).all()
        return [
            {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "display_name": user.display_name,
            }
            for user in users
        ]
    finally:
        db.close()


@app.get("/matches")
def get_matches():
    db = SessionLocal()
    try:
        matches = db.query(Match).order_by(Match.starts_at).all()
        return [
            {
                "id": match.id,
                "home_team": match.home_team,
                "away_team": match.away_team,
                "stage": match.stage,
                "starts_at": match.starts_at,
                "score_home": match.score_home,
                "score_away": match.score_away,
                "is_finished": match.is_finished,
            }
            for match in matches
        ]
    finally:
        db.close()


@app.post("/admin/matches")
def create_match(payload: MatchCreate):
    db = SessionLocal()
    try:
        match = Match(
            home_team=payload.home_team,
            away_team=payload.away_team,
            starts_at=payload.starts_at,
            stage=payload.stage,
            tournament_code=payload.tournament_code,
        )

        db.add(match)
        db.commit()
        db.refresh(match)

        return {
            "id": match.id,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "starts_at": match.starts_at,
        }
    finally:
        db.close()


@app.get("/predictions")
def get_predictions():
    db = SessionLocal()
    try:
        predictions = db.query(Prediction).all()

        return [
            {
                "id": prediction.id,
                "user": prediction.user.display_name,
                "match": f"{prediction.match.home_team} — {prediction.match.away_team}",
                "prediction": f"{prediction.pred_home}:{prediction.pred_away}",
                "points": prediction.points,
            }
            for prediction in predictions
        ]
    finally:
        db.close()