# Step 1 — Business Understanding

## 1. Business problem

Job seekers often have one broad master CV but need to apply to many jobs with
different requirements. Manually comparing every job description with the CV,
selecting relevant evidence, rewriting an application letter, and producing a
consistent PDF is slow and error-prone.

Jobify addresses this problem by helping a candidate:

1. ingest and preserve a master CV;
2. search relevant job listings;
3. retrieve CV evidence that matches a selected job;
4. generate a truthful, job-specific cover letter;
5. generate and validate a RenderCV document;
6. review the result before any email is sent.

## 2. Users and questions

The primary user is an individual job seeker. Typical questions include:

- Which current listings match my experience?
- Which parts of my CV support this SAP or software-engineering role?
- Which skills should be emphasized for this selected job?
- Can I produce a tailored cover letter without inventing experience?
- Can I obtain a valid PDF application package?

The system is not a recruiter-ranking system and does not make an employment
decision.

## 3. Why an LLM alone is insufficient

An LLM without retrieval may write a plausible but unsupported application. For
example, given a job requiring SAP FICO, it could claim that the candidate
implemented SAP FICO modules even when the CV only proves SAP ABAP and SAP BTP
experience. That answer sounds professional but is factually unsafe.

Jobify retrieves CV evidence before generation, instructs the model to use only
that evidence, and keeps PDF/schema validation in deterministic Python code.
The candidate still reviews the output before delivery.

## 4. Proposed architecture

```text
Master CV PDF ──► extract + normalize ──► chunks + embeddings ──► pgvector
                                                                    ▲
Tanitjobs search ──► selected job ──► job embedding ──► retrieve top-k chunks
                                                            │
                                                            ▼
                                                   Ollama generation
                                                     │          │
                                                     ▼          ▼
                                             cover letter   RenderCV YAML
                                                                  │
                                                                  ▼
                                                            Docker PDF
                                                                  │
                                                     human review + email approval
```

The current application is a human-in-the-loop, RAG-enabled workflow. The
Python program controls the sequence; the LLM does not yet independently
choose tools in an agentic loop.

## 5. Quantified success criteria

These are target thresholds to be measured in Step 5, not claimed results.

| Type | Criterion | Target |
|---|---|---:|
| Business | A user can produce a reviewed application package from one selected job | ≤ 5 minutes after job selection |
| Business | Displayed jobs are judged relevant by the candidate | ≥ 70% |
| Business | Generated factual claims are supported by the master CV | ≥ 90% |
| Business | RenderCV output is accepted and produces a non-empty PDF | ≥ 95% of valid inputs |
| Data mining | Relevant CV evidence appears in retrieved top-6 chunks | Hit@6 ≥ 0.80 |
| Data mining | Relevant evidence is ranked near the top | MRR ≥ 0.70 |
| Data mining | Generated applications contain usable source/evidence references | Citation support ≥ 90% |
| Data mining | Out-of-scope requests are refused instead of answered speculatively | ≥ 95% on a labelled test set |

## 6. Constraints and risks

- **Copyright and scraping:** only public job pages should be collected; rate
  limits and site terms must be respected.
- **Privacy:** the CV contains personal data. It is processed locally and must
  not be committed to Git or uploaded to an external provider.
- **Bias:** search and semantic similarity may favor certain wording, roles,
  languages, or employers.
- **Hallucination:** the local model may invent facts; retrieval and human
  review reduce but do not eliminate this risk.
- **Freshness:** job listings change and may expire; the database records the
  source URL and scraping time.
- **Cost and hardware:** local Ollama avoids API cost but increases latency and
  limits model size.
- **Email safety:** sending an application is an external action, so Jobify
  requires explicit user approval.

