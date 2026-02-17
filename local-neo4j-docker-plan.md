---
name: local-neo4j-docker
overview: Make Neo4j run locally via Docker Compose, and wire the app + ETL to use the local Neo4j service instead of Neo4j Aura/cloud URIs.
---

## Serve Neo4j locally (Docker)

### Goal

- Run **Neo4j locally** (Docker) so the Cypher agent + ETL use a local graph DB instead of a cloud instance.
- Keep MongoDB/Postgres local as they already are.

### Key places in the repo today

- Compose currently runs only MongoDB + Postgres + ETL (`docker-compose.yml`), but **no Neo4j service**.
- The app reads Neo4j connection details from env via `config/__init__.py` (defaults to `bolt://localhost:7687`).
- The Cypher agent uses those values via `cypher_agent/config.py`.

### Implementation plan

- Add a `neo4j` service to `docker-compose.yml`
  - Expose ports `7474` (browser) and `7687` (bolt).
  - Configure auth via `NEO4J_AUTH=neo4j/<password>` (pull from env).
  - Persist data with a named volume (e.g. `neo4j_data`).
  - (Optional but recommended) add a healthcheck so dependent services wait for Neo4j readiness.

- Wire the ETL container to talk to the Neo4j container
  - In `docker-compose.yml` update `neo4j_etl`:
    - Add `depends_on: neo4j` (ideally with `condition: service_healthy` if healthcheck is added).
    - Set `NEO4J_URI=bolt://neo4j:7687` **inside the compose network** (service-name DNS), while keeping host-side `.env` as `bolt://localhost:7687` for Streamlit/CLI.

- Update local environment guidance
  - Update `README.md` to replace “Neo4j cloud instance” wording with local Neo4j instructions:
    - `NEO4J_URI=bolt://localhost:7687`
    - `NEO4J_USER=neo4j`
    - `NEO4J_PASSWORD=...`
    - Mention Neo4j browser at `http://localhost:7474`.

- (Strongly recommended) secret hygiene
  - Ensure `.env` files are not committed and don’t contain real keys/passwords.
  - Add a `.env.example` and a `.gitignore` entry for `.env`, `.env.*`.

### Verification (after changes)

- `docker compose up -d` and confirm Neo4j is reachable on `localhost:7687`.
- Run the Cypher agent initialization path (e.g. `cli.py` Cypher evaluation or a simple orchestrator query) to confirm it connects to local Neo4j.
- Run `streamlit run streamlit_app.py` and ask a Cypher-heavy question to confirm end-to-end.
