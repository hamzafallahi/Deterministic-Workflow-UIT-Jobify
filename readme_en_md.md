# RAG News Agent — A CRISP-DM Reference Project

Comprehensive educational project: building a **RAG** (*Retrieval-Augmented Generation*) system **from scratch** followed by an **agent** that uses it as a **tool**, following the **6 steps of CRISP-DM**.

The agent answers questions about today's news (RSS feeds from France 24, Le Monde, franceinfo) **while citing its sources**.
**Everything is free and local**: open-source embeddings and LLM (Qwen 2.5 via Ollama), no API keys required.

```
   1. Business ──► 2. Data ──► 3. Preparation ──► 4. Modeling ──► 5. Evaluation ──► 6. Deployment
       ▲                              ▲                  (RAG)              │              (Agent)
       │                              └─────── criteria not met ────────────┤
       └────────────────────────────── need has changed ────────────────────┘
```

## Documentation

| Document | Content |
|---|---|
| [`docs/1_comprehension_metier.md`](docs/1_comprehension_metier.md) | **Step 1**: problem, solution, quantified success criteria |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Code organization, data flow, RAG vs Agent, principles |
| [`docs/GUIDE_DEMO.md`](docs/GUIDE_DEMO.md) | How to run and **present** each step |
| [`docs/GUIDE_ETUDIANTS.md`](docs/GUIDE_ETUDIANTS.md) ([PDF](docs/GUIDE_ETUDIANTS.pdf)) | **Specifications** for completing your own project (modalities, deliverables, grading rubric) |

## Architecture at a Glance

```
main.py                          single entry point
src/agent_rag/
├── config.py                    all settings
├── commun/                      JSON files + LLM access
├── etape2_donnees/              RSS collection + exploration
├── etape3_preparation/          cleaning + chunks
├── etape4_modelisation/         embeddings, vector index, RAG chain
├── etape5_evaluation/           test set, baseline, metrics, LLM-as-a-judge
└── etape6_deploiement/          tools + agent (agentic loop)
app/                             FastAPI API + Streamlit interface
notebooks/                       step-by-step demonstration
tests/                           automated tests (pytest)
data/  rapports/                 outputs from each step
```

One folder = one CRISP-DM step. Details in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Installation

Prerequisites: Python ≥ 3.10 and [Ollama](https://ollama.com/download).

```bash
ollama pull qwen2.5:3b          # the agent LLM (~1.9 GB, fast)
ollama pull qwen2.5:7b          # the step 5 judge LLM (~4.7 GB, more reliable)

uv sync                         # option A: with uv (recommended)
# or
python -m venv .venv            # option B: with pip
.venv\Scripts\activate          #   (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
```

The embedding model (~470 MB) downloads automatically upon the first launch of step 4.

## Usage

A single command, one subcommand per step (with uv: `uv run python main.py ...`):

| CRISP-DM Step | Command |
|---|---|
| 2. Data | `python main.py donnees` |
| 3. Preparation | `python main.py preparation` |
| 4. Modeling | `python main.py modelisation` |
| 4. Test classic RAG | `python main.py rag "What is the rugby news?"` |
| 5. Evaluation (search) | `python main.py evaluation` |
| 5. Evaluation (+ RAG vs agent answers) | `python main.py evaluation --generation` |
| 6. Terminal agent | `python main.py agent` |
| 6. REST API | `python main.py api` → http://localhost:8000/docs |
| 6. Web interface | `python main.py interface` → http://localhost:8501 (or double-click `lancer_interface.bat`) |
| 2 → 5 all at once | `python main.py pipeline` |

```bash
uv run pytest                   # 29 tests, < 1 s, no Internet or LLM required
```

Without an internet connection, step 2 falls back to a small set of **dummy** articles (`data/exemple/`).

### Example Agent Session

```
You > What is the score of the France-Turkey match?
   [tool] rechercher_actualites({"requete": "score match France-Turkey"})

Agent > According to the articles, Les Bleus took the lead following an own goal…
Sources :
- France-Turkey: on a corner kick, Les Bleus take the lead… (franceinfo) : https://...
```

The `[tool]` line shows the moment when **the agent decides on its own** to call the RAG tool.

## Exercise Ideas

1. **Step 3** — Vary `TAILLE_CHUNK` (50, 120, 300) and compare results in `rapports/historique_experiences.csv`.
2. **Step 4** — Test another embedding model (`intfloat/multilingual-e5-small`).
3. **Step 4** — Replace the NumPy index with ChromaDB or FAISS (only `index_vectoriel.py` needs to change).
4. **Step 5** — Write 10 test questions **by hand** and compare them to the generated questions.
5. **Step 5** — Modify `prompts.py` and measure the effect on citations and faithfulness.
6. **Step 6** — Add a `filtrer_par_source(source)` tool or a date filter.
7. **Step 6** — Connect another LLM (OpenAI, Claude, Gemini) by modifying only `commun/llm.py`.

## Known Limitations (to be discussed in class)

- RSS feeds only provide **title + summary**: the agent does not have access to the full article.
- The index must be **rebuilt** to include the current day's news (`python main.py pipeline`).
- The test set is **synthetic** (generated by the LLM) and the **judge** is an LLM (qwen2.5:7b): useful, but less reliable than human annotation.
- The small local LLM (qwen2.5:3b) struggles to decide when to call a tool: a **guardrail** in the code ("fallback search") guarantees a search happens. See section 7 of `docs/ARCHITECTURE.md`.
- On a PC without a dedicated graphics card, an agent response takes from 30 seconds to 2 minutes.