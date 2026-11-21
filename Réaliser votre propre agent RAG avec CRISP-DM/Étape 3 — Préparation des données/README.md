# Step 3 — Data Preparation

The preparation pipeline is described using the five names required by the
assignment.

## 1. Selection

- Select the single configured master CV PDF.
- Select job pages from the Tanitjobs domain and paths beginning with `/job/`.
- Select only non-empty CV chunks and job descriptions.
- Retrieve the configured top `RETRIEVAL_LIMIT` chunks for the selected job.

## 2. Cleaning

`normalize_spaced_pdf_text()` removes artificial character spacing introduced by
PDF extraction, converts non-breaking spaces, and collapses repeated
whitespace. Job pages are parsed to text with BeautifulSoup. Empty or malformed
listings are skipped with an explicit warning.

Cleaning must not invent missing company, location, email, date, or experience
values.

## 3. Construction

`chunk_text()` converts normalized CV text into overlapping windows:

```text
chunk size = 1000 characters
overlap    = 200 characters
```

The overlap reduces the chance that a relevant fact is split at a boundary.
Each chunk is embedded with `nomic-embed-text`, producing a 768-dimensional
vector.

## 4. Integration

The selected job description is embedded with the same embedding model and
compared with CV chunk vectors in PostgreSQL/pgvector. The retrieved evidence is
then inserted into the Ollama prompt. The full CV metadata remains available
for identity and complete RenderCV construction.

## 5. Formatting

Prepared records are stored in:

- `cv_chunks(source_name, chunk_index, content, embedding, created_at)`;
- `cv_metadata(source_name, cv_text, keywords_json, chunk_count, updated_at)`;
- `job_postings(source_url, title, company, location, description, ...)`.

RenderCV data is normalized before YAML serialization so unsupported sections,
invalid dates, invalid phone values, and unsupported social-network labels are
removed or converted.

## Chunk metadata requirement

The database schema preserves `source_name` and `chunk_index` for every chunk.
This enables traceability to the master CV. The current generated cover letter
does not expose those identifiers as citations, so source citation remains a
Step 5/6 improvement.

## Before/after statistics to collect

| Measure | Before cleaning | After cleaning | Reason |
|---|---:|---:|---|
| CV characters | Run-time value | Run-time value | Detect extraction loss |
| CV chunks | Not applicable | Run-time value | Measure chunking |
| Empty job descriptions | Run-time value | 0 accepted | Reject unusable listings |
| Duplicate job URLs | Run-time value | 0 stored duplicates | Unique URL constraint |
| Malformed listings | Run-time value | Excluded | Prevent invalid retrieval |

These values must be generated from a collection run; placeholders are
deliberately not presented as measured results.

