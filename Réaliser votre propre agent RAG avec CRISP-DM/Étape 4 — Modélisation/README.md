# Step 4 — Modeling

## 1. Embedding model and vector index

Jobify uses Ollama's `nomic-embed-text` embedding model. The application
verifies that embeddings have exactly 768 dimensions. PostgreSQL with the
pgvector extension stores the vectors and uses an HNSW cosine-distance index.

This choice keeps the system local, avoids a second database service, and
supports semantic matching between a job description and CV evidence.

## 2. Search function

The effective search operation is:

```python
Database.retrieve_chunks(embedding, limit)
```

The selected job description is embedded, then PostgreSQL executes cosine
nearest-neighbor ordering and returns the top `RETRIEVAL_LIMIT` chunks. The
default value is `6`.

Conceptually:

```text
rechercher(question, k)
  query_vector = embed(question)
  return pgvector ORDER BY cosine_distance(query_vector, chunk.embedding) LIMIT k
```

## 3. Classic RAG chain

```text
Retrieve:  embed(selected job description) -> retrieve top-k CV chunks
Augment:   add retrieved CV evidence to the generation prompt
Generate:  Ollama writes the cover letter and tailored RenderCV YAML
```

The current generation uses `qwen3.5:4b` with `think=false`, temperature
`0.2–0.3`, and `num_ctx=8192`. Cover-letter and YAML generation are separate
requests so each output has a smaller, focused schema.

## 4. Why these choices

- **nomic-embed-text:** local, lightweight, and verified at 768 dimensions;
  suitable for the project's hardware and PostgreSQL schema.
- **pgvector:** persistent, simple to operate with the existing PostgreSQL
  service, and supports cosine/HNSW retrieval.
- **k=6:** provides multiple evidence chunks without filling the local model's
  context with the entire database. It must still be validated experimentally.
- **qwen3.5:4b:** fits the available GPU better than the previous model and
  produces structured output with thinking disabled.
- **deterministic RenderCV validation:** protects the final PDF from invalid
  model-generated fields.

## 5. Limitations

The current search API returns chunk text rather than a citation object
containing source name, rank, and score. This is sufficient for internal
augmentation but insufficient for a fully source-citing conversational agent.
Step 5 should measure retrieval quality, and Step 6 should expose source
metadata to the user.

