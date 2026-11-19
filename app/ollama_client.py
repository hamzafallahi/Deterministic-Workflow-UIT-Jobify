"""Local Ollama operations for text generation and embeddings."""

import json
import re
import time
from typing import Any

import requests


class OllamaError(RuntimeError):
    """Raised when Ollama cannot produce a usable response."""


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str = "deepseek-r1:7b",
        embedding_model: str = "nomic-embed-text",
        timeout: int = 180,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embedding_model = embedding_model
        self.timeout = timeout
        self._verify_server()
        self._ensure_model(model)
        self._ensure_model(embedding_model)

    def _verify_server(self) -> None:
        try:
            response = requests.get(
                f"{self.base_url}/api/tags", timeout=10
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise OllamaError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Start Ollama and ensure port 11434 is accessible."
            ) from exc

    def _ensure_model(self, model: str) -> None:
        try:
            response = requests.post(
                f"{self.base_url}/api/show",
                json={"model": model},
                timeout=30,
            )
            if response.status_code == 404:
                pull = requests.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model, "stream": False},
                    timeout=600,
                )
                pull.raise_for_status()
                return
            response.raise_for_status()
        except requests.RequestException as exc:
            raise OllamaError(f"Ollama could not prepare model '{model}': {exc}") from exc

    def embed(self, text: str) -> list[float]:
        try:
            response = self._post(
                "/api/embed",
                {"model": self.embedding_model, "input": text},
            )
            embeddings = response.get("embeddings")
            if isinstance(embeddings, list) and embeddings:
                values = embeddings[0]
            else:
                values = response.get("embedding")
            if not isinstance(values, list) or not values:
                raise OllamaError("Ollama returned no embedding values")
            if len(values) != 768:
                raise OllamaError(
                    f"Embedding model returned {len(values)} dimensions; "
                    "expected 768. Choose a 768-dimensional Ollama embedding model."
                )
            return [float(value) for value in values]
        except OllamaError:
            raise
        except requests.RequestException as exc:
            raise OllamaError(f"Ollama embedding request failed: {exc}") from exc

    def _json_request(
        self,
        prompt: str,
        max_tokens: int = 400,
        num_ctx: int = 4096,
        format_response: Any = "json",
        retries: int = 3,
    ) -> dict[str, Any]:
        for attempt in range(retries):
            response = self._post(
                "/api/generate",
                {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": format_response,
                    "think": False,
                    "options": {
                        "temperature": 0.05 if attempt == 0 else 0.1,
                        "num_ctx": num_ctx,
                        "num_predict": max_tokens,
                        "repeat_penalty": 1.15,
                        "repeat_last_n": 64,
                    },
                },
            )
            text = response.get("response")
            if not isinstance(text, str):
                raise OllamaError("Ollama returned an invalid response")
            try:
                return _parse_json(text)
            except OllamaError:
                if attempt == retries - 1:
                    raise

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(3):
            try:
                response = requests.post(
                    f"{self.base_url}{path}",
                    json=payload,
                    timeout=self.timeout,
                )
                if not response.ok:
                    detail = response.text.strip().replace("\n", " ")[:500]
                    raise OllamaError(
                        f"Ollama HTTP {response.status_code}: "
                        f"{detail or response.reason}"
                    )
                result = response.json()
                if not isinstance(result, dict):
                    raise OllamaError("Ollama returned invalid JSON")
                return result
            except requests.RequestException as exc:
                if attempt == 2:
                    raise
                time.sleep(2**attempt)
            except OllamaError:
                raise

    def extract_keywords(self, cv_text: str) -> list[str]:
        cv_excerpt = cv_text[:2500]
        keyword_schema = {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 12,
                }
            },
            "required": ["keywords"],
            "additionalProperties": False,
        }
        result = self._json_request(
            "Extract target job titles from this CV. Return JSON with exactly "
            'one field: {"keywords":["..."]}. The values must be 3-12 concise '
            "job-search titles, using titles that fit the candidate's actual field. "
            "Examples include Software Engineer, Full Stack Developer, SAP Consultant, "
            "Law Lecturer, Legal Advisor, Corporate Trainer, Data Analyst, or "
            "Human Resources Specialist. Do not return technologies, frameworks, tools, "
            "databases, products, certificates, or domains alone. Do not return generic words "
            "or explanations. Derive titles from the candidate's actual experience "
            "and target roles.\n"
            f"CV:\n{cv_excerpt}",
            max_tokens=200,
            num_ctx=2048,
            format_response=keyword_schema,
        )
        keywords = result.get("keywords")
        if not isinstance(keywords, list) or not all(
            isinstance(item, str) for item in keywords
        ):
            raise OllamaError("Ollama returned invalid keyword data")
        cleaned = _normalize_role_keywords(keywords, cv_text)
        if not cleaned:
            raise OllamaError("Ollama did not return any valid target job titles")
        return cleaned[:12]

    def generate_application(
        self, job: dict[str, Any], cv_chunks: list[str], master_cv_text: str
    ) -> tuple[str, dict[str, Any]]:
        retrieved_context = "\n\n---\n\n".join(cv_chunks)
        source_context = master_cv_text[:12000]
        response_schema = {
            "type": "object",
            "properties": {
                "cover_letter": {
                    "type": "string",
                    "minLength": 300,
                    "maxLength": 5000,
                },
                "rendercv_yaml": {
                    "type": "object",
                    "properties": {
                        "cv": {"type": "object"},
                        "design": {"type": "object"},
                    },
                    "required": ["cv"],
                    "additionalProperties": True,
                },
            },
            "required": ["cover_letter", "rendercv_yaml"],
            "additionalProperties": False,
        }
        result = self._json_request(
            "Create a tailored job application from the source CV and job description. "
            "Return JSON with exactly two fields: cover_letter and rendercv_yaml.\n\n"
            "COVER LETTER RULES:\n"
            "- Write 3-5 substantial professional paragraphs.\n"
            "- Use only facts supported by the source CV.\n"
            "- Do not invent employers, degrees, dates, projects, skills, or metrics.\n\n"
            "RENDERCV YAML RULES:\n"
            "- Return a RenderCV data object with a top-level cv object.\n"
            "- Tailor the CV to this job: change the headline, reorder sections and "
            "entries, select the most relevant experience and projects, and rewrite "
            "their summaries/highlights to emphasize requirements in the job.\n"
            "- Keep only truthful evidence from the source CV. Do not add facts that "
            "are absent from it.\n"
            "- Keep the candidate's real identity, contact details, education, and "
            "dates unless they are absent from the source.\n"
            "- Use only cv.sections.education, experience, projects, and skills. "
            "Education entries require institution and area. Experience entries "
            "require company and position. Project entries require name. Skills "
            "entries require label and details.\n"
            "- Do not return Markdown fences, explanations, or a YAML string; "
            "rendercv_yaml must be a JSON object.\n\n"
            f"JOB:\n{json.dumps(job, ensure_ascii=False)}\n"
            f"RETRIEVED RELEVANT CV EVIDENCE:\n{retrieved_context[:7000]}\n"
            f"FULL SOURCE CV:\n{source_context}",
            max_tokens=2200,
            num_ctx=8192,
            format_response=response_schema,
            retries=3,
        )
        cover_letter = result.get("cover_letter")
        if not isinstance(cover_letter, str) or len(cover_letter.strip()) < 300:
            raise OllamaError("Ollama returned an empty cover letter")
        rendercv_yaml = result.get("rendercv_yaml")
        if not isinstance(rendercv_yaml, dict) or not isinstance(
            rendercv_yaml.get("cv"), dict
        ):
            raise OllamaError("Ollama returned an invalid RenderCV document")
        _apply_deterministic_cv_identity(rendercv_yaml, master_cv_text)

        return cover_letter.strip(), rendercv_yaml


