FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

WORKDIR /app

COPY pyproject.toml ./

RUN uv pip install --system requests pymongo python-dotenv

COPY config/ ./config/
COPY stream_stackexchange/ ./stream_stackexchange/

RUN mkdir -p /app/data

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "stream_stackexchange/setup_data_pipeline.py"]
