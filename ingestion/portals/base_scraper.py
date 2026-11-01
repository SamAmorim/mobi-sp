"""
Scraper base com Playwright (interceptação de rede/JSON) + BeautifulSoup.

No MVP o fluxo padrão é DEMO_MODE / fixtures. Playwright fica pronto para
portal real, com rate-limit e sem bypass de CAPTCHA/WAF.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from bs4 import BeautifulSoup

from config import DEMO_MODE, FIXTURES_DIR, TIPOS_INGESTAO
from ingestion.base import Listing, listing_from_dict

logger = logging.getLogger(__name__)


class BasePortalScraper(ABC):
    fonte: str = "portal"
    fixture_name: str = "listings_demo.json"
    request_delay_s: float = 1.5

    def __init__(self, demo: Optional[bool] = None) -> None:
        self.demo = DEMO_MODE if demo is None else demo

    def run(self) -> list[Listing]:
        if self.demo:
            logger.info("[%s] DEMO_MODE — carregando fixtures", self.fonte)
            return self.load_fixture()
        try:
            return self.scrape_live()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] Falha no scrape ao vivo (%s). Usando fixture.",
                self.fonte,
                exc,
            )
            return self.load_fixture()

    def load_fixture(self) -> list[Listing]:
        path = FIXTURES_DIR / self.fixture_name
        with path.open(encoding="utf-8") as f:
            raw_list = json.load(f)
        listings: list[Listing] = []
        for raw in raw_list:
            try:
                item = listing_from_dict(self.fonte, raw)
            except ValueError as exc:
                logger.warning("Ignorando anúncio inválido: %s", exc)
                continue
            if item.tipo_imovel not in TIPOS_INGESTAO:
                continue
            listings.append(item)
        return listings

    @abstractmethod
    def scrape_live(self) -> list[Listing]:
        """Implementação específica do portal (Playwright + parse)."""

    def intercept_json_listings(
        self,
        start_url: str,
        url_substring: str = "/api/",
        timeout_ms: int = 45000,
    ) -> list[dict[str, Any]]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright não instalado. Use DEMO_MODE ou instale playwright."
            ) from exc

        captured: list[dict[str, Any]] = []

        def on_response(response) -> None:
            try:
                if url_substring not in response.url:
                    return
                ctype = response.headers.get("content-type") or ""
                if "application/json" not in ctype:
                    return
                captured.append({"url": response.url, "data": response.json()})
            except Exception:  # noqa: BLE001
                return

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="MobiSP-ResearchBot/0.1 (+pesquisa educacional SP)"
            )
            page = context.new_page()
            page.on("response", on_response)
            page.goto(start_url, wait_until="networkidle", timeout=timeout_ms)
            time.sleep(self.request_delay_s)
            html = page.content()
            browser.close()

        if not captured:
            soup = BeautifulSoup(html, "lxml")
            return self.parse_html_listings(soup)
        return self.parse_api_payloads(captured)

    def parse_api_payloads(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return []

    def parse_html_listings(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        return []
