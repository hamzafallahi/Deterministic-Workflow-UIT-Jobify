# Step 6 — Deployment

## 1. Current deployment

Jobify is deployed as Docker services:

- `app`: interactive Python workflow;
- `db`: PostgreSQL with pgvector;
- `rendercv`: isolated PDF rendering service.

The terminal interface lets the user choose a CV, search roles, select a job,
review generated files, render a PDF, and approve email delivery.

## 2. Current tools

The workflow contains deterministic capabilities equivalent to tools:

| Capability | Current implementation |
|---|---|
| Search jobs | `TanitjobsScraper.search()` |
| Retrieve CV evidence | `Database.retrieve_chunks()` |
| Render CV | `render_yaml()` |
| Send application | `send_application()` after explicit approval |

However, these capabilities are called by Python in a fixed sequence. The LLM
does not yet select tools, observe tool results, and loop until it can answer.
Therefore the honest classification is **human-in-the-loop agentic workflow**,
not a complete autonomous tool-calling agent.

## 3. Required agent design

The next implementation should expose at least these two tools to the model:

```text
search_cv(question, k)
  Search the indexed master CV and return matching chunks with source name,
  chunk index, and similarity score. Use for questions about the candidate.

search_jobs(role)
  Search public Tanitjobs listings for a role and return title, company,
  location, description, and source URL. Use for job discovery.
```

The tool descriptions must be explicit because they are the only information
the LLM uses to decide whether to call a tool.

## 4. Required system prompt

```text
You are Jobify, a grounded job-application assistant.
Use tools when the user asks about CV evidence or current job listings.
Answer only from tool results and supplied conversation context.
Never invent employers, degrees, dates, skills, job details, or contact data.
Cite the source name and chunk index for CV evidence, and the URL for jobs.
If the evidence is insufficient, say that you do not know.
Do not make hiring predictions or provide medical, legal, or unrelated advice.
Ask for confirmation before sending an email or performing an irreversible action.
```

## 5. Five-question demonstration script

The following is the required demonstration structure. It should be executed
after the agent loop is implemented and saved with actual transcripts.

1. **Without a tool:** “What can Jobify do?”  
   Expected: a short capability explanation without CV/job retrieval.
2. **With the RAG tool:** “Which experience supports an SAP analyst role?”  
   Expected: `search_cv` call, grounded answer and chunk citations.
3. **Follow-up with memory:** “Which of those experiences used enterprise
   systems?”  
   Expected: answer uses the previous tool result or performs a focused search.
4. **Using the other tool:** “Find current SAP consultant jobs in Tunisia.”  
   Expected: `search_jobs` call and URLs.
5. **Out of scope:** “What medical condition do I have?”  
   Expected: “I do not know; this is outside Jobify's supported evidence.”

## 6. Deployment status

**Implemented:** Docker deployment, terminal interaction, local model,
retrieval, rendering, email confirmation, and deterministic safety checks.

**Missing for full assignment compliance:** LLM-controlled agentic loop, formal
tool descriptions exposed to the LLM, source-citing conversational responses,
and saved transcripts for all five demonstration cases.

