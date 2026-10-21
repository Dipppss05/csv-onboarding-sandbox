# CSV Onboarding Sandbox

A containerized data-onboarding service. You upload an employee CSV, every row is checked against a PostgreSQL schema, clean rows are loaded (or updated), and each bad row comes back with the exact reason it was rejected. Every upload is logged.

Built for ASU's *Growing a Competency* assignment to practice **Docker and Docker Compose**. Uses sample data only.

## Architecture

```
 ┌──────────── docker compose ────────────┐
 │                                        │
 │  api  (python:3.12-slim, FastAPI)      │  ← http://localhost:8000/docs
 │    │  waits for db healthcheck         │
 │    ▼                                   │
 │  db   (postgres:16-alpine)             │  ← localhost:5433
 │    • schema + seed from db/init/*.sql  │
 │    • data kept in named volume pgdata  │
 └────────────────────────────────────────┘
```

## Run it

```bash
docker compose up --build -d
docker compose ps            # both containers should be "running" / "healthy"
```

Open **http://localhost:8000/docs**, then use **POST /upload** → *Try it out* → choose a file from `sample_data/`.

Or from the terminal:

```bash
curl -F "file=@sample_data/employees_good.csv"  http://localhost:8000/upload
curl -F "file=@sample_data/employees_messy.csv" "http://localhost:8000/upload?dry_run=true"
curl http://localhost:8000/summary
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Confirms the API can reach the database container |
| POST | `/upload?dry_run=` | Validate a CSV and load the clean rows (validation only when `dry_run=true`) |
| GET | `/employees?department=` | List the loaded employees |
| GET | `/summary` | Headcount and average hourly rate per department |
| GET | `/imports` | Upload history |

## Validation rules

Required columns · positive integer IDs · no duplicate IDs or emails in a file · valid email · department must exist (case-insensitive) · `YYYY-MM-DD` hire date that isn't in the future · hourly rate > 0 · an email can't be reused by a different employee already in the DB.

## Useful commands

```bash
docker compose logs -f api                      # follow API logs
docker exec -it onboarding-db psql -U onboard -d onboarding   # SQL shell inside the db container
docker compose restart db                       # data survives (named volume)
docker compose down                             # stop and remove containers, keep data
docker compose down -v                          # also delete the volume, so the schema is rebuilt
```
