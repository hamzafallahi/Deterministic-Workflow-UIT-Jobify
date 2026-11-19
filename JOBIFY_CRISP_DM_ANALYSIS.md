# Jobify: Architecture, Workflow, and CRISP-DM Analysis

This document explains what Jobify currently does, how its files work together,
how the RAG pipeline is used, and how the implementation compares with the
teacher's CRISP-DM/RAG-agent requirements.

## 1. Short answer: is Jobify an agent?

Jobify is best described academically as a **human-in-the-loop, RAG-enabled
agentic workflow**.

It has several agent characteristics:

- It perceives information from a CV PDF and live job listings.
- It stores long-term semantic memory in PostgreSQL/pgvector.
- It retrieves relevant CV evidence for a selected job.
- It uses an LLM to extract roles and write a cover letter.
- It acts on the outside world by scraping, rendering a PDF, and optionally
  sending an email.
- It asks the user for decisions at important points.

However, it is not yet a fully autonomous agent like the teacher's news
reference project. The Python program currently controls the sequence:

```text
choose CV -> choose roles -> scrape jobs -> choose job -> retrieve -> generate
-> render -> ask permission -> email
```

The LLM does not independently select tools in a loop, observe tool results,
re-plan, or evaluate its own answer. The user and `app/__main__.py` are the
controller. Therefore, the most accurate presentation wording is:

> Jobify is a modular RAG system exposed through an interactive agentic
> workflow. It uses deterministic Python tools, local LLM reasoning, semantic
> memory, and human approval for consequential actions.

That is a defensible scope for the hardware available. A GTX 1660 Super is not
well suited to running both a large planning model and a separate large worker
model. A small local model plus deterministic tools is a sensible engineering
trade-off, provided the missing agent and evaluation requirements are clearly
identified.

## 2. What the current application does

Given a CV PDF and a running Ollama/PostgreSQL/RenderCV environment, Jobify:

1. Finds the active PDF in `master_cv`.
2. Lets the user reuse a CV already stored in the database or re-ingest the PDF.
3. Extracts and normalizes PDF text.
4. Splits the text into overlapping chunks.
5. Creates a 768-dimensional embedding for every chunk with
   `nomic-embed-text`.
6. Stores the chunks and vectors in PostgreSQL/pgvector.
7. Extracts target job titles with `deepseek-r1:7b`.
8. Lets the user choose up to three search titles.
9. Searches Tanitjobs for each selected title.
10. Downloads and parses individual job pages.
11. Lets the user select one job.
12. Embeds the selected job description and performs cosine-similarity
    retrieval against the stored CV chunks.
13. Sends the retrieved evidence to DeepSeek to generate a cover letter.
14. Builds the RenderCV YAML deterministically from the full CV profile.
15. Saves the YAML and cover letter in `cv_data`.
16. Invokes the RenderCV container and verifies the PDF.
17. Displays the letter and asks for explicit permission before SMTP delivery.

The important design change is that the LLM no longer generates the complete
CV YAML. The deterministic parser builds the profile, while the LLM is used
for role extraction and the cover letter. This prevents hallucinated phone
numbers, invalid education fields, unsupported RenderCV sections, and invented
experience from degrading the CV.

## 3. File responsibilities and call graph

### Entry point

[`app/__main__.py`](app/__main__.py) is the application orchestrator. It
imports the other modules and controls the interactive workflow.

Its main calls are:

```text
main()
├── settings from app/config.py
├── find_master_cv() / extract_pdf_text() / chunk_text()
│   └── app/cv_ingest.py
├── OllamaClient(...)
│   └── app/ollama_client.py
├── Database(...)
│   └── app/database.py
├── _choose_cv()
│   └── list_cv_sources(), get_cv_metadata(), get_source_chunks()
├── ollama.embed() / ollama.extract_keywords()
├── TanitjobsScraper.search()
│   └── app/scraper.py
├── database.save_jobs()
├── database.retrieve_chunks(ollama.embed(job.description), k)
├── ollama.generate_application()
├── build_cv_profile() / build_rendercv_yaml()
│   └── app/cv_ingest.py
├── save_yaml() / render_yaml()
│   └── app/rendercv.py
└── send_application()
    └── app/emailer.py
```

