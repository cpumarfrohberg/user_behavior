#!/usr/bin/env bash
set -e
# Start infrastructure (MongoDB, PostgreSQL, Neo4j), then run Streamlit
docker compose up -d mongodb postgres neo4j
uv run streamlit run streamlit_app.py
