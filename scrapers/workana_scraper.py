"""
Scraper do Workana com tolerância a falhas por card.
"""

from __future__ import annotations

from urllib.parse import urljoin

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from .base import PersistentScraper, Project


WORKANA_URL = (
    "https://www.workana.com/jobs"
    "?category=it-programming"
    "&language=pt"
    "&skills=microsoft-excel,python,sql,vba"
)

DEBUG_DUMP = False

CARD_SELECTORS = [
    "div.project-item",
    "div.project",
    "article",
    "[data-testid*='project']",
    "li[class*='project']",
]

LINK_SELECTORS = [
    "a[href*='/job/']",
    "a[href*='/jobs/']",
]


def _safe_text(locator, timeout: int = 2000) -> str:
    try:
        return (locator.text_content(timeout=timeout) or "").strip()
    except Exception:
        return ""


def _safe_attr(locator, attribute: str) -> str:
    try:
        return locator.get_attribute(attribute) or ""
    except Exception:
        return ""


def _save_debug(page: Page, page_number: int) -> None:
    if not DEBUG_DUMP:
        return

    try:
        with open(
            f"workana_dump_pagina_{page_number}.html",
            "w",
            encoding="utf-8",
        ) as file:
            file.write(page.content())
    except Exception:
        pass

    try:
        page.screenshot(
            path=f"workana_dump_pagina_{page_number}.png",
            full_page=True,
        )
    except Exception:
        pass


def _find_first_selector(page: Page, selectors: list[str]) -> str | None:
    for selector in selectors:
        try:
            if page.locator(selector).count() > 0:
                return selector
        except Exception:
            continue

    return None


def _extract_projects(
    page: Page,
    page_number: int,
) -> list[Project]:
    projects: list[Project] = []
    urls_seen: set[str] = set()

    try:
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2500)

        link_selector = _find_first_selector(page, LINK_SELECTORS)

        if not link_selector:
            _save_debug(page, page_number)
            print("Nenhum link de projeto foi encontrado.")
            return []

        card_selector = _find_first_selector(page, CARD_SELECTORS)

        if card_selector:
            cards = page.locator(card_selector)
        else:
            cards = page.locator(link_selector)

        total_cards = cards.count()

        print(
            f"Workana página {page_number}: "
            f"{total_cards} cards encontrados"
        )

        for index in range(total_cards):
            try:
                card = cards.nth(index)

                if card_selector:
                    link_el = card.locator(link_selector).first
                else:
                    link_el = card

                if link_el.count() == 0:
                    continue

                href = _safe_attr(link_el, "href")

                if not href:
                    continue

                url = urljoin(
                    "https://www.workana.com",
                    href,
                )

                if url in urls_seen:
                    continue

                title = _safe_text(link_el)

                if not title:
                    title = _safe_attr(link_el, "title")

                if not title:
                    title = "Projeto sem título"

                description = ""
                budget_text = ""
                skills: list[str] = []
                card_text = ""

                if card_selector:
                    desc_el = card.locator(
                        ".project-details, "
                        ".html-desc, "
                        ".description, "
                        "[class*='description']"
                    ).first

                    if desc_el.count() > 0:
                        description = _safe_text(
                            desc_el,
                            timeout=2000,
                        )

                    budget_el = card.locator(
                        ".budget, "
                        ".project-budget, "
                        "[class*='budget'], "
                        "[class*='price']"
                    ).first

                    if budget_el.count() > 0:
                        budget_text = _safe_text(
                            budget_el,
                            timeout=2000,
                        )

                    skill_els = card.locator(
                        ".skills a, "
                        ".skill-tag, "
                        "[class*='skill']"
                    )

                    skill_count = min(
                        skill_els.count(),
                        20,
                    )

                    for skill_index in range(skill_count):
                        skill = _safe_text(
                            skill_els.nth(skill_index),
                            timeout=1000,
                        )

                        if skill and skill not in skills:
                            skills.append(skill)

                    card_text = _safe_text(
                        card,
                        timeout=2000,
                    ).lower()

                is_free_to_bid = not any(
                    word in card_text
                    for word in (
                        "destacado",
                        "premium",
                        "featured",
                    )
                )

                project_id = (
                    href.rstrip("/").split("/")[-1]
                    or title
                )

                projects.append(
                    Project(
                        id=f"workana_{project_id}",
                        platform="workana",
                        title=title,
                        url=url,
                        description=description,
                        budget_text=budget_text,
                        is_free_to_bid=is_free_to_bid,
                        skills=skills,
                    )
                )

                urls_seen.add(url)

            except PlaywrightTimeoutError as error:
                print(
                    f"Card {index + 1} ignorado por timeout: "
                    f"{error}"
                )
                continue

            except Exception as error:
                print(
                    f"Card {index + 1} ignorado: "
                    f"{error}"
                )
                continue

        _save_debug(page, page_number)

        print(
            f"Workana página {page_number}: "
            f"{len(projects)} projetos extraídos"
        )

        return projects

    except PlaywrightTimeoutError as error:
        _save_debug(page, page_number)
        print(f"Timeout geral na Workana: {error}")
        return projects

    except Exception as error:
        _save_debug(page, page_number)
        print(f"Erro geral ao extrair Workana: {error}")
        return projects


def scrape_workana(
    max_pages: int = 3,
    mode: str = "auto",
) -> list[Project]:
    all_projects: list[Project] = []
    seen_ids: set[str] = set()

    with PersistentScraper(
        "workana",
        mode=mode,
    ) as page:
        page.set_default_timeout(5000)

        for page_number in range(
            1,
            max_pages + 1,
        ):
            url = f"{WORKANA_URL}&page={page_number}"

            print(
                f"→ Abrindo Workana: "
                f"página {page_number}"
            )

            try:
                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                if response:
                    print(
                        f"Status HTTP: "
                        f"{response.status}"
                    )

                    if response.status == 403:
                        print(
                            "Workana bloqueou a página "
                            "com HTTP 403."
                        )
                        break

                print(f"URL carregada: {page.url}")
                print(
                    f"Título da página: "
                    f"{page.title()}"
                )

                batch = _extract_projects(
                    page,
                    page_number,
                )

                if not batch:
                    print(
                        "Nenhum projeto encontrado "
                        f"na página {page_number}."
                    )
                    break

                added = 0

                for project in batch:
                    if project.id in seen_ids:
                        continue

                    seen_ids.add(project.id)
                    all_projects.append(project)
                    added += 1

                print(
                    f"Página {page_number}: "
                    f"{added} novos projetos"
                )

            except PlaywrightTimeoutError as error:
                _save_debug(page, page_number)

                print(
                    "A página demorou demais para "
                    f"carregar: {error}"
                )

                continue

            except Exception as error:
                _save_debug(page, page_number)

                print(
                    "Erro ao processar a página "
                    f"{page_number}: {error}"
                )

                continue

    print(
        f"Total Workana: "
        f"{len(all_projects)} projetos"
    )

    return all_projects


if __name__ == "__main__":
    projects = scrape_workana(
        max_pages=1,
        mode="cdp",
    )

    for project in projects:
        print(project)

    print(
        f"Total encontrado: "
        f"{len(projects)}"
    )
