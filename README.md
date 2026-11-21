# Jobify

Jobify is a Dockerized, human-in-the-loop job-application assistant. It reads
one master CV PDF, stores searchable CV chunks in PostgreSQL/pgvector, finds
public Tanitjobs listings, retrieves CV evidence for a selected job, and asks
local Ollama to generate both a tailored cover letter and a tailored RenderCV
YAML CV. The YAML is normalized, rendered to PDF in a separate RenderCV
container, and shown to the user before optional email delivery.

The current text model is `qwen3.5:4b`. Thinking is disabled for structured
generation, with low temperature and an 8192-token context. Cover-letter and
RenderCV YAML generation are deliberately separate Ollama requests.

## Project layout

```text
app/
  __main__.py       interactive workflow and orchestration
  config.py         environment-backed immutable settings
  cv_ingest.py      PDF extraction, normalization and chunking
  database.py       PostgreSQL/pgvector persistence and retrieval
  emailer.py        SMTP delivery with PDF attachment
  ollama_client.py  embeddings, role extraction and two generation requests
  rendercv.py       YAML normalization and Docker RenderCV execution
  scraper.py        Tanitjobs HTTP collection and parsing
sql/001_init.sql    PostgreSQL schema and pgvector index
master_cv/          exactly one input CV PDF
cv_data/            generated YAML, TXT and PDF files
rendercv/           RenderCV service image
docker-compose.yml  db, rendercv and app services
```

For the detailed technical call graph, database explanation, file-by-file
responsibilities, and every `.env` parameter, see
[TECHNICAL_WORKFLOW.md](TECHNICAL_WORKFLOW.md).

## Prerequisites

- Docker Desktop with Compose.
- Ollama running on Windows and reachable from Docker.
- The configured Ollama generation model and embedding model.
- One text-readable PDF in `master_cv`.

The application automatically pulls a missing Ollama model through
`/api/pull`, but pulling explicitly gives better visibility:

```powershell
ollama serve
ollama pull qwen3.5:4b
ollama pull nomic-embed-text
```

## Configure

Copy the template if needed:

```powershell
Copy-Item .env.example .env
notepad .env
```

Set the private values `USER_EMAIL`, `EMAIL_APP_PASSWORD`, and
`POSTGRES_CONNECTION_STRING`. Never commit `.env`, credentials, CV PDFs, or
generated application files.

The application loads `.env` on the host-side project and Docker Compose passes
selected values into the `app` container. Explicit values in `.env` override
Compose `${NAME:-default}` values. For example, the Compose fallback for
`CV_CHUNK_SIZE` is `1800`, but the current `.env` sets it to `1000`.

## Run the complete workflow

From:

```text
C:\Users\hamza\Desktop\Jobify UIT
```

Start the database and persistent RenderCV service:

```powershell
docker compose up --build -d db rendercv
docker compose ps
```

Run the interactive application:

```powershell
docker compose run --rm app
```

The program then performs this high-level sequence:

1. Find exactly one PDF in `/workspace/master_cv`.
2. Connect to Ollama and ensure the generation and embedding models exist.
3. Connect to PostgreSQL and show stored CV sources.
4. Either re-ingest the PDF or reuse stored CV metadata/chunks.
5. Extract role keywords with Ollama.
6. Ask the user to select up to three search keywords.
7. Fetch and parse Tanitjobs listings for each selected keyword.
8. Deduplicate listings by URL and save them in `job_postings`.
9. Ask the user to select one job.
10. Embed the job description and retrieve the closest CV chunks.
11. Send one request for the cover letter and a second request for the tailored
    RenderCV YAML.
12. Normalize and save the YAML and cover letter in `cv_data`.
13. Execute RenderCV in the `rendercv_service` container and verify the PDF.
14. Ask for a recipient and explicit `y`/`yes` confirmation before SMTP send.

At the keyword prompt, enter comma-separated numbers, for example:

```text
Enter numbers separated by commas (for example 1,4,7), or q to quit: 1,3
```

