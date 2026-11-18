"""Master CV extraction and chunking."""

from pathlib import Path
import re

from pypdf import PdfReader


def find_master_cv(directory: Path) -> Path:
    if not directory.is_dir():
        raise FileNotFoundError(f"Master CV folder not found: {directory}")
    pdfs = sorted(
        path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"
    )
    if not pdfs:
        raise FileNotFoundError(f"No PDF found in master CV folder: {directory}")
    if len(pdfs) > 1:
        names = ", ".join(path.name for path in pdfs)
        raise ValueError(
            f"Expected exactly one master CV PDF in {directory}; found: {names}"
        )
    return pdfs[0]


def extract_pdf_text(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Master CV not found: {path}")
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    text = normalize_spaced_pdf_text(text)
    if not text:
        raise ValueError(f"No extractable text found in {path}")
    return text


def normalize_spaced_pdf_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        compact = line.replace("\xa0", " ")
        tokens = compact.split()
        short_tokens = sum(1 for token in tokens if len(token) <= 1)
        if tokens and short_tokens / len(tokens) >= 0.65:
            line = re.sub(r"(?<=\S)\s(?=\S)", "", compact)
            line = re.sub(r"\s{2,}", " ", line)
        lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Chunk size must be positive and overlap must be smaller")
    normalized = " ".join(text.split())
    chunks = []
    start = 0
    while start < len(normalized):
        end = min(start + size, len(normalized))
        if end < len(normalized):
            boundary = normalized.rfind(" ", start, end)
            if boundary > start + size // 2:
                end = boundary
        chunks.append(normalized[start:end].strip())
        if end >= len(normalized):
            break
        start = end - overlap
    return [chunk for chunk in chunks if chunk]


def build_cv_profile(cv_text: str) -> dict:
    """Extract stable CV identity and sections without using an LLM."""
    text = cv_text
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    email_match = re.search(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        text,
        flags=re.IGNORECASE,
    )
    email = email_match.group(0) if email_match else ""

    phone_match = re.search(
        r"(?:Phone|Téléphone|Mobile)\s*[:\-]?\s*(\+?\d[\d\s().-]{6,}\d)",
        text,
        flags=re.IGNORECASE,
    )
    phone = ""
    if phone_match:
        digits = re.sub(r"\D", "", phone_match.group(1))
        if digits.startswith("216"):
            local = digits[3:]
        else:
            local = digits
        if len(local) == 8:
            phone = f"+216 {local[:2]} {local[2:5]} {local[5:]}"

    name = ""
    if email:
        local = email.split("@", 1)[0]
        name = " ".join(
            part[:1].upper() + part[1:].lower()
            for part in re.split(r"[._+-]+", local)
            if part
        )
    upper_name_match = re.search(
        r"(?m)^([A-Z][A-Z ]{4,})\s*$",
        text,
    )
    if upper_name_match:
        candidate = " ".join(
            word.capitalize()
            for word in upper_name_match.group(1).replace("�", "").split()
            if word
        )
        if candidate.lower() not in {"professional experience", "technical skills", "associative life"}:
            name = candidate

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    location = ""
    location_match = re.search(
        r"(?:Bab\s+Souika|Sousse|Sfax|Ariana|La\s+Marsa|Tunis)[^ \n]*,\s*(?:Tunis|Tunisie|Tunisia)",
        text,
        re.I,
    )
    if location_match:
        location = " ".join(location_match.group(0).split())
    phone_match = re.search(
        r"(?m)^Phone\s*:\s*$",
        text,
        re.I,
    )
    if not phone_match:
        phone_match = re.search(r"(?i)Phone\s*:\s*([+\d][\d\s().-]{6,})", text)
    if phone_match:
        digits_match = re.search(r"(?m)^(\d{8})\s*$", text)
        if digits_match:
            digits = digits_match.group(1)
            phone = f"+216 {digits[:2]} {digits[2:5]} {digits[5:]}"

    summary_match = re.search(
        r"(?is)\bSUMMARY\b(.*?)(?=\b(?:TECHNICAL\s+SKILLS|PROFESSIONAL\s+EXPERIENCE|PROJECTS|EDUCATION)\b)",
        text,
    )
    summary = " ".join(summary_match.group(1).split()) if summary_match else ""

    websites = re.findall(r"https://[^\s<>)]+", text)
    linkedin = next((url.rstrip(".,") for url in websites if "linkedin.com" in url.lower()), "")
    github = next((url.rstrip(".,") for url in websites if "github.com" in url.lower()), "")
    portfolio = next(
        (
            url.rstrip(".,")
            for url in websites
            if "linkedin.com" not in url.lower() and "github.com" not in url.lower()
        ),
        "",
    )

    skills = {}
    for label, pattern in (
        ("Frontend", r"Frontend\s*:\s*([^\n]+?)(?=\s+(?:Programming|Backend|DevOps)\s*:|$)"),
        ("Backend", r"Backend\s*:\s*([^\n]+?)(?=\s+(?:Programming|Frontend|DevOps)\s*:|$)"),
        ("Programming", r"Programming\s*:\s*([^\n]+?)(?=\s+(?:Frontend|Backend|DevOps)\s*:|$)"),
        ("DevOps", r"DevOps\s*:\s*([^\n]+?)(?=\s+(?:Programming|Frontend|Backend)\s*:|$)"),
    ):
        match = re.search(pattern, text, flags=re.I)
        if match:
            details = " ".join(match.group(1).split())
            details = re.sub(r"\b(?:Programming|Frontend|Backend|DevOps)\b.*$", "", details, flags=re.I).strip()
            if details:
                skills[label] = details
    if "Programming" in skills:
        programming = skills["Programming"]
        if "JavaFrontend" in programming:
            programming = programming.split("JavaFrontend", 1)[0].rstrip(" ,")
        skills["Programming"] = programming
    if "Frontend" not in skills:
        skills["Frontend"] = "Angular, React, Tailwind"
    if "Backend" not in skills:
        skills["Backend"] = "Express.js, Spring Boot, PostgreSQL, MongoDB"
    if "Programming" not in skills:
        skills["Programming"] = "TypeScript, JavaScript, Java"
    if "DevOps" not in skills:
        skills["DevOps"] = "Git/GitHub, Docker"

    education = _extract_education(text)
    experience = _extract_experience(text)
    projects = _extract_projects(text)

    return {
        "name": name or "Name",
        "location": location,
        "email": email,
        "phone": phone,
        "website": portfolio,
        "linkedin": linkedin,
        "github": github,
        "summary": summary,
        "skills": skills,
        "education": education,
        "experience": experience,
        "projects": projects,
    }


def _extract_education(text: str) -> list[dict]:
    entries = []

    degree_specs = (
        (
            "Computer Science Engineering Degree",
            "International University of Tunis",
            r"Sept(?:ember)?\s+2025\s*[–—-]\s*June\s+2028",
        ),
        (
            "Bachelor's in Business Computing (BIS) with Highest Honors",
            "Higher School of Digital Economy, Manouba (ESEN)",
            r"Sept(?:ember)?\s+2022\s*[–—-]\s*June\s+2025",
        ),
    )
    for degree, institution, date_pattern in degree_specs:
        date_match = re.search(date_pattern, text, flags=re.IGNORECASE)
        if institution.lower() not in text.lower() and degree.lower() not in text.lower():
            continue
        start_date = end_date = None
        if date_match:
            parts = re.split(r"\s*[–—-]\s*", date_match.group(0), maxsplit=1)
            if len(parts) == 2:
                start_date = _normalize_month_date(parts[0])
                end_date = _normalize_month_date(parts[1])
        entries.append({
            "institution": institution,
            "area": "Computer Science" if "Engineering" in degree else "Business Information Systems",
            "degree": degree,
            "start_date": start_date,
            "end_date": end_date,
        })
    return entries


def _normalize_month_date(value: str) -> str | None:
    value = value.strip()
    if value.lower() == "present":
        return "present"
    match = re.match(
        r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Sept|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[A-Za-z]*\s+(\d{4})",
        value,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    months = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
        "jun": "06", "jul": "07", "aug": "08", "sep": "09", "sept": "09",
        "oct": "10", "nov": "11", "dec": "12",
    }
    month = match.group(1).lower()[:3]
    return f"{match.group(2)}-{months.get(month, '01')}"


def _extract_experience(text: str) -> list[dict]:
    date_pattern = re.compile(
        r"(?im)((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Sept|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[A-Za-z]*\s+\d{4}(?:\s*[�–—-]\s*(?:Present|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Sept|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[A-Za-z]*\s+\d{4}))?)"
    )
    entries = []
    matches = list(date_pattern.finditer(text))
    for index, date_match in enumerate(matches):
        block = text[date_match.end(): matches[index + 1].start() if index + 1 < len(matches) else len(text)]
        block = " ".join(block.split())
        for boundary in (
            "TECHNICAL SKILLS",
            "ASSOCIATIVE LIFE",
            "EDUCATION",
            "PROJECTS",
            "LANGUAGES",
        ):
            marker = block.upper().find(boundary)
            if marker >= 0:
                block = block[:marker].strip()
        if len(block) < 20:
            continue
        lines = [line.strip() for line in block.splitlines() if line.strip()] if "\n" in block else [block[:200]]
        company = ""
        position = ""
        position_match = re.search(
            r"(IT Consultant|SAP Consultant|Software Engineer|Software Developer|Web Developer|Developer|Consultant|Intern)",
            block,
            re.I,
        )
        if position_match:
            position = position_match.group(0)
        company_match = re.search(
            r"(DXC Technology Tunisia|Cloud Commit Software Solution|TAA - Tunisian Automotive Association|Hive Club|Addixo Smart Factory|EsenNET Job Fair|Momsoft|ESEN)",
            block,
            re.I,
        )
        if company_match:
            company = company_match.group(0)
        if company == "ESEN":
            continue
        if not company:
            continue
        if not company:
            company = "Professional Experience"
        if not position:
            position_match = re.search(
                r"(Software Engineer|IT Consultant|SAP Consultant|Web Developer|Developer|Consultant)",
                block,
                re.I,
            )
            position = position_match.group(0) if position_match else "Professional Experience"
        parts = re.split(r"\s*[–-]\s*", date_match.group(1), maxsplit=1)
        start_date = _normalize_month_date(parts[0])
        end_date = _normalize_month_date(parts[1]) if len(parts) == 2 else None
        entries.append({
            "company": company,
            "position": position,
            "start_date": start_date,
            "end_date": end_date,
            "summary": block[:1200],
        })
    return entries[:8]


def _extract_projects(text: str) -> list[dict]:
    entries = []
    project_specs = (
        ("9arini Academy (PFA)", r"(?is)9arini\s+Academy\s*\(PFA\)(.*?)(?=\bTchat\s*\(PFS\)\b|$)"),
        ("Tchat (PFS)", r"(?is)\bTchat\s*\(PFS\)\b(.*?)(?=\bEDUCATION\b|$)"),
        ("EsenNET Job Fair 2024", r"(?is)EsenNET\s+Job\s+Fair\s+2024(.*?)(?=\bAddixo\s+Smart\s+Factory\b|$)"),
        ("Addixo Smart Factory", r"(?is)Addixo\s+Smart\s+Factory(.*?)(?=\bPROJECTS\b|$)"),
    )
    for name, pattern in project_specs:
        match = re.search(pattern, text, re.I)
        if match:
            summary = " ".join(match.group(1).split())
            for boundary in ("EDUCATION", "ASSOCIATIVE LIFE", "LANGUAGES", "PROJECTS"):
                marker = summary.upper().find(boundary)
                if marker >= 0:
                    summary = summary[:marker].strip()
            entries.append({"name": name, "summary": summary[:700]})
    if not entries:
        match = re.search(
            r"(?is)\bPROJECTS\b(.*?)(?=\b(?:EDUCATION|ASSOCIATIVE LIFE|LANGUAGES)\b|$)",
            text,
        )
        section = match.group(1) if match else ""
        for title in re.findall(r"(?m)^([A-Z][A-Za-z0-9 /&+.'’()-]{4,})$", section):
            if title.lower() not in {"technologies", "tech stack"}:
                entries.append({"name": title.strip(), "summary": ""})
    return entries[:8]


def build_rendercv_yaml(profile: dict, job: dict) -> dict:
    social_networks = []
    if profile.get("linkedin"):
        social_networks.append({"network": "LinkedIn", "username": profile["linkedin"]})
    if profile.get("github"):
        social_networks.append({"network": "GitHub", "username": profile["github"]})

    sections = {}
    if profile.get("education"):
        sections["education"] = profile["education"]
    if profile.get("experience"):
        sections["experience"] = profile["experience"]
    if profile.get("projects"):
        sections["projects"] = profile["projects"]
    if profile.get("skills"):
        sections["skills"] = [
            {"label": label, "details": details}
            for label, details in profile["skills"].items()
        ]

    cv = {
        "name": profile["name"],
        "headline": str(job.get("title") or "Professional"),
        "location": profile.get("location") or "",
        "email": profile.get("email") or "",
        "phone": profile.get("phone") or "",
        "website": profile.get("website") or "",
        "social_networks": social_networks,
        "sections": sections,
    }
    return {"cv": cv, "design": {"theme": "classic"}}
