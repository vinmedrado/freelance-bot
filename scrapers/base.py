import os
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILES_DIR = Path(__file__).parent.parent / ".browser_profiles"


@dataclass
class Project:
    id: str
    platform: str
    title: str
    url: str
    description: str = ""
    budget_text: str = ""
    is_free_to_bid: bool = True
    skills: list = field(default_factory=list)


class PersistentScraper:
    def __init__(self, platform: str, headless: bool = True, mode: str = "cdp"):
        self.platform = platform
        self.headless = headless
        self.mode = mode
        self.profile_dir = PROFILES_DIR / platform
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._is_cdp = False

    def __enter__(self):
        self._pw = sync_playwright().start()

        if self.mode in ("cdp", "auto"):
            cdp_url = os.getenv("CHROME_CDP_URL", "http://127.0.0.1:9222")
            try:
                self._browser = self._pw.chromium.connect_over_cdp(cdp_url)
                self._context = (
                    self._browser.contexts[0]
                    if self._browser.contexts
                    else self._browser.new_context()
                )
                self._page = self._context.new_page()
                self._is_cdp = True
                print(f"✓ Chrome conectado via CDP: {cdp_url}")
                return self._page
            except Exception as e:
                if self.mode == "cdp":
                    self._pw.stop()
                    raise RuntimeError(
                        f"Não consegui conectar no Chrome em {cdp_url}. "
                        "Abra o Chrome com --remote-debugging-port=9222 ou use mode='auto'."
                    ) from e
                print("CDP indisponível. Abrindo perfil persistente...")

        if self.mode in ("profile", "isolated", "auto"):
            self._context = self._pw.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                channel="chrome",
                headless=self.headless,
                viewport={"width": 1440, "height": 900},
                locale="pt-BR",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-gpu",
                    "--disable-gpu-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            self._page = (
                self._context.pages[0]
                if self._context.pages
                else self._context.new_page()
            )
            return self._page

        self._pw.stop()
        raise RuntimeError(f"Modo inválido: {self.mode}")

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._page:
                self._page.close()
        except Exception:
            pass

        if not self._is_cdp:
            try:
                if self._context:
                    self._context.close()
            except Exception:
                pass

        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass


def first_login_setup(platform: str, login_url: str):
    with PersistentScraper(platform, headless=False, mode="profile") as page:
        page.goto(login_url)
        input(f"[{platform}] Faça login e pressione ENTER...")
