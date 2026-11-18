"""RenderCV YAML persistence and Docker execution."""

from pathlib import Path
import re
import shutil
from typing import Any

import docker
import yaml


class RenderError(RuntimeError):
    """Raised when RenderCV cannot produce a PDF."""


def save_yaml(data: dict[str, Any], path: Path) -> None:
    if not isinstance(data.get("cv"), dict) or not data["cv"].get("name"):
        raise RenderError("Generated RenderCV data is missing cv.name")
    normalize_rendercv_data(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def normalize_rendercv_data(data: dict[str, Any]) -> None:
    cv = data["cv"]
    cv.pop("design", None)
    data["design"] = {"theme": "classic"}

    allowed_cv_keys = {
        "name",
        "headline",
        "location",
        "email",
        "phone",
        "photo",
        "website",
        "social_networks",
        "custom_connections",
        "sections",
    }
    singular_section = cv.pop("section", None)
    if isinstance(singular_section, dict):
        existing_sections = cv.setdefault("sections", {})
        if not isinstance(existing_sections, dict):
            existing_sections = {}
            cv["sections"] = existing_sections
        for name, entries in singular_section.items():
            if name not in existing_sections:
                existing_sections[name] = entries
    for key in list(cv):
        if key not in allowed_cv_keys:
            cv.pop(key, None)

    cv.setdefault("headline", "")
    cv.setdefault("location", "")
    cv.setdefault("email", "")
    cv.setdefault("phone", "")
    cv.setdefault("website", "")
    cv.setdefault("social_networks", [])
    phone = str(cv.get("phone") or "").strip()
    phone_digits = re.sub(r"\D", "", phone)
    if len(phone_digits) == 8:
        cv["phone"] = f"+216 {phone_digits[:2]} {phone_digits[2:5]} {phone_digits[5:]}"
    elif phone_digits.startswith("216") and len(phone_digits) == 11:
        local = phone_digits[3:]
        cv["phone"] = f"+216 {local[:2]} {local[2:5]} {local[5:]}"
    else:
        cv.pop("phone", None)
    sections = cv.setdefault("sections", {})
    if not isinstance(sections, dict):
        sections = {}
        cv["sections"] = sections

    allowed_sections = {"education", "experience", "projects", "skills"}
    for section_name in list(sections):
        if section_name not in allowed_sections:
            sections.pop(section_name, None)

    normalized_education = []
    for entry in sections.get("education", []) if isinstance(sections.get("education", []), list) else []:
        if not isinstance(entry, dict):
            continue
        institution = entry.get("institution") or entry.get("school_name") or entry.get("university")
        area = entry.get("area") or entry.get("field") or entry.get("degree") or ""
        if not institution:
            continue
        normalized = {
            "institution": str(institution),
            "area": str(area or "Computer Science"),
        }
        degree = entry.get("degree")
        if degree:
            normalized["degree"] = str(degree)
        start_date = normalize_rendercv_date(entry.get("start_date"))
        end_date = normalize_rendercv_date(entry.get("end_date") or entry.get("graduation_year"))
        if start_date:
            normalized["start_date"] = start_date
        if end_date:
            normalized["end_date"] = end_date
        location = entry.get("location")
        if location:
            normalized["location"] = str(location)
        highlights = entry.get("highlights")
        if isinstance(highlights, list):
            normalized["highlights"] = [str(item) for item in highlights if item]
        if normalized:
            normalized_education.append(normalized)
    if normalized_education:
        sections["education"] = normalized_education
    else:
        sections.pop("education", None)

    normalized_experience = []
    for entry in sections.get("experience", []) if isinstance(sections.get("experience", []), list) else []:
        if not isinstance(entry, dict):
            continue
        company = entry.get("company")
        position = entry.get("position")
        if not company or not position:
            continue
        normalized = {"company": str(company), "position": str(position)}
        duration = entry.get("duration")
        if not entry.get("start_date") and duration:
            duration_start, duration_end = normalize_rendercv_duration(str(duration))
            if duration_start:
                normalized["start_date"] = duration_start
            if duration_end:
                normalized["end_date"] = duration_end
        start_date = normalize_rendercv_date(entry.get("start_date"))
        end_date = normalize_rendercv_date(entry.get("end_date"))
        if start_date:
            normalized["start_date"] = start_date
        if end_date:
            normalized["end_date"] = end_date
        summary = entry.get("summary") or entry.get("description")
        if summary:
            normalized["summary"] = str(summary)
        highlights = (
            entry.get("highlights")
            or entry.get("achievements")
            or entry.get("key_achievements")
        )
        if isinstance(highlights, list):
            normalized["highlights"] = [
                str(item.get("key_achievement") if isinstance(item, dict) else item)
                for item in highlights
                if item
            ]
        normalized_experience.append(normalized)
    if normalized_experience:
        sections["experience"] = normalized_experience
    else:
        sections.pop("experience", None)

    normalized_projects = []
    for entry in sections.get("projects", []) if isinstance(sections.get("projects", []), list) else []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name") or entry.get("project_name")
        if not name:
            continue
        normalized = {"name": str(name)}
        summary = entry.get("summary") or entry.get("description")
        if summary:
            normalized["summary"] = str(summary)
        start_date = normalize_rendercv_date(entry.get("start_date"))
        end_date = normalize_rendercv_date(entry.get("end_date"))
        if start_date:
            normalized["start_date"] = start_date
        if end_date:
            normalized["end_date"] = end_date
        highlights = (
            entry.get("highlights")
            or entry.get("achievements")
            or entry.get("key_achievements")
        )
        if isinstance(highlights, list):
            normalized["highlights"] = [
                str(item) for item in highlights if item
            ]
        normalized_projects.append(normalized)
    if normalized_projects:
        sections["projects"] = normalized_projects
    else:
        sections.pop("projects", None)

    normalized_skills = []
    for entry in sections.get("skills", []) if isinstance(sections.get("skills", []), list) else []:
        if isinstance(entry, dict):
            label = entry.get("label") or entry.get("skill") or entry.get("category")
            details = entry.get("details")
            if not details:
                details = entry.get("tech_stack") or entry.get("frameworks")
            if isinstance(details, list):
                details = ", ".join(str(item) for item in details if item)
            if label and details:
                normalized_skills.append({"label": str(label), "details": str(details)})
        elif isinstance(entry, str) and entry.strip():
            normalized_skills.append({"label": "Skills", "details": entry.strip()})
    if normalized_skills:
        sections["skills"] = normalized_skills
    else:
        sections.pop("skills", None)


def normalize_rendercv_date(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in {"present", "today", "now"}:
        return "present"
    match = re.match(r"^(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?$", text)
    if match:
        year, month, day = match.groups()
        result = year
        if month:
            result += f"-{int(month):02d}"
        if day:
            result += f"-{int(day):02d}"
        return result
    months = {
        "jan": "01", "january": "01", "feb": "02", "february": "02",
        "mar": "03", "march": "03", "apr": "04", "april": "04",
        "may": "05", "jun": "06", "june": "06", "jul": "07", "july": "07",
        "aug": "08", "august": "08", "sep": "09", "sept": "09",
        "september": "09", "oct": "10", "october": "10",
        "nov": "11", "november": "11", "dec": "12", "december": "12",
    }
    match = re.match(r"^([A-Za-z]+)\s+(\d{4})$", text)
    if match:
        month = months.get(match.group(1).lower())
        if month:
            return f"{match.group(2)}-{month}"
    return None


def normalize_rendercv_duration(value: str) -> tuple[str | None, str | None]:
    parts = re.split(r"\s+(?:-|–|—|to)\s+", value.strip(), maxsplit=1)
    if len(parts) == 1:
        return normalize_rendercv_date(parts[0]), None
    return normalize_rendercv_date(parts[0]), normalize_rendercv_date(parts[1])


def render_yaml(
    yaml_path: Path, output_dir: Path, service: str, project_dir: Path
) -> Path:
    relative_name = yaml_path.name
    try:
        client = docker.DockerClient(
            base_url="unix:///var/run/docker.sock", timeout=180
        )
        container = None
        for name in (service, "rendercv_service"):
            try:
                container = client.containers.get(name)
                break
            except docker.errors.NotFound:
                continue
        if container is None:
            raise RenderError(
                f"RenderCV container not found (tried {service} and rendercv_service)"
            )
        result = container.exec_run(
            ["rendercv", "render", f"data/{relative_name}"],
            workdir="/app",
        )
        client.close()
    except docker.errors.DockerException as exc:
        raise RenderError(f"RenderCV execution failed: {exc}") from exc
    exit_code = getattr(result, "exit_code", 1)
    if exit_code != 0:
        output = getattr(result, "output", b"")
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        raise RenderError(str(output).strip() or "RenderCV returned a non-zero status")
    pdf_path = output_dir / f"{yaml_path.stem}.pdf"
    candidate_paths = sorted(
        output_dir.rglob("*.pdf"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidate_paths:
        if candidate == pdf_path:
            continue
        if "rendercv_output" in candidate.parts:
            shutil.copy2(candidate, pdf_path)
            break
    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        raise RenderError(f"RenderCV did not create {pdf_path}")
    return pdf_path
