"""Environment-backed application configuration."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return parsed


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str = os.getenv(
        "OLLAMA_BASE_URL", "http://host.docker.internal:11434"
    )
    user_email: str = os.getenv("USER_EMAIL", "")
    email_app_password: str = os.getenv("EMAIL_APP_PASSWORD", "")
    postgres_connection_string: str = os.getenv(
        "POSTGRES_CONNECTION_STRING",
        "postgresql://jobify:change-me@db:5432/jobify",
    )
    tanitjobs_base_url: str = os.getenv(
        "TANITJOBS_BASE_URL", "https://www.tanitjobs.com"
    )
    tanitjobs_search_url: str = os.getenv(
        "TANITJOBS_SEARCH_URL", "https://www.tanitjobs.com/jobs/"
    )
    scraper_timeout_seconds: int = _int_env("SCRAPER_TIMEOUT_SECONDS", 20)
    scraper_max_jobs: int = _int_env("SCRAPER_MAX_JOBS", 10)
    scraper_jobs_per_keyword: int = _int_env("SCRAPER_JOBS_PER_KEYWORD", 5)
    scraper_verify_tls: bool = _bool_env("SCRAPER_VERIFY_TLS", True)
    scraper_ca_bundle_path: str = os.getenv("SCRAPER_CA_BUNDLE_PATH", "").strip()
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = _int_env("SMTP_PORT", 587)
    cv_data_dir: Path = Path(os.getenv("CV_DATA_DIR", "./cv_data"))
    rendercv_service: str = os.getenv("RENDERCV_SERVICE", "rendercv_service")
    master_cv_dir: Path = Path(os.getenv("MASTER_CV_DIR", "/workspace/master_cv"))
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
    ollama_embedding_model: str = os.getenv(
        "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"
    )
    ollama_timeout: int = _int_env("OLLAMA_TIMEOUT_SECONDS", 180)
    cv_chunk_size: int = _int_env("CV_CHUNK_SIZE", 1000)
    cv_chunk_overlap: int = _int_env("CV_CHUNK_OVERLAP", 200)
    retrieval_limit: int = _int_env("RETRIEVAL_LIMIT", 6)
    docker_compose_project_dir: Path = Path(
        os.getenv("DOCKER_COMPOSE_PROJECT_DIR", "/workspace")
    )


settings = Settings()