### Configuration

[`app/config.py`](app/config.py) loads `.env` and exposes one immutable
`Settings` object. It contains model names, URLs, timeouts, database settings,
directories, chunking values, retrieval size, SMTP values, and the RenderCV
service name.

This avoids scattering magic values through the application. For example:

- `CV_CHUNK_SIZE=1000`
- `CV_CHUNK_OVERLAP=200`
- `RETRIEVAL_LIMIT=6`
- `OLLAMA_MODEL=deepseek-r1:7b`
- `OLLAMA_EMBEDDING_MODEL=nomic-embed-text`

Credentials must remain in `.env`, never in Python or documentation.

## 4. CV ingestion in detail

### 4.1 Finding and reading the PDF

`find_master_cv()` searches the configured `MASTER_CV_DIR` and currently
requires exactly one PDF. `extract_pdf_text()` uses `pypdf.PdfReader` and
concatenates the extracted text from all pages.

This is text extraction, not OCR. A scanned image-only PDF will fail unless an
OCR stage is added.

### 4.2 PDF text normalization

PDF extraction does not always preserve normal words. Some PDFs produce output
such as:

```text
S o f t w a r e   E n g i n e e r
```

`normalize_spaced_pdf_text()` detects lines containing a high proportion of
single-character tokens and removes artificial spaces. It also:

- converts non-breaking spaces;
- collapses repeated whitespace;
- preserves line boundaries where possible.

This normalization is needed because embeddings and regular expressions work
far better on `Software Engineer` than on character-separated PDF output.

### 4.3 Chunking

`chunk_text()` first creates a normalized one-line representation, then uses a
sliding window:

```text
chunk size: 1000 characters
overlap:     200 characters
```

The overlap prevents important facts at a boundary from being split into
separate, unrelated pieces. The current settings normally produce seven
chunks for the original CV, although the exact count depends on document
length.

The application also upgrades older stored CVs if their chunk count differs
from the current chunking result. It re-embeds the upgraded chunks rather than
silently using an obsolete index.

### 4.4 Profile construction

`build_cv_profile()` is deliberately deterministic. It extracts:

- name and contact details;
- Tunisian phone numbers;
- email, LinkedIn, GitHub, and website;
- summary;
- skills;
- education;
- professional experience;
- projects.

The phone logic accepts eight local Tunisian digits or `+216` followed by
eight digits. It formats the local number as `+216 XX XXX XXX`. This is why a
number such as `50909086` can become `+216 50 909 086`, while an invented
nine-digit value is discarded.

The parser is currently heuristic. It is reliable for the known CV layouts but
is not a universal parser for every PDF design. Multi-column layouts,
unusual headings, and scanned documents remain limitations.

## 5. Ollama and LLM responsibilities

[`app/ollama_client.py`](app/ollama_client.py) uses two local Ollama models:

| Purpose | Model |
|---|---|
| Text generation | `deepseek-r1:7b` |
| Embeddings | `nomic-embed-text` |

### Role extraction

`extract_keywords()` asks DeepSeek for concise target job titles rather than
technologies. The result is normalized and filtered so that values such as
`React`, `Docker`, or `PostgreSQL` do not become job-search roles.

The prompt supports multiple domains, including software, law, education,
training, business, and human resources. This is important because a CV does
not have to be an IT CV.

### Cover-letter generation

`generate_application()` receives:

- the selected job title, company, location, description, and URL;
- the top retrieved CV chunks.

The prompt tells DeepSeek to use only supplied evidence and not invent
employers, degrees, dates, projects, or skills. JSON schema constraints,
bounded context, low temperature, repeat penalties, and retries reduce the
malformed-output problem seen with DeepSeek-R1.

The model generates the cover letter only. It does not generate the final CV
structure.

## 6. Database and data schema

PostgreSQL is used for durable storage and pgvector for semantic retrieval.
The schema is initialized by [`sql/001_init.sql`](sql/001_init.sql).

