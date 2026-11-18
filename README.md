# Jobify

Jobify is a Dockerized interactive job-application assistant. It reads the
single PDF placed in `master_cv`, creates Ollama embeddings for CV chunks, stores them in
PostgreSQL/pgvector, extracts search keywords, finds Tanitjobs postings, and
lets you select one job. It then generates a tailored RenderCV YAML file and
cover letter, renders and verifies the PDF, and asks for explicit approval
before sending an email.

## Use the app

Run these commands from:

```text
C:\Users\hamza\Desktop\Jobify UIT
```

### 1. Configure credentials

Copy the environment template and edit it:

```powershell
Copy-Item .env.example .env
notepad .env
```

Set `USER_EMAIL`, `EMAIL_APP_PASSWORD`, and
`POSTGRES_CONNECTION_STRING`. Never commit `.env` or put credentials in code.
Rotate any credentials that have previously been exposed.

Ensure Ollama is running on Windows and has DeepSeek-R1:

```powershell
ollama serve
ollama run deepseek-r1:7b
```

The app automatically tries to pull `nomic-embed-text` when it is missing.

Place exactly one PDF in the `master_cv` folder:

```text
master_cv\<your-cv-name>.pdf
```

The filename can be anything. Jobify stops with a clear error if the folder
contains zero PDFs or more than one PDF.

### 2. Start the supporting services

```powershell
docker compose up --build -d db rendercv
docker compose ps
```

### 3. Run one complete application workflow

```powershell
docker compose run --rm app
```

The application will:

1. Extract text from the master PDF.
2. Split it into overlapping chunks and create 768-dimensional Ollama
   embeddings.
3. Replace that CV's rows in `cv_chunks`.
4. Ask DeepSeek-R1 for job titles and technology keywords.
5. Ask you to select up to three extracted keywords.
6. Fetch up to five Tanitjobs postings for each selected keyword and display them.
7. Ask you to select one posting.
8. Retrieve the most relevant CV chunks with pgvector.
9. Generate and save `<job>-<company>-<date>.yaml` and `.txt` in `cv_data`.
10. Run RenderCV and verify the matching PDF.
11. Display the cover letter and ask whether to send it.

At the keyword prompt, enter up to three numbers separated by commas, for
example:

```text
Choose up to 3 keywords to search on Tanitjobs:
1. Software Engineer
2. Full Stack Developer
3. Backend Developer
4. React
Enter numbers separated by commas (for example 1,4,7), or q to quit: 1,3
```

Jobify performs a separate Tanitjobs search for each selected keyword and
fetches up to five postings per keyword. Duplicate postings are shown only
once.

If no recruiter email is found, the program asks you for one. Press Enter
without providing an address to keep all files local. Answer `y` only when you
want SMTP delivery.

### 4. Stop services

```powershell
docker compose down
```

This preserves the PostgreSQL volume. To intentionally reset the database:

```powershell
docker compose down -v
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama API reachable from Docker |
| `OLLAMA_MODEL` | `deepseek-r1:7b` | Local text-generation model |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | 768-dimensional embedding model |
| `OLLAMA_TIMEOUT_SECONDS` | `180` | Ollama request timeout |
| `POSTGRES_CONNECTION_STRING` | Compose PostgreSQL URL | Database connection |
| `MASTER_CV_DIR` | `/workspace/master_cv` | Folder containing exactly one input PDF |
| `CV_DATA_DIR` | `/app/cv_data` | Generated files |
| `SCRAPER_MAX_JOBS` | `10` | Maximum displayed jobs |
| `SCRAPER_JOBS_PER_KEYWORD` | `5` | Jobs fetched for each selected keyword |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | `587` | SMTP port |
| `RENDERCV_SERVICE` | `rendercv_service` | RenderCV container name |

## Services and storage

- `db` uses `pgvector/pgvector:pg16` and initializes `sql/001_init.sql`.
- `rendercv` is built from `rendercv/` and shares `cv_data` as `/app/data`.
- `app` mounts the Docker socket so it can invoke RenderCV in the running
  `rendercv_service` container.
- `cv_chunks` stores source chunks and vectors; `job_postings` stores scraped
  job metadata.
- Generated YAML, PDF, and cover-letter files are written to `cv_data/`.

The SQL initialization script runs only when PostgreSQL creates a new data
volume. Use `docker compose down -v` to recreate it.