def _extract_master_phone(context: str) -> str:
    labeled_patterns = (
        r"(?:phone|t[eé]l[eé]phone|mobile)\s*[:\-]?\s*(\+?\d[\d\s().-]{6,}\d)",
    )
    candidates: list[str] = []
    for pattern in labeled_patterns:
        candidates.extend(re.findall(pattern, context, flags=re.IGNORECASE))

    for candidate in candidates:
        digits = re.sub(r"\D", "", candidate)
        if digits.startswith("216"):
            local = digits[3:]
        else:
            local = digits
            if local.startswith("00"):
                local = local[2:]
            if local.startswith("216"):
                local = local[3:]
        if len(local) == 8:
            formatted_local = f"{local[:2]} {local[2:5]} {local[5:]}"
            return f"+216 {formatted_local}"
    for candidate in re.findall(r"(?m)^\s*(\d{8})\s*$", context):
        digits = candidate
        formatted_local = f"{digits[:2]} {digits[2:5]} {digits[5:]}"
        return f"+216 {formatted_local}"
    return ""


def _apply_deterministic_cv_identity(rendercv_yaml: dict[str, Any], context: str) -> None:
    cv = rendercv_yaml.setdefault("cv", {})
    if not isinstance(cv, dict):
        return

    emails = re.findall(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        context,
        flags=re.IGNORECASE,
    )
    email = emails[0].strip() if emails else ""
    if email:
        cv["email"] = email
        local = email.split("@", 1)[0]
        parts = [part for part in re.split(r"[._+-]+", local) if part]
        if parts and all(part.lower() not in {"job", "cv"} for part in parts):
            cv["name"] = " ".join(part[:1].upper() + part[1:].lower() for part in parts)

    phone = _extract_master_phone(context)
    if phone:
        cv["phone"] = phone
    else:
        cv.pop("phone", None)

    links = re.findall(r"https://[^\s<>)]+", context)
    linkedin = next((link.rstrip(".,") for link in links if "linkedin.com" in link.lower()), "")
    github = next((link.rstrip(".,") for link in links if "github.com" in link.lower()), "")
    portfolio = next(
        (
            link.rstrip(".,")
            for link in links
            if "linkedin.com" not in link.lower()
            and "github.com" not in link.lower()
            and link.rstrip(".,") not in {linkedin, github}
        ),
        "",
    )
    social_networks = []
    if linkedin:
        social_networks.append({"network": "LinkedIn", "username": linkedin})
    if github:
        social_networks.append({"network": "GitHub", "username": github})
    if social_networks:
        cv["social_networks"] = social_networks
    if portfolio:
        cv["website"] = portfolio

    sections = cv.setdefault("sections", {})
    if not isinstance(sections, dict):
        cv["sections"] = {}
    if not cv["sections"]:
        cleaned_context = " ".join(context.split())
        summary = cleaned_context[:1800].strip()
        skills = []
        skill_names = (
            "React", "Carbon Design System", "Node.js", "Express.js",
            "Docker", "Redis", "RabbitMQ", "Keycloak", "Nginx",
            "Java", "Spring Boot", "Python", "JavaScript", "TypeScript",
            "PostgreSQL", "SAP", "Angular", "Vue.js",
        )
        context_lower = context.lower()
        for skill in skill_names:
            if skill.lower() in context_lower:
                skills.append(skill)
        cv["sections"] = {
            "summary": [summary] if summary else ["Professional experience from the master CV"],
        }
        if skills:
            cv["sections"]["skills"] = [
                {"label": "Technology", "details": ", ".join(skills)}
            ]


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end >= start:
        cleaned = cleaned[start : end + 1]
    result: Any = None
    try:
        result = json.loads(cleaned, strict=False)
    except json.JSONDecodeError:
        result = None
        for candidate_start in range(len(cleaned)):
            if cleaned[candidate_start] != "{":
                continue
            try:
                candidate_result, _ = json.JSONDecoder(strict=False).raw_decode(cleaned, candidate_start)
                if isinstance(candidate_result, dict):
                    result = candidate_result
                    break
            except json.JSONDecodeError:
                continue
    if not isinstance(result, dict):
        raise OllamaError("Ollama returned malformed JSON")
    if not isinstance(result, dict):
        raise OllamaError("Ollama response must be a JSON object")
    return result