### `cv_chunks`

```text
id           BIGSERIAL primary key
source_name  source PDF name
chunk_index  order within that CV
content      normalized chunk text
embedding    vector(768)
created_at   insertion time
```

`UNIQUE(source_name, chunk_index)` prevents duplicate positions for the same
source. The HNSW cosine index accelerates nearest-neighbor retrieval.

### `cv_metadata`

```text
source_name   primary key
cv_text       complete normalized CV text
keywords_json extracted job titles
chunk_count   current number of chunks
updated_at    last update time
```

This table enables the stored-CV selection menu. Reusing a CV avoids reading
the PDF and recreating embeddings on every run. The complete text is retained
because deterministic profile construction needs more than the small set of
chunks retrieved for a particular job.

### `job_postings`

```text
source_url      unique Tanitjobs URL
title           job title
company         company, if found
location        location, if found
description     parsed job description
recruiter_email discovered email, if any
posted_at       scraped date text, if any
scraped_at      database insertion time
```

This gives the workflow a durable record of scraped jobs and supports
deduplication by URL.

### Why two kinds of CV storage?

`cv_chunks` is optimized for semantic search. `cv_metadata` is optimized for
remembering the original normalized CV and its extracted role menu. Keeping
both avoids reconstructing the profile from only the top six chunks and makes
CV reuse fast.

## 7. RAG flow: is RAG actually used?

Yes. The retrieval step is in the active application path:

```text
selected job description
        |
        v
ollama.embed(job.description)
        |
        v
Database.retrieve_chunks(vector, RETRIEVAL_LIMIT)
        |
        v
PostgreSQL: ORDER BY embedding <=> query_vector LIMIT 6
        |
        v
relevant CV chunks
        |
        v
ollama.generate_application(job, relevant_chunks)
        |
        v
cover letter
```

This is a classic `Retrieve -> Augment -> Generate` chain:

- **Retrieve:** pgvector finds CV chunks closest to the job description.
- **Augment:** those chunks are inserted into the cover-letter prompt.
- **Generate:** DeepSeek writes a letter grounded in that context.

The deterministic RenderCV YAML is intentionally built from the full stored CV
profile, not only retrieved chunks. This is not a failure of RAG: retrieval
is used for the job-specific letter, while the complete factual CV is used to
avoid deleting unrelated but valid CV sections.

The current system does not return chunk IDs or source citations in the cover
letter. That is acceptable for an application letter but is a gap relative to
the teacher's news-agent requirement that answers cite sources.

## 8. How the Tanitjobs scraper works

[`app/scraper.py`](app/scraper.py) is a custom HTTP scraper using `requests` and
BeautifulSoup. It does not use browser automation.

For each selected role it:

1. Sends a GET request to the configured Tanitjobs jobs endpoint.
2. Uses `keywords[all_words]` and other search parameters.
3. Extracts same-domain links whose path begins with `/job/`.
4. Downloads candidate job pages.
5. Extracts title, description, company, location, and posted date.
6. Searches page text for recruiter email addresses.
7. Applies role-specific relevance filtering.
8. Returns at most the configured number of postings.

The main workflow runs one search per selected keyword, merges the results, and
deduplicates them by URL. The scraper handles request failures, HTTP 429,
malformed listings, and timeouts with explicit errors or logged skips.

The scraper is a tool in the software architecture, but it is not currently a
tool selected by the LLM. The Python workflow calls it directly.

## 9. RenderCV generation and the previous failures

`build_rendercv_yaml()` constructs a RenderCV data structure from the
deterministic profile. `save_yaml()` then calls
`normalize_rendercv_data()` before writing YAML.

RenderCV normalization:

- removes unsupported top-level `design` data from the CV object and supplies a
  supported design;
- converts accidental singular `section` to plural `sections`;
- removes unknown CV keys;
- allowlists supported sections: `education`, `experience`, `projects`, and
  `skills`;
- removes malformed entries;
- ensures education has required `institution` and `area`;
- converts dates such as `September 2022` to accepted ISO-like values;
- validates and formats the phone number;
- removes unsupported `publications` entries when they do not satisfy the
  RenderCV schema.

