# Step 2 — Data Understanding

## 1. Data sources

| Source | Type | Purpose | Collection |
|---|---|---|---|
| `master_cv/*.pdf` | Private PDF | Candidate facts, skills and history | Local file read with `pypdf` |
| Tanitjobs search pages | Public HTML | Candidate job discovery | `requests` + BeautifulSoup |
| Tanitjobs job pages | Public HTML | Job descriptions and recruiter data | `requests` + BeautifulSoup |
| PostgreSQL/pgvector | Local database | Persistent chunks, embeddings and jobs | Application writes |

The master CV is not modified on disk. Its normalized extracted text is stored
as CV metadata, while the original PDF remains the source document.

## 2. Automated collection workflow

1. `find_master_cv()` requires exactly one PDF in the configured directory.
2. `extract_pdf_text()` reads all pages and normalizes PDF spacing.
3. `TanitjobsScraper.search()` requests one search phrase at a time.
4. Listing URLs are restricted to the Tanitjobs domain and `/job/` paths.
5. Job pages are parsed into title, company, location, description, email and
   posted date.
6. Jobs are deduplicated by their unique source URL in PostgreSQL.

## 3. Current observable exploration

The current CV ingestion run produced **7 chunks** using the configured
`CV_CHUNK_SIZE=1000` and `CV_CHUNK_OVERLAP=200` settings. The exact character
distribution should be exported during a reproducible exploration run because
the count depends on the active CV text.

The application stores the following job fields:

`title`, `company`, `location`, `description`, `recruiter_email`,
`posted_at`, `source_url`, and `scraped_at`.

The source code currently does not export the required exploration table.
Therefore missing-value rates, duplicate counts, and job-period distributions
must be measured from a saved collection before being reported as results.

## 4. Required charts

The final exploration notebook/report must include and comment on at least:

1. **Chunk-length distribution:** detects whether the 1000-character window
   creates very short or excessively long pieces.
2. **Job metadata completeness:** compares the proportion of postings with a
   company, location, recruiter email and posted date.

Interpretation to record:

- unusually short chunks may indicate PDF extraction or section-boundary
  problems;
- missing company or email values should not be replaced with invented data;
- duplicate URLs must be removed before retrieval or evaluation;
- a narrow posting period improves freshness but may reduce sample size.

## 5. Conclusions for Step 3

- PDF whitespace normalization is necessary before embeddings.
- Overlap is needed because CV evidence can cross chunk boundaries.
- Source name and chunk index must travel with every chunk.
- Job descriptions should be kept separate from CV chunks, then combined only
  at retrieval time.
- Empty company, location and recruiter fields must remain explicit missing
  values.
- Raw collection snapshots should be saved outside Git when they contain
  personal data or large HTML pages.

## 6. Status

**Implemented:** automated CV and job collection, URL deduplication, database
storage, and basic normalization.

**Missing for full assignment compliance:** a saved raw-data snapshot, an
automated exploration report, before/after statistics, and two rendered
commented charts.

