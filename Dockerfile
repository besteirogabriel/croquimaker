FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates nodejs npm && rm -rf /var/lib/apt/lists/*
RUN npm install -g @openai/codex@0.145.0
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["python", "run.py"]