`render_yaml()` uses the Docker SDK to execute RenderCV in the running
`rendercv_service` container, then verifies that a PDF was produced in the
shared `cv_data` directory.

The earlier intermittent errors were not random. They came from the LLM
producing different invalid YAML structures on different prompts:

- missing education fields;
- natural-language dates;
- missing publication authors;
- invalid phone numbers;
- singular `section`;
- unsupported `design` or section structures.

Moving CV construction from the LLM to deterministic code addresses the root
cause instead of trying to repair every possible hallucinated YAML shape.

## 10. Email flow and safety

`app/emailer.py` uses `smtplib` and attaches the verified PDF. The workflow:

1. Uses an email found on the job page if available.
2. Otherwise asks the user for an address.
3. Saves locally if the user presses Enter without an address.
4. Shows the recipient and asks for explicit confirmation.
5. Sends only after `y` or `yes`.

This human approval step is important because email is an external,
potentially irreversible action.

## 11. CRISP-DM comparison

### Step 1 — Business understanding

**Implemented partially.**

The practical problem is clear: help a job seeker find relevant listings and
prepare a truthful, tailored application package. The user, job-selection
interaction, and email-approval interaction are clear.

Still needed for full compliance:

- a dedicated business-understanding document;
- at least four quantified success criteria;
- explicit business and data-mining thresholds;
- documented risks such as privacy, bias, scraping legality, model cost,
  freshness, and hallucination.

Example criteria that could be added:

| Criterion | Example threshold |
|---|---:|
| CV text extraction coverage | at least 95% of manually visible text |
| Retrieval relevance | Hit@6 at least 0.80 on an annotated test set |
| Letter factuality | at least 90% of checked claims supported by the CV |
| Job-search usefulness | at least 70% of displayed jobs judged relevant |

These are examples, not measured results. They must be evaluated rather than
claimed.

### Step 2 — Data understanding

**Implemented only as runtime ingestion.**

Jobify collects two data types: private CV PDFs and public Tanitjobs pages.
It currently does not provide the required exploration report, raw-data
archive, missing-value analysis, duplicate analysis, period analysis, or two
commented charts.

A compliant submission should add a report showing:

- number of CV pages and extracted characters;
- number of chunks and chunk-length distribution;
- number of jobs per query;
- missing company/location/email rates;
- duplicate URL count;
- examples of scraper failures;
- at least two charts.

Private CVs should not be included in the submitted ZIP without consent.

### Step 3 — Data preparation

**Implemented technically, but not documented in the required structure.**

The code performs the five requested ideas:

1. **Selection:** selects the active CV and relevant job pages.
2. **Cleaning:** normalizes PDF whitespace and job-page text.
3. **Construction:** builds chunks, embeddings, and deterministic profiles.
4. **Integration:** combines CV evidence with job descriptions.
5. **Formatting:** stores vectors and creates RenderCV-compatible structures.

The seven-chunk behavior is a consequence of the current 1000/200 settings,
not a universal guarantee. Chunk metadata includes source name and index in the
database, but the generated letter does not expose that metadata as citations.

Still needed:

- before/after statistics;
- a written justification based on exploration;
- a separate preparation report;
- a systematic comparison of chunking choices.

### Step 4 — Modeling

**The core RAG model is implemented.**

Jobify has:

- an embedding model;
- a pgvector index;
- a retrieval function;
- a configurable `k` value (`RETRIEVAL_LIMIT`);
- a Retrieve -> Augment -> Generate chain;
- an LLM prompt designed to reduce unsupported claims.

The choices are reasonable for a local machine:

- `nomic-embed-text` provides 768-dimensional vectors;
- pgvector avoids a second vector database;
- HNSW provides an efficient approximate index;
- DeepSeek-R1:7b is usable locally, although slow and less reliable than a
  larger hosted model.

Still needed:

- measured justification for embedding/model choices;
- retrieval experiments;
- source-aware answer formatting if citations are required.

