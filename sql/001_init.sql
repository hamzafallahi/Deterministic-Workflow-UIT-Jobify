CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS cv_chunks (
    id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_name, chunk_index)
);

CREATE INDEX IF NOT EXISTS cv_chunks_embedding_idx
    ON cv_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS job_postings (
    id BIGSERIAL PRIMARY KEY,
    source_url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    company TEXT,
    location TEXT,
    description TEXT NOT NULL,
    recruiter_email TEXT,
    posted_at TEXT,
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cv_metadata (
    source_name TEXT PRIMARY KEY,
    cv_text TEXT NOT NULL,
    keywords_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
