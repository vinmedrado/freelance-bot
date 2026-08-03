"""
Scraper do 99Freelas.

Estratégia segura:
- Usa a sua própria sessão autenticada do navegador.
- Lê apenas páginas que você consegue acessar logado.
- Não burla captcha, login, paywall, limite, bloqueio ou regra da plataforma.

Recomendado:
    1) Abra o Chrome com CDP:
       chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\\chrome-ml"

    2) Faça login normalmente no 99Freelas nesse Chrome.

    3) Rode:
       python main.py --plataforma 99freelas

Fallback antigo com profile isolado:
    python -c "from scrapers.base import first_login_setup; first_login_setup('99freelas', 'https://www.99freelas.com.br/login')"
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from .base import PersistentScraper, Project

BASE_URL = "https://www.99freelas.com.br"

# A página de notificações funciona quando a conta está logada, mas pode vir vazia
# dependendo das preferências/notificações. A busca é um fallback mais estável.
FREELAS_URLS = [
    "https://www.99freelas.com.br/project-notifications/view?limit=500",
    "https://www.99freelas.com.br/search/projects?search=python%20excel%20power%20bi%20sql&limit=50",
    "https://www.99freelas.com.br/search/projects?search=planilha%20excel%20dashboard%20automacao&limit=50",
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
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _project_id_from_url(url: str, fallback: str) -> str:
    match = re.search(r"-(\d+)(?:\?|/)?$", _clean_project_url(url))
    if match:
        return match.group(1)
    path = urlparse(url).path.rstrip("/")
    if path:
        return path.split("/")[-1]
    return re.sub(r"\W+", "_", fallback.lower()).strip("_")[:80]


def _is_login_or_blocked_page(page: Page) -> bool:
    current_url = page.url.lower()
    title = (page.title() or "").lower()
    body_text = _normalize_space(page.locator("body").inner_text(timeout=3000)).lower()

    login_markers = [
        "/login",
        "/cadastro",
        "entrar",
        "login",
        "criar conta",
        "acesse sua conta",
        "faça login",
    ]
    blocked_markers = [
        "captcha",
        "verifique que você não é um robô",
        "access denied",
        "acesso negado",
    ]

    if any(marker in current_url for marker in ["/login", "/cadastro", "/signup"]):
        return True
    if any(marker in title for marker in login_markers + blocked_markers):
        return True
    if any(marker in body_text for marker in blocked_markers):
        return True
    return False


def _dump_debug(page: Page, name: str = "freelas99_dump.html") -> None:
    if not DEBUG_DUMP:
        return
    try:
        with open(name, "w", encoding="utf-8") as f:
            f.write(page.content())
    except Exception:
        pass


def _extract_projects(page: Page) -> list[Project]:
    """Extrai cards do 99Freelas com seletores tolerantes a variações."""
    _dump_debug(page)

    if _is_login_or_blocked_page(page):
        raise RuntimeError(
            "O 99Freelas abriu tela de login/bloqueio em vez da lista de projetos. "
            "Abra o Chrome com --remote-debugging-port=9222, faça login manualmente "
            "e rode novamente usando mode='cdp'."
        )

    # Primeiro tenta o card oficial da página de notificações.
    cards = page.query_selector_all("li.result-item, .result-list li.result-item")

    # Fallback para páginas de busca/variações: pega blocos próximos de links de projeto.
    if not cards:
        link_cards = []
        links = page.query_selector_all("a[href*='/project/']")
        for link in links:
            card = link.evaluate_handle(
                """
                el => el.closest('li, article, .result-item, .project-item, .card, .item') || el.parentElement
                """
            ).as_element()
            if card and card not in link_cards:
                link_cards.append(card)
        cards = link_cards

    projects: list[Project] = []
    seen: set[str] = set()

    for card in cards:
        title_el = card.query_selector(".title a[href*='/project/'], a.notification-link[href*='/project/'], a[href*='/project/']")
        if not title_el:
            continue

        raw_url = title_el.get_attribute("href")
        url = _clean_project_url(_absolute_url(raw_url))
        title = _normalize_space(title_el.inner_text())
        if not title or not url:
            continue

        project_id = _project_id_from_url(url, title)
        unique_id = f"99freelas_{project_id}"
        if unique_id in seen:
            continue
        seen.add(unique_id)

        desc_el = card.query_selector(".description, .descricao, .project-description, .summary")
        description = _normalize_space(desc_el.inner_text()) if desc_el else ""

        info_el = card.query_selector(".information, .info, .metadata")
        info_text = _normalize_space(info_el.inner_text()) if info_el else ""

        skill_els = card.query_selector_all(".habilidades a.habilidade, .skills a, .skill-tag, a[href*='skill']")
        skills = [_normalize_space(s.inner_text()) for s in skill_els if _normalize_space(s.inner_text())]

        # Na listagem do 99Freelas normalmente não há orçamento. Quando aparecer,
        # capturamos sem depender disso para o robô funcionar.
        budget_text = ""
        budget_match = re.search(r"R\$\s*[\d\.]+(?:,\d{2})?", card.inner_text())
        if budget_match:
            budget_text = budget_match.group(0)

        # Projeto exclusivo não significa impossível de propor; só deixa metadado
        # para você filtrar depois, caso queira.
        is_exclusive = card.query_selector(".flags img[alt*='exclusivo' i], img[alt*='Projeto exclusivo' i]") is not None

        full_description = description
        if info_text and info_text not in description:
            full_description = f"{info_text}\n{description}".strip()
        if is_exclusive:
            full_description = f"[Projeto exclusivo]\n{full_description}".strip()

        projects.append(
            Project(
                id=unique_id,
                platform="99freelas",
                title=title,
                url=url,
                description=full_description,
                budget_text=budget_text,
                is_free_to_bid=True,
                skills=skills,
            )
        )

    return projects


def scrape_99freelas(mode: str = "auto") -> list[Project]:
    all_projects: list[Project] = []
    last_error: Exception | None = None

    with PersistentScraper("99freelas", mode=mode, headless=False) as page:
        for url in FREELAS_URLS:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except PlaywrightTimeoutError:
                    pass

                try:
                    page.wait_for_selector("li.result-item, a[href*='/project/']", timeout=15000)
                except PlaywrightTimeoutError:
                    _dump_debug(page, "freelas99_sem_cards.html")

                batch = _extract_projects(page)
                all_projects.extend(batch)

                # Se a página de notificações já trouxe projetos, não precisa bater nas buscas.
                if batch:
                    break
            except Exception as exc:
                last_error = exc
                continue

    # Deduplicação final entre notificações e busca.
    deduped: dict[str, Project] = {p.id: p for p in all_projects}
    projects = list(deduped.values())

    if not projects and last_error:
        raise RuntimeError(f"Não consegui coletar projetos do 99Freelas. Último erro: {last_error}") from last_error

    return projects


if __name__ == "__main__":
    for proj in scrape_99freelas():
        print(proj)
