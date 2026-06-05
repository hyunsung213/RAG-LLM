FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV IEUNG_API_HOST=0.0.0.0
ENV IEUNG_API_PORT=10000
ENV CHROMA_PERSIST_DIR=./chroma_db
ENV CHROMA_COLLECTION_NAME=ieung_rag

CMD ["sh", "-c", "gunicorn wsgi:app --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 2 --timeout 120"]
