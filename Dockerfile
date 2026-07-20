FROM node:22-slim AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=croqui_engine.app.web

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libgl1 libglib2.0-0 libreoffice-calc libreoffice-draw \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend-build /frontend/dist ./croqui_engine/app/static/editor
RUN mkdir -p data/uploads data/outputs data/tmp docs

EXPOSE 5000

CMD ["flask", "--app", "croqui_engine.app.web", "run", "--host=0.0.0.0", "--port=5000"]
