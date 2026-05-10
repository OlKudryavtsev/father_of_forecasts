
from fastapi import FastAPI
app = FastAPI(title='Отец прогнозов')

matches = [
    {"id":1,"home":"Mexico","away":"South Africa","start":"2026-06-11T18:00"}
]

predictions = []

@app.get("/matches")
def get_matches():
    return matches

@app.post("/predict/{match_id}")
def predict(match_id:int, user:str, home:int, away:int):
    predictions.append({
        "match_id":match_id,"user":user,"home":home,"away":away
    })
    return {"status":"ok"}

@app.get("/table")
def table():
    return {"leaderboard":[]}
