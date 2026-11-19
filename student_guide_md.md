# Student Guide — Building Your Own RAG Agent with CRISP-DM

**Individual Project (Exam / DS Grade)**

This project (news agent) serves as your reference template: [https://github.com/choukamani/UIT-Project](https://github.com/choukamani/UIT-Project)

**Your mission:** Build a RAG agent on a domain of your choice, following the **6 CRISP-DM steps**. You may draw inspiration from the reference project's architecture, but the topic, data, and analysis must be your own.

---

## 0. Guidelines & Modalities

| Aspect | Details |
| :--- | :--- |
| **Evaluation** | This project constitutes your exam (DS) grade. |
| **Work** | Strictly individual: pairs/groups are not accepted. |
| **Instructions** | Also available on Moodle. |
| **Submission** | Project compressed into a `.zip` file, sent via email, no later than the day before the session. |
| **Zip Contents** | Code, README, documentation — **excluding** the `.venv` folder and large data files. |
| **Presentation** | During the session: presentation of all completed parts + live demonstration of the agent. |
| **Q&A** | Questions will be asked about your project and your presentation. |

---

## 1. Choosing a Topic

You need: **(a)** a legal source of text documents, and **(b)** questions that a real user would ask about these documents.

| Topic Idea | Possible Data Source | Possible Additional Tool |
| :--- | :--- | :--- |
| **Academic Regulations Assistant** | University regulations PDF | `calculer_moyenne(notes)` *(calculate_average)* |
| **Legal Assistant (Labor Code)** | Law articles (Légifrance, open data) | `rechercher_article(numero)` *(search_article)* |
| **Cooking Recipe Assistant** | Recipe dataset (Kaggle) | `convertir_unites(quantite, unite)` *(convert_units)* |
| **Customer Service FAQ** | Help pages of an open-source product | `creer_ticket(sujet)` *(create_ticket)* |
| **Scientific Watch** | arXiv abstracts (Public API) | `filtrer_par_annee(annee)` *(filter_by_year)* |
| **City Tourist Assistant** | Wikipedia / Wikivoyage pages | `meteo_du_jour(ville)` *(todays_weather)* |
| **Python Library Documentation** | Official docs (Markdown) | `executer_exemple(code)` *(run_example)* |

> **Warning:** Do not scrape websites that prohibit it, and do not use personal data.

---

## 2. Deliverables, Step by Step

### Step 1 — Business Understanding → `docs/1_comprehension_metier.md`
- [ ] **The problem:** Who is the user? What questions do they ask?
- [ ] Why an LLM alone is not enough (include an example of a bad response).
- [ ] **The solution:** RAG + agent + tools diagram/schema.
- [ ] At least **4 quantified success criteria** (both business AND data mining), with their thresholds.
- [ ] Constraints and risks (copyright/rights, bias, cost, confidentiality, data freshness).

### Step 2 — Data Understanding → `etape2_donnees/`
- [ ] Automated collection; raw data saved without modification.
- [ ] Exploration report: volume, sources, missing values, duplicates, lengths, time period.
- [ ] At least **2 commented charts/graphs** (in a notebook or interface).
- [ ] A list of conclusions justifying the choices made in Step 3.

### Step 3 — Data Preparation → `etape3_preparation/`
- [ ] The **5 named sub-steps**: selection, cleaning, construction, integration, formatting.
- [ ] Chunking strategy justified by exploration (chunk size, overlap).
- [ ] Each chunk carries its metadata (to enable source citation).
- [ ] Before / after statistics (how many items removed and why).

### Step 4 — Modeling → `etape4_modelisation/`
- [ ] Embeddings + vector index + `rechercher(question, k)` *(search)* function.
- [ ] A classic RAG chain (`Retrieve` → `Augment` → `Generate`).
- [ ] Justification of choices (embedding model, $k$, LLM).

### Step 5 — Evaluation → `etape5_evaluation/`
- [ ] A saved test set (at least **15 questions**; ideally with a portion written by hand).
- [ ] A simple baseline and a comparison against your model.
- [ ] Retrieval metrics: **Hit@k** and **MRR**.
- [ ] Generation/response metrics: **source citation** and **faithfulness**.
- [ ] Automated verification of the success criteria from Step 1.
- [ ] At least **3 experiments** logged in `rapports/historique_experiences.csv` (e.g., 3 chunk sizes, or 2 embedding models) along with their analysis.

### Step 6 — Deployment → `etape6_deploiement/` + `app/`
- [ ] An agent with an agentic loop and at least **2 tools** (including RAG search).
- [ ] Clear tool descriptions (this is all the LLM sees to decide when to use them).
- [ ] A system prompt that enforces: answering strictly from sources, citing them, and not hallucinating/making things up.
- [ ] An interface of your choice: terminal, FastAPI API, or Streamlit web page.
- [ ] A **5-question demonstration**:
  1. Without a tool
  2. With a tool
  3. Follow-up question (memory)
  4. Using the other tool
  5. Out-of-scope question (the agent must state that it does not know)

### Cross-Cutting Requirements (Transverse)
- [ ] Architecture identical to the reference project (see `docs/ARCHITECTURE.md`).
- [ ] `config.py`: no magic values hardcoded elsewhere in the codebase.
- [ ] At least **8 pytest tests** (preparation, metrics, agent loop using a mock/fake LLM).
- [ ] `README.md` with installation and execution commands readable in under 5 minutes.

---

## 3. Starting from the Reference Project

```bash
# 1. Copy the reference project and rename it
# 2. Verify that everything works BEFORE modifying anything
uv sync
uv run pytest
uv run python main.py pipeline

# 3. Replace, in this exact order:
#    docs/1_comprehension_metier.md    -> your scoping (BEFORE writing any code!)
#    etape2_donnees/collecte.py        -> your data source
#    config.py                         -> your settings and thresholds
#    etape6_deploiement/outils.py      -> your tools
#    etape6_deploiement/prompts.py     -> your instructions/prompts
#    tests/                            -> adapt test data
```

*Note: The files in `etape3_preparation/`, `etape4_modelisation/`, and `etape5_evaluation/` often work without modification—that is the main advantage of a good architecture.*

---

## 4. Indicative Grading Rubric (/20)

| Criterion | Points |
| :--- | :---: |
| **Step 1:** Clear problem statement, quantified and relevant success criteria | 2 |
| **Step 2:** Complete exploration, conclusions linked to Step 3 | 2 |
| **Step 3:** Justified preparation, metadata, before/after statistics | 2 |
| **Step 4:** Functional vector index + RAG chain, justified choices | 2 |
| **Step 5:** Test set, baseline, 4 metrics, 3 analyzed experiments | 4 |
| **Step 6:** Agent with $\ge 2$ tools, interface, demonstration of the 5 cases | 4 |
| **Code Quality:** Architecture, `config.py`, tests, readability | 2 |
| **Oral Presentation:** Live demo, critical perspective on limitations | 2 |
| **Total** | **20** |

---

## 5. Common Mistakes to Avoid

- **Starting with code instead of Step 1** (writing success criteria after the fact).
- **Evaluating with questions copied directly from titles** → artificially perfect scores.
- **Forgetting the baseline:** *"0.8 MRR is good... compared to what?"*
- **Changing multiple settings at once between two experiments** → makes it impossible to draw valid conclusions.
- **Putting business logic inside the interface** (Streamlit/FastAPI) instead of the core package.
- **Vague tool descriptions** → the LLM won't know when to call them.