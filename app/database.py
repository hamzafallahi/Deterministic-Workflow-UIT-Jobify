"""PostgreSQL persistence and pgvector retrieval."""

from contextlib import contextmanager
from typing import Iterator
import json

import psycopg

from .scraper import JobPosting


class Database:
    def __init__(self, connection_string: str):
        if not connection_string or "PASTE" in connection_string:
            raise ValueError("POSTGRES_CONNECTION_STRING is not configured")
        self.connection_string = connection_string

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        with psycopg.connect(self.connection_string) as connection:
            yield connection

    def ensure_cv_metadata(self) -> None:
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS cv_metadata ("
                    "source_name TEXT PRIMARY KEY, cv_text TEXT NOT NULL, "
                    "keywords_json JSONB NOT NULL DEFAULT '[]'::jsonb, "
                    "chunk_count INTEGER NOT NULL DEFAULT 0, "
                    "updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
                )

    def list_cv_sources(self) -> list[tuple[str, int]]:
        self.ensure_cv_metadata()
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT source_name, COUNT(*) FROM cv_chunks "
                    "WHERE embedding IS NOT NULL GROUP BY source_name "
                    "ORDER BY source_name"
                )
                return [(row[0], row[1]) for row in cursor.fetchall()]

    def get_cv_metadata(self, source_name: str) -> tuple[str, list[str]]:
        self.ensure_cv_metadata()
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT cv_text, keywords_json FROM cv_metadata "
                    "WHERE source_name = %s",
                    (source_name,),
                )
                row = cursor.fetchone()
                if not row:
                    return "", []
                keywords = row[1] if isinstance(row[1], list) else []
                return row[0], keywords

    def get_source_chunks(self, source_name: str) -> list[str]:
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT content FROM cv_chunks WHERE source_name = %s "
                    "ORDER BY chunk_index",
                    (source_name,),
                )
                return [row[0] for row in cursor.fetchall()]

    def save_cv_metadata(
        self, source_name: str, cv_text: str, keywords: list[str], chunk_count: int
    ) -> None:
        self.ensure_cv_metadata()
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO cv_metadata "
                    "(source_name, cv_text, keywords_json, chunk_count, updated_at) "
                    "VALUES (%s, %s, %s::jsonb, %s, NOW()) "
                    "ON CONFLICT (source_name) DO UPDATE SET "
                    "cv_text=EXCLUDED.cv_text, "
                    "keywords_json=EXCLUDED.keywords_json, "
                    "chunk_count=EXCLUDED.chunk_count, "
                    "updated_at=NOW()",
                    (
                        source_name,
                        cv_text,
                        json.dumps(keywords, ensure_ascii=False),
                        chunk_count,
                    ),
                )

    def replace_cv_chunks(
        self, source_name: str, chunks: list[str], embeddings: list[list[float]]
    ) -> None:
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM cv_chunks WHERE source_name = %s", (source_name,))
                for index, (content, embedding) in enumerate(zip(chunks, embeddings)):
                    cursor.execute(
                        "INSERT INTO cv_chunks "
                        "(source_name, chunk_index, content, embedding) "
                        "VALUES (%s, %s, %s, %s::vector)",
                        (source_name, index, content, _vector_literal(embedding)),
                    )

    def save_jobs(self, jobs: list[JobPosting]) -> None:
        with self.connection() as connection:
            with connection.cursor() as cursor:
                for job in jobs:
                    cursor.execute(
                        "INSERT INTO job_postings "
                        "(source_url, title, company, location, description, "
                        "recruiter_email, posted_at) VALUES "
                        "(%s, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (source_url) DO UPDATE SET "
                        "title=EXCLUDED.title, company=EXCLUDED.company, "
                        "location=EXCLUDED.location, description=EXCLUDED.description, "
                        "recruiter_email=EXCLUDED.recruiter_email, posted_at=EXCLUDED.posted_at",
                        (
                            job.url,
                            job.title,
                            job.company,
                            job.location,
                            job.description,
                            job.recruiter_email,
                            job.posted_at,
                        ),
                    )

    def retrieve_chunks(self, embedding: list[float], limit: int) -> list[str]:
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT content FROM cv_chunks WHERE embedding IS NOT NULL "
                    "ORDER BY embedding <=> %s::vector LIMIT %s",
                    (_vector_literal(embedding), limit),
                )
                return [row[0] for row in cursor.fetchall()]


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in values) + "]"
