"""Interactive Jobify application workflow."""

from datetime import date
import re
import sys

from .config import settings
from .cv_ingest import (
    chunk_text,
    extract_pdf_text,
    find_master_cv,
)
from .database import Database
from .emailer import EmailError, send_application
from .ollama_client import OllamaClient, OllamaError
from .rendercv import render_yaml, save_yaml
from .scraper import ScraperError, TanitjobsScraper


def _safe_name(value: str) -> str:
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    return re.sub(r"[-\s]+", "-", value).strip("-_") or "unknown"


def _choose_job(jobs):
    print("\nAvailable jobs:")
    for index, job in enumerate(jobs, 1):
        print(
            f"{index}. {job.title} | {job.company or 'Unknown'} | "
            f"{job.location or 'Unknown'}\n   {job.url}"
        )
    while True:
        answer = input(f"\nSelect a job (1-{len(jobs)}) or q to quit: ").strip()
        if answer.lower() == "q":
            raise SystemExit("No application generated.")
        try:
            index = int(answer)
        except ValueError:
            print("Enter a number from the list.")
            continue
        if 1 <= index <= len(jobs):
            return jobs[index - 1]
        print("That number is not in the list.")


def _choose_keywords(keywords: list[str]) -> list[str]:
    print("\nChoose up to 3 keywords to search on Tanitjobs:")
    for index, keyword in enumerate(keywords, 1):
        print(f"{index}. {keyword}")
    while True:
        answer = input("Enter numbers separated by commas (for example 1,4,7), or q to quit: ").strip()
        if answer.lower() == "q":
            raise SystemExit("No application generated.")
        try:
            indexes = [int(value.strip()) for value in answer.split(",") if value.strip()]
        except ValueError:
            print("Use comma-separated numbers from the list.")
            continue
        if not indexes or len(indexes) > 3 or len(set(indexes)) != len(indexes):
            print("Choose between 1 and 3 different keywords.")
            continue
        if all(1 <= index <= len(keywords) for index in indexes):
            return [keywords[index - 1] for index in indexes]
        print("One or more numbers are not in the list.")


def _choose_cv(database: Database, master_cv_path) -> tuple[str, str, list[str], bool]:
    sources = database.list_cv_sources()
    print("\nMaster CV options:")
    for index, (source_name, chunk_count) in enumerate(sources, 1):
        print(f"{index}. Reuse stored CV: {source_name} ({chunk_count} chunks)")
    ingest_index = len(sources) + 1
    print(f"{ingest_index}. Re-ingest {master_cv_path.name}")
    while True:
        answer = input(
            f"Choose 1-{ingest_index} or q to quit: "
        ).strip()
        if answer.lower() == "q":
            raise SystemExit("No application generated.")
        try:
            choice = int(answer)
        except ValueError:
            print("Enter a number from the list.")
            continue
        if choice == ingest_index:
            return master_cv_path.name, "", [], True
        if 1 <= choice <= len(sources):
            source_name = sources[choice - 1][0]
            cv_text, keywords = database.get_cv_metadata(source_name)
            return source_name, cv_text, keywords, False
        print("That number is not in the list.")