To keep the generated files local, press Enter when no recruiter email is
found. Only answer `y` or `yes` to the final send confirmation when delivery is
intended.

## Stop and reset

```powershell
docker compose down
```

This keeps the PostgreSQL named volume. To intentionally delete the database
volume and recreate the schema:

```powershell
docker compose down -v
```

Generated files remain in `cv_data` unless removed separately.

## Configuration summary

| Variable | Current/default value | Controls |
|---|---|---|
| `USER_EMAIL` | empty | SMTP sender address |
| `EMAIL_APP_PASSWORD` | empty | SMTP app password; never document the value |
| `POSTGRES_CONNECTION_STRING` | Compose PostgreSQL URL | Database host, database, user and password |
| `TANITJOBS_BASE_URL` | `https://www.tanitjobs.com` | Stored setting; currently not read by the scraper |
| `TANITJOBS_SEARCH_URL` | `https://www.tanitjobs.com/jobs/` | Listing search endpoint |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama endpoint from the app container |
| `OLLAMA_MODEL` | `qwen3.5:4b` | Text generation and structured JSON model |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | 768-dimensional embedding model |
| `OLLAMA_TIMEOUT_SECONDS` | `180` | Timeout for Ollama HTTP calls |
| `CV_CHUNK_SIZE` | `1000` in current `.env` | Maximum normalized CV chunk size in characters |
| `CV_CHUNK_OVERLAP` | `200` in current `.env` | Characters repeated between adjacent chunks |
| `RETRIEVAL_LIMIT` | `6` | Number of nearest CV chunks supplied to generation |
| `MASTER_CV_DIR` | `/workspace/master_cv` | Mounted directory containing exactly one PDF |
| `CV_DATA_DIR` | `/app/cv_data` | Shared generated YAML, TXT and PDF directory |
| `SCRAPER_TIMEOUT_SECONDS` | `20` | HTTP timeout per Tanitjobs request |
| `SCRAPER_MAX_JOBS` | `5` in current `.env` and Compose | General scraper default; the interactive path uses the per-keyword limit |
| `SCRAPER_JOBS_PER_KEYWORD` | `5` | Maximum postings collected for each selected keyword |
| `SCRAPER_VERIFY_TLS` | `false` in current `.env` | Present in `.env`, but not currently read by `Settings` or `scraper.py` |
| `SCRAPER_CA_BUNDLE_PATH` | empty | Present in `.env`, but not currently read by `Settings` or `scraper.py` |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | `587` | SMTP submission port |
| `RENDERCV_SERVICE` | `rendercv_service` | Container name searched by the Docker SDK |
| `DOCKER_COMPOSE_PROJECT_DIR` | `/workspace` | Retained workflow setting; currently unused by Docker SDK rendering |

`TANITJOBS_BASE_URL`, `SCRAPER_VERIFY_TLS`, and `SCRAPER_CA_BUNDLE_PATH` are
documented as currently inactive configuration entries, not as working
controls. The scraper derives its allowed hostname from
`TANITJOBS_SEARCH_URL` and calls `requests.Session.get()` without passing TLS
options.

## Services and storage

- `db` uses `pgvector/pgvector:pg16`, initializes `sql/001_init.sql`, and
  persists data in the `postgres_data` named volume.
- `rendercv` is built from `rendercv/`, stays alive for Docker SDK `exec_run`,
  and mounts host `cv_data` as `/app/data`.
- `app` mounts the master CV read-only, shares `cv_data`, mounts the Docker
  socket, and uses `host.docker.internal` to reach Windows Ollama.
- PostgreSQL stores CV chunks/vectors, CV metadata, and scraped job postings.
- Host `cv_data` stores generated YAML, cover letters, and PDFs.

The SQL initialization mount runs only when PostgreSQL creates a new volume.

## CRISP-DM documentation

The assignment documentation is in
[Réaliser votre propre agent RAG avec CRISP-DM](Réaliser%20votre%20propre%20agent%20RAG%20avec%20CRISP-DM/README.md).