TECH_ONLY_KEYWORDS = {
    "react",
    "angular",
    "vue",
    "node.js",
    "express.js",
    "spring boot",
    "docker",
    "redshift",
    "redis",
    "rabbitmq",
    "keycloak",
    "nginx",
    "javascript",
    "typescript",
    "python",
    "java",
    "sap",
    "mysql",
    "postgresql",
}

ROLE_TITLE_FALLBACKS = [
    "Software Engineer",
    "Full Stack Developer",
    "Backend Developer",
    "Frontend Developer",
    "SAP Consultant",
    "IT Consultant",
    "Web Developer",
]


def _normalize_role_keywords(keywords: list[str], cv_text: str) -> list[str]:
    role_markers = (
        " developer",
        " engineer",
        " consultant",
        " analyst",
        " architect",
        " manager",
        " administrator",
        " specialist",
        " programmer",
        " lecturer",
        " teacher",
        " trainer",
        " instructor",
        " advisor",
        " counsel",
        " lawyer",
        " researcher",
        " researcher",
        " officer",
        " coordinator",
        " assistant",
        " enseignant",
        " enseignante",
        " formatrice",
        " formateur",
        " juriste",
        " avocat",
        " avocate",
        " arbitre",
        " doctorante",
        " doctorant",
        " web",
        " software",
    )
    cleaned: list[str] = []
    cv_lower = cv_text.lower()
    for raw in keywords:
        value = " ".join(raw.strip().split())
        normalized = value.lower().rstrip(".")
        if not normalized or normalized in TECH_ONLY_KEYWORDS:
            continue
        canonical = _canonical_role_title(normalized)
        if canonical:
            value = canonical
        elif not any(marker in f" {normalized}" for marker in role_markers):
            continue
        if value not in cleaned:
            cleaned.append(value)

    if "react" in cv_lower or "angular" in cv_lower or "vue" in cv_lower:
        for title in ("Frontend Developer", "Full Stack Developer", "Web Developer"):
            if title not in cleaned:
                cleaned.append(title)
    if "node" in cv_lower or "spring" in cv_lower or "java" in cv_lower or "python" in cv_lower:
        for title in ("Software Engineer", "Backend Developer", "Full Stack Developer"):
            if title not in cleaned:
                cleaned.append(title)
    if "sap" in cv_lower:
        if "SAP Consultant" not in cleaned:
            cleaned.append("SAP Consultant")

    if any(token in cv_lower for token in ("droit", "juridique", "arbitrage", "juriste")):
        for title in (
            "Law Lecturer",
            "Legal Advisor",
            "Legal Consultant",
            "Law Researcher",
            "Arbitration Consultant",
        ):
            if title not in cleaned:
                cleaned.append(title)
    if any(token in cv_lower for token in (
        "enseignante",
        "enseignant",
        "formatrice",
        "formateur",
        "formation",
        "training",
        "soft skills",
    )):
        for title in (
            "Law Lecturer",
            "Corporate Trainer",
            "Employability Trainer",
            "Human Resources Trainer",
        ):
            if title not in cleaned:
                cleaned.append(title)

    if not cleaned:
        fallback_titles = [
            "Consultant",
            "Specialist",
            "Analyst",
            "Coordinator",
            "Manager",
        ]
        for title in fallback_titles:
            if title not in cleaned:
                cleaned.append(title)

    ordered: list[str] = []
    for title in ROLE_TITLE_FALLBACKS:
        if title in cleaned and title not in ordered:
            ordered.append(title)
    for title in cleaned:
        if title not in ordered:
            ordered.append(title)
    return ordered


