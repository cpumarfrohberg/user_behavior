FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libsqlite3-dev \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

COPY . .

ENV PYTHONPATH=/app

EXPOSE 8000
CMD ["python", "stream_stackexchange/setup_data_pipeline.py"]