def main() -> None:
    settings.cv_data_dir.mkdir(parents=True, exist_ok=True)
    master_cv_path = find_master_cv(settings.master_cv_dir)
    ollama = OllamaClient(
        settings.ollama_base_url,
        settings.ollama_model,
        settings.ollama_embedding_model,
        settings.ollama_timeout,
    )
    database = Database(settings.postgres_connection_string)
    source_name, stored_cv_text, keywords, ingest = _choose_cv(database, master_cv_path)

    if ingest:
        print(f"Reading and embedding master CV: {master_cv_path.name}")
        cv_text = extract_pdf_text(master_cv_path)
        chunks = chunk_text(cv_text, settings.cv_chunk_size, settings.cv_chunk_overlap)
        print(f"Creating embeddings for {len(chunks)} CV chunks...")
        embeddings = [ollama.embed(chunk) for chunk in chunks]
        database.replace_cv_chunks(source_name, chunks, embeddings)
        keywords = ollama.extract_keywords(cv_text)
        database.save_cv_metadata(source_name, cv_text, keywords, len(chunks))
    else:
        print(f"Reusing stored CV: {source_name}")
        cv_text = stored_cv_text or "\n\n".join(database.get_source_chunks(source_name))
        if not cv_text:
            raise FileNotFoundError(f"No stored text found for CV: {source_name}")
        upgraded_chunks = chunk_text(cv_text, settings.cv_chunk_size, settings.cv_chunk_overlap)
        stored_chunk_count = len(database.get_source_chunks(source_name))
        if stored_chunk_count != len(upgraded_chunks):
            print(
                f"Upgrading stored CV from {stored_chunk_count} to "
                f"{len(upgraded_chunks)} chunks..."
            )
            embeddings = [ollama.embed(chunk) for chunk in upgraded_chunks]
            database.replace_cv_chunks(source_name, upgraded_chunks, embeddings)
            if not keywords:
                keywords = ollama.extract_keywords(cv_text)
            database.save_cv_metadata(
                source_name, cv_text, keywords, len(upgraded_chunks)
            )
        if not keywords:
            keywords = ollama.extract_keywords(cv_text)
            database.save_cv_metadata(
                source_name,
                cv_text,
                keywords,
                len(database.get_source_chunks(source_name)),
            )
    if not keywords:
        raise OllamaError("No job-search keywords were extracted from the CV")
    selected_keywords = _choose_keywords(keywords)
    scraper = TanitjobsScraper()
    jobs = []
    seen_urls = set()
    for keyword in selected_keywords:
        print(f"Searching Tanitjobs for: {keyword}")
        keyword_jobs = scraper.search(
            [keyword], limit=settings.scraper_jobs_per_keyword
        )
        for job in keyword_jobs:
            if job.url not in seen_urls:
                jobs.append(job)
                seen_urls.add(job.url)
    if not jobs:
        print("No jobs were found. Try adjusting Tanitjobs configuration or keywords.")
        return
    database.save_jobs(jobs)
    job = _choose_job(jobs)
    relevant_chunks = database.retrieve_chunks(
        ollama.embed(job.description), settings.retrieval_limit
    )
    cover_letter, rendercv_data = ollama.generate_application(
        {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "description": job.description,
            "url": job.url,
        },
        relevant_chunks,
        cv_text,
    )

    stem = (
        f"{_safe_name(job.title)}-{_safe_name(job.company)}-{date.today().isoformat()}"
    )
    yaml_path = settings.cv_data_dir / f"{stem}.yaml"
    cover_letter_path = settings.cv_data_dir / f"{stem}.txt"
    save_yaml(rendercv_data, yaml_path)
    cover_letter_path.write_text(cover_letter, encoding="utf-8")
    print(f"\nSaved RenderCV YAML: {yaml_path}")
    print(f"Saved cover letter: {cover_letter_path}")
    pdf_path = render_yaml(
        yaml_path,
        settings.cv_data_dir,
        settings.rendercv_service,
        settings.docker_compose_project_dir,
    )
    print(f"RenderCV PDF verified: {pdf_path}")
    print(f"\n--- Cover letter ---\n{cover_letter}\n--- End cover letter ---")

    recipient = job.recruiter_email
    if recipient:
        print(f"\nRecruiter email found: {recipient}")
    else:
        recipient = input(
            "\nNo recruiter email found. Enter a target email, or press Enter to save only: "
        ).strip()
    if not recipient:
        print(f"Your customized CV and cover letter are saved in {settings.cv_data_dir}.")
        return
    confirmation = input(f"Send the application to {recipient}? [y/N]: ").strip().lower()
    if confirmation not in {"y", "yes"}:
        print(f"Files remain saved in {settings.cv_data_dir}; no email was sent.")
        return
    send_application(
        settings.smtp_host,
        settings.smtp_port,
        settings.user_email,
        settings.email_app_password,
        recipient,
        f"Application for {job.title} - {job.company}",
        cover_letter,
        pdf_path,
    )
    print("Application email sent successfully.")


if __name__ == "__main__":
    try:
        main()
    except (
        FileNotFoundError,
        ValueError,
        ScraperError,
        OllamaError,
        EmailError,
        OSError,
    ) as exc:
        print(f"Jobify failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
