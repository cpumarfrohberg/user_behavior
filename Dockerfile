FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install requests pymongo python-dotenv ollama

COPY config/ ./config/
COPY stream_stackexchange/ ./stream_stackexchange/

RUN mkdir -p /app/data

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "stream_stackexchange/collector.py"]
