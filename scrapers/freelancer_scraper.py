"""
Scraper do Freelancer.com.

Uso seguro: navegue no Chrome já aberto com sessão logada e rode via CDP.
Os seletores são genéricos e tolerantes a variações de DOM.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from .base import PersistentScraper, Project

BASE_URL = "https://www.freelancer.com"
FREELANCER_SEARCH_URLS = [
    "https://www.freelancer.com/jobs/search/?keywords=python+excel+power+bi+sql",
    "https://www.freelancer.com/jobs/search/?keywords=python+automation+etl",
    "https://www.freelancer.com/jobs/search/?keywords=data+analysis+dashboard",
]

DEBUG_DUMP = False


def _normalize_space(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _absolute_url(href: str | None) -> str:
    if not href:
        return ""
    return urljoin(BASE_URL, href.strip())


def _clean_project_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _project_id_from_url(url: str, fallback: str) -> str:
    match = re.search(r"-(\d+)(?:\?|/)?$", _clean_project_url(url))
    if match:
        return match.group(1)
    path = urlparse(url).path.rstrip("/")
    if path:
        return path.split("/")[-1]
    return re.sub(r"\W+", "_", fallback.lower()).strip("_")[:80]


def _dump_debug(page: Page, name: str = "freelancer_dump.html") -> None:
    if not DEBUG_DUMP:
        return
    try:
        with open(name, "w", encoding="utf-8") as f:
            f.write(page.content())
    except Exception:
        pass


def _extract_projects(page: Page) -> list[Project]:
    _dump_debug(page)

    link_cards = []
    links = page.query_selector_all("a[href*='/projects/']")

    for link in links:
        card = link.evaluate_handle(
            """
            el => el.closest('article, li, .JobSearchCard-item, .job-tile, .ProjectCard, .job-card, .JobCard') || el.parentElement
            """
        ).as_element()
        if card and card not in link_cards:
            link_cards.append(card)

    projects: list[Project] = []
    seen: set[str] = set()

    for card in link_cards:
        title_el = card.query_selector("a[href*='/projects/']")
        if not title_el:
            continue

        raw_url = title_el.get_attribute("href")
        url = _clean_project_url(_absolute_url(raw_url))
        title = _normalize_space(title_el.inner_text())
        if not title or not url:
            continue

        project_id = _project_id_from_url(url, title)
        unique_id = f"freelancer_{project_id}"
        if unique_id in seen:
            continue
        seen.add(unique_id)

        desc_el = card.query_selector(".Job-description, .JobSearchCard-description, .project-description, .project-tile__description, p, span")
        description = _normalize_space(desc_el.inner_text()) if desc_el else ""

        skills = []
        skill_els = card.query_selector_all(".Job-skills a, .JobSkills-item, .project-tags__item, .job-tags a, .badge")
        for s in skill_els:
            text = _normalize_space(s.inner_text())
            if text:
                skills.append(text)

        budget_text = ""
        budget_match = re.search(r"(?:R\$|US\$)\s*[\d\.]+(?:,\d{2})?", card.inner_text())
        if budget_match:
            budget_text = budget_match.group(0)

        badge_el = card.query_selector(".badge-premium, .badge-featured, .job-card__badge, .featured, .paid-promotion")
        is_free_to_bid = badge_el is None

        projects.append(
            Project(
                id=unique_id,
                platform="freelancer",
                title=title,
                url=url,
                description=description,
                budget_text=budget_text,
                is_free_to_bid=is_free_to_bid,
                skills=skills,
            )
        )

    return projects


def scrape_freelancer(mode: str = "auto") -> list[Project]:
    all_projects: list[Project] = []
    last_error = None

    with PersistentScraper("freelancer", mode=mode, headless=False) as page:
        for url in FREELANCER_SEARCH_URLS:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except PlaywrightTimeoutError:
                    pass

                try:
                    page.wait_for_selector("a[href*='/projects/']", timeout=15000)
                except PlaywrightTimeoutError:
                    _dump_debug(page, "freelancer_sem_cards.html")

                batch = _extract_projects(page)
                if batch:
                    all_projects.extend(batch)
                    break
            except Exception as exc:
                last_error = exc
                continue

    deduped: dict[str, Project] = {p.id: p for p in all_projects}
    projects = list(deduped.values())

    if not projects and last_error:
        raise RuntimeError(f"Não consegui coletar projetos do Freelancer.com. Último erro: {last_error}") from last_error

    return projects


if __name__ == "__main__":
    for proj in scrape_freelancer():
        print(proj)