def _canonical_role_title(normalized: str) -> str | None:
    if any(token in normalized for token in ("law lecturer", "droit", "legal teacher", "enseignante en droit", "enseignant en droit")):
        return "Law Lecturer"
    if "legal advisor" in normalized or "legal counsel" in normalized or "juriste" in normalized:
        return "Legal Advisor"
    if "legal consultant" in normalized or "consultant juridique" in normalized:
        return "Legal Consultant"
    if "law researcher" in normalized or "chercheur juridique" in normalized or "doctorante" in normalized:
        return "Law Researcher"
    if "arbitration" in normalized or "arbitre" in normalized:
        return "Arbitration Consultant"
    if "corporate trainer" in normalized or "formateur" in normalized or "formatrice" in normalized:
        return "Corporate Trainer"
    if "employability" in normalized:
        return "Employability Trainer"
    if "human resources trainer" in normalized:
        return "Human Resources Trainer"
    if "trainer" in normalized or "instructor" in normalized or "enseignante" in normalized or "enseignant" in normalized:
        return "Trainer"
    if "sap" in normalized:
        return "SAP Consultant"
    if "full stack" in normalized or "full-stack" in normalized:
        return "Full Stack Developer"
    if "frontend" in normalized or "front-end" in normalized:
        return "Frontend Developer"
    if "web developer" in normalized:
        return "Web Developer"
    if "backend" in normalized or "back-end" in normalized:
        return "Backend Developer"
    if "devops" in normalized:
        return "DevOps Engineer"
    if "software engineer" in normalized or "software developer" in normalized:
        return "Software Engineer"
    if "software" in normalized and "engineer" in normalized:
        return "Software Engineer"
    if "it consultant" in normalized:
        return "IT Consultant"
    if "solutions architect" in normalized:
        return "Solutions Architect"
    if "enterprise architect" in normalized:
        return "Enterprise Architect"
    if "software architect" in normalized:
        return "Software Architect"
    if "enterprise" in normalized and "architect" in normalized:
        return "Enterprise Architect"
    if "system architect" in normalized:
        return "System Architect"
    if "security specialist" in normalized:
        return "Security Specialist"
    if "web" in normalized and "developer" in normalized:
        return "Web Developer"
    if "data engineer" in normalized:
        return "Data Engineer"
    if "qa" in normalized or "quality assurance" in normalized:
        return "QA Engineer"
    if "project manager" in normalized:
        return "Project Manager"
    if "product manager" in normalized:
        return "Product Manager"
    return None
