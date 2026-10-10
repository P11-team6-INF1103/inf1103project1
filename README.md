# Workplace Safety Incident Triage System

INF1103 Team 6, Project Part 1. A terminal app for construction-site supervisors. A supervisor
logs an incident, the app asks AI for supporting evidence, fixed business rules judge how
serious it is, and the result is saved so Workplace Safety & Health officers can review the
worst incidents first. The AI gathers evidence; it does not make the final call.

## How it works

```
user -> io_manager -> ai_manager -> logic_manager -> data_manager
```

| Module | Job |
|---|---|
| `io_manager.py` | All terminal input and output, with validation. The only file that prints. |
| `ai_manager.py` | Builds prompts, calls Gemini (hazard flags, review), Groq (web search) and the weather API, validates every reply against a schema, and never crashes on an API failure. No business rules. |
| `logic_manager.py` | Scores severity and applies the rules: stop-work review, systemic escalation, log only, or pending review. |
| `data_manager.py` | Saves and loads incidents as JSON in `data/`, and queries them by location. |
| `main.py` | Wires the four modules together. |

Outcome rules:
1. Severity 4 or above, or an injury with high recurrence likelihood: stop-work review.
2. The same location with 3 or more earlier incidents in 30 days: systemic escalation.
3. Otherwise: log only.
4. If the AI could not assess the incident: pending review (a person must look at it).

## Setup

You need Python 3.11 or newer.

```bash
pip install -r library.txt
cp .env.example .env
```

Put your own `GEMINI_API_KEY` and `GROQ_API_KEY` in `.env`. Never commit `.env`.
Without keys the app still runs, but every incident is sent to pending review.

## Run

```bash
python main.py                          # interactive menu
python main.py --batch incidents.json   # process a JSON list of incidents and exit
```

A batch file is a JSON list of objects with `description`, `location`, `reporter_role`,
`injury` (true/false) and an optional ISO 8601 `timestamp`.

Incidents are saved to `data/incidents.json`. Set `INCIDENT_DATA_DIR` to use another folder.

## Run the tests

```bash
pip install pytest ruff
pytest tests/
ruff check .
```

## Run with Docker

```bash
docker build -t inf1103project1 .
docker run -it --env-file .env -v "$(pwd)/data:/app/data" inf1103project1
```

`.env` is kept out of the image by `.dockerignore`; the keys are passed in at run time.
The `-v` option keeps saved incidents on your machine between runs.

## Published image

Every merge to `main` publishes an image to GitHub Container Registry:

```bash
docker pull ghcr.io/p11-team6-inf1103/inf1103-p-11team6:latest
docker run -it --env-file .env ghcr.io/p11-team6-inf1103/inf1103-p-11team6:latest
```
