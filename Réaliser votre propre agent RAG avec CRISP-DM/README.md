# Jobify — Building Your Own RAG Agent with CRISP-DM

This folder documents Jobify according to the six CRISP-DM steps required in
the student guide. The documentation is written in English, while the folder
names follow the assignment wording.

Jobify is a local, human-in-the-loop job application assistant. It reads a
master CV, searches public job listings on Tanitjobs, retrieves CV evidence
with PostgreSQL/pgvector, and generates a tailored cover letter and RenderCV
document with a local Ollama model.

## Deliverables

| Step | Folder | Status |
|---|---|---|
| 1 | `Étape 1 — Compréhension du métier` | Business scope and measurable criteria |
| 2 | `Étape 2 — Compréhension des données` | Data sources, collection, exploration plan and current observations |
| 3 | `Étape 3 — Préparation des données` | Five preparation sub-steps, chunking and metadata design |
| 4 | `Étape 4 — Modélisation` | Embeddings, vector retrieval and RAG architecture |
| 5 | `Étape 5 — Évaluation` | Test set, metrics, baseline and experiment log |
| 6 | `Étape 6 — Déploiement` | Current deployment, agent gap analysis and five-case demonstration |

## Important academic distinction

The current Jobify implementation already contains a working CV-to-job RAG
workflow, but it does not yet satisfy every reference-project requirement.
The documents therefore distinguish:

- **Implemented:** supported directly by the current source code;
- **Partial:** present in the workflow but not yet measured or formalized;
- **Missing:** required work that still needs implementation or evidence.

No unmeasured score is presented as a result. This is intentional: a successful
interactive run proves functionality, not retrieval quality or factuality.

For the implementation-level workflow, call graph, database schema, file
responsibilities, Docker topology, and environment parameters, see the
repository [technical workflow](../TECHNICAL_WORKFLOW.md).

## Source evidence

The analysis is based on:

- `app/cv_ingest.py`
- `app/database.py`
- `app/ollama_client.py`
- `app/scraper.py`
- `app/rendercv.py`
- `app/__main__.py`
- `app/config.py`
- `sql/001_init.sql`
- `JOBIFY_CRISP_DM_ANALYSIS.md`
