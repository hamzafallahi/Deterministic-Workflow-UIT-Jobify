"""HTTP scraper for Tanitjobs postings."""

from __future__ import annotations

from dataclasses import dataclass
from email.utils import parseaddr
import logging
import re
from typing import Iterable
from time import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .config import settings

LOGGER = logging.getLogger(__name__)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.IGNORECASE)


class ScraperError(RuntimeError):
    """Raised when a Tanitjobs request or response cannot be processed."""


@dataclass(frozen=True)
class JobPosting:
    title: str
    company: str
    location: str
    description: str
    url: str
    recruiter_email: str | None = None
    posted_at: str | None = None


class TanitjobsScraper:
    """Fetch recent Tanitjobs listings without relying on browser automation."""

    def __init__(
        self,
        search_url: str = settings.tanitjobs_search_url,
        timeout_seconds: int = settings.scraper_timeout_seconds,
        session: requests.Session | None = None,
    ) -> None:
        self.search_url = search_url
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Jobify/0.1 (+https://www.tanitjobs.com; "
                    "job-search assistant)"
                ),
                "Accept-Language": "en-US,en;q=0.8,fr;q=0.6",
            }
        )

    def search(self, keywords: Iterable[str], limit: int | None = None) -> list[JobPosting]:
        """Return postings for one search phrase."""
        terms = [term.strip() for term in keywords if term and term.strip()]
        if not terms:
            raise ValueError("At least one non-empty search keyword is required")
        requested_limit = limit if limit is not None else settings.scraper_max_jobs
        if requested_limit <= 0:
            raise ValueError("limit must be greater than zero")

        if len(terms) > 1:
            raise ValueError("Tanitjobs search accepts one selected keyword at a time")
        response = self._get(
            self.search_url,
            params={
                "listing_type[equal]": "Job",
                "searchId": f"{time():.4f}",
                "action": "search",
                "keywords[all_words]": terms[0],
                "GooglePlace[location][value]": "",
                "GooglePlace[location][radius]": "50",
            },
        )
        soup = BeautifulSoup(response.text, "html.parser")
        links = self._listing_links(soup)
        jobs: list[JobPosting] = []
        for url in links[:40]:
            if len(jobs) >= requested_limit:
                break
            try:
                job = self._parse_job(url)
                if self._matches_search_term(job, terms[0]):
                    jobs.append(job)
            except ScraperError:
                LOGGER.warning("Skipping malformed Tanitjobs listing: %s", url)
        return jobs

    @staticmethod
    def _matches_search_term(job: JobPosting, term: str) -> bool:
        text = f"{job.title} {job.description}".lower()
        term_lower = term.lower().strip()
        frontend_terms = ("frontend", "front-end", "react", "angular", "vue", "javascript")
        if term_lower in {"frontend developer", "front-end developer", "web developer"}:
            return any(item in text for item in frontend_terms)
        if term_lower in {"backend developer", "back-end developer"}:
            return any(item in text for item in (
                "backend", "back-end", "java", "python", "node", "spring",
                "api", "server",
            ))
        if term_lower == "sap consultant":
            return "sap" in text
        if term_lower in {"software engineer", "full stack developer", "it consultant"}:
            words = [word for word in re.findall(r"[a-z][a-z0-9+#.-]*", term_lower) if len(word) >= 3]
            if term_lower == "software engineer":
                return any(item in text for item in ("software engineer", "software developer", "développeur", "developer"))
            if term_lower == "full stack developer":
                return any(item in text for item in ("full stack", "full-stack", "développeur", "developer"))
            if term_lower == "it consultant":
                return any(item in text for item in ("consultant", "consulting", "it "))
            return bool(words)
        return term_lower in text

    def _get(self, url: str, *, params: dict[str, str] | None = None) -> requests.Response:
        try:
            response = self.session.get(url, params=params, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise ScraperError(f"Unable to fetch Tanitjobs page: {url}") from exc
        if response.status_code == 429:
            raise ScraperError("Tanitjobs rate limit reached (HTTP 429)")
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise ScraperError(f"Tanitjobs returned HTTP {response.status_code}") from exc
        return response

    def _listing_links(self, soup: BeautifulSoup) -> list[str]:
        links: list[str] = []
        seen: set[str] = set()
        anchors = soup.select(".sj-card-title a[href]")
        if not anchors:
            anchors = soup.select("a[href]")
        for anchor in anchors:
            href = anchor.get("href", "").strip()
            label = anchor.get_text(" ", strip=True)
            if not href or not label or len(label) < 3:
                continue
            absolute_url = urljoin(self.search_url, href)
            parsed = urlparse(absolute_url)
            if parsed.netloc != urlparse(self.search_url).netloc:
                continue
            if absolute_url in seen or absolute_url.rstrip("/") == self.search_url.rstrip("/"):
                continue
            if not parsed.path.lower().startswith("/job/"):
                continue
            seen.add(absolute_url)
            links.append(absolute_url)
        return links

    def _parse_job(self, url: str) -> JobPosting:
        soup = BeautifulSoup(self._get(url).text, "html.parser")
        title = self._text(soup, ["h1", "meta[property='og:title']"])
        description = self._text(
            soup,
            ["[class*='description']", "[id*='description']", "main", "article"],
        )
        if not title or not description:
            raise ScraperError(f"Missing title or description in listing: {url}")
        company = self._text(soup, ["[class*='company']", "[id*='company']"]) or ""
        location = self._text(soup, ["[class*='location']", "[id*='location']"]) or ""
        posted_at = self._text(
            soup, ["time", "[class*='date']", "[class*='published']"]
        )
        return JobPosting(
            title=title,
            company=company,
            location=location,
            description=description,
            url=url,
            recruiter_email=self._find_email(soup.get_text(" ", strip=True)),
            posted_at=posted_at,
        )

    @staticmethod
    def _text(soup: BeautifulSoup, selectors: list[str]) -> str:
        for selector in selectors:
            node = soup.select_one(selector)
            if node is None:
                continue
            value = node.get("content") if node.name == "meta" else node.get_text(" ", strip=True)
            if value:
                return " ".join(value.split())
        return ""

    @staticmethod
    def _find_email(text: str) -> str | None:
        for candidate in EMAIL_RE.findall(text):
            address = parseaddr(candidate)[1].lower()
            if address:
                return address
        return None