### Step 5 — Evaluation

**This is the largest current academic gap.**

The application has operational error handling but not a reproducible
evaluation stage. It lacks:

- a saved test set of at least 15 manually written questions;
- a classic baseline;
- Hit@k;
- MRR;
- citation and faithfulness measurements;
- automated success-criterion checks;
- three logged experiments with controlled changes.

The assignment is not complete academically until the system is measured.
Successful interactive runs prove functionality, not retrieval quality or
factuality.

A suitable Jobify evaluation set could contain:

- job descriptions with manually marked relevant CV chunks;
- questions such as “Which experience matches this Python backend role?”;
- expected evidence spans;
- expected roles and skills;
- deliberately out-of-scope jobs.

The baseline could be keyword matching over the full CV. Compare it with
pgvector retrieval while changing only one variable at a time:

1. chunk size 500 vs 1000 vs 1500;
2. overlap 0 vs 100 vs 200;
3. embedding model A vs embedding model B.

### Step 6 — Deployment

**Implemented as a usable deployment, but not yet equivalent to the reference
agent.**

Implemented:

- Dockerized services;
- terminal interface;
- persistent database;
- local LLM;
- scraper, retrieval, rendering, and email capabilities;
- explicit human approval.

Missing relative to the guide:

- an LLM-controlled agentic loop;
- at least two tools exposed through tool descriptions to the LLM;
- a system prompt enforcing source-only answers and citations;
- the five required demonstration cases:
  1. no tool;
  2. RAG tool;
  3. follow-up using memory;
  4. second tool;
  5. out-of-scope question;
- at least eight pytest tests.

## 12. Reference architecture versus Jobify

The teacher's reference project separates code by CRISP-DM step:

```text
etape2_donnees/
etape3_preparation/
etape4_modelisation/
etape5_evaluation/
etape6_deploiement/
tests/
docs/
app/
```

Jobify currently uses a smaller production-oriented layout:

```text
app/
├── config.py
├── cv_ingest.py
├── database.py
├── emailer.py
├── ollama_client.py
├── rendercv.py
├── scraper.py
└── __main__.py
sql/
docker-compose.yml
Dockerfile
README.md
```

The current layout is modular and understandable, but it does not mirror the
reference directory structure or provide one artifact per CRISP-DM step. For
the exam, documentation folders can be added without forcing all runtime code
into a new structure.

## 13. Recommended completion plan

The highest-value additions, in order, are:

1. Add `docs/1_comprehension_metier.md` with the problem, users, risks, and
   four measured success criteria.
2. Add a data-understanding report with raw-data handling, statistics, and two
   charts.
3. Add a preparation report explaining the five preparation sub-steps and
   chunking experiments.
4. Add a reproducible evaluation dataset and scripts for Hit@k, MRR,
   citation support, and faithfulness.
5. Add at least eight pytest tests, including mocked Ollama calls.
6. Add a small tool-calling agent layer with at least two tools:
   `search_cv(question)` and `search_jobs(role)`.
7. Add a source-only system prompt and an out-of-scope response policy.
8. Demonstrate the five required agent interactions.
9. Improve `find_master_cv()` so stored-CV reuse can work even when no current
   PDF is present.
10. Keep the current deterministic RenderCV builder as the safety boundary.

## 14. Suggested presentation explanation

A concise oral explanation can be:

> Jobify solves a job-application problem using CRISP-DM principles. It
> ingests a CV, cleans and chunks it, creates embeddings, stores them in
> pgvector, retrieves evidence against a selected Tanitjobs description, and
> uses a local LLM to write a grounded cover letter. Deterministic Python code
> builds and validates the CV because free local LLM output is not reliable
> enough for strict RenderCV schemas. The terminal program is currently a
> human-in-the-loop agentic workflow rather than a fully autonomous
> tool-calling loop. Its main remaining academic weaknesses are formal
> exploration, evaluation, experiments, tests, and an LLM-controlled agent
> interface.

This framing is honest, technically accurate, and demonstrates awareness of
the difference between a RAG pipeline, a workflow, and an autonomous agent.
