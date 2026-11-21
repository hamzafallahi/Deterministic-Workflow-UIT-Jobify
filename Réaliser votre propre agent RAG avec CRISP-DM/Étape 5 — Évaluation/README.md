# Step 5 — Evaluation

This folder defines a reproducible evaluation plan. The current application
does not yet calculate these metrics, so no score is claimed here.

## 1. Saved test set

`test_questions.csv` contains 15 manually designed questions covering SAP,
backend, frontend, projects, education, identity, and out-of-scope requests.
Each question should be annotated with the relevant CV chunk index after the
collection run.

## 2. Baseline

The baseline is keyword retrieval over the complete normalized CV:

1. lowercase the question and CV;
2. count matching non-stopword terms for each CV chunk;
3. return the top `k` chunks by count.

The baseline is intentionally simple. Comparing it with pgvector answers the
question: does semantic retrieval improve ranking beyond literal word overlap?

## 3. Retrieval metrics

For each question with a labelled relevant-chunk set:

```text
Hit@k = 1 if at least one relevant chunk is in the first k results, else 0
MRR   = 1 / rank(first relevant result), or 0 if no relevant result exists
```

Report the mean across all labelled questions and compare baseline versus
pgvector at the same `k`.

## 4. Generation metrics

- **Citation support:** percentage of factual claims that can be traced to a
  supplied CV chunk or the full master CV.
- **Faithfulness:** percentage of answer claims judged entailed by the supplied
  evidence.

These should be scored with a small human annotation sheet or a documented
judge protocol. An LLM judge may assist, but it must not be presented as
ground truth without manual checks.

## 5. Automated success-criteria checks

The evaluation runner should verify:

- Hit@6 ≥ 0.80;
- MRR ≥ 0.70;
- citation support ≥ 90%;
- faithfulness ≥ 90%;
- PDF generation success ≥ 95%;
- out-of-scope refusal ≥ 95%.

Failures should be reported explicitly rather than hidden by fallback answers.

## 6. Controlled experiments

`rapports/historique_experiences.csv` records three planned experiments. Only
one variable should change between experiments:

1. chunk size 500;
2. chunk size 1000;
3. chunk size 1500.

The analysis should compare retrieval metrics, generation faithfulness, runtime,
and context size. A later experiment may compare a second embedding model, but
it must be logged separately.

## 7. Current status

The production workflow demonstrates retrieval and generation, but the
assignment's formal test runner, baseline comparison, citation metric,
faithfulness metric, and measured experiment results remain to be implemented.

