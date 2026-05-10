
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install fastapi uvicorn sqlalchemy psycopg2-binary aiogram
CMD -sh -c ["python bot.py & uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
