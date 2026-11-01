"""
Adaptador de portal (padrão VivaReal/Zap).

No MVP o fluxo padrão é DEMO_MODE + fixtures.
scrape_live() permanece como esqueleto com interceptação de rede.
"""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from ingestion.base import Listing, listing_from_dict
from ingestion.portals.base_scraper import BasePortalScraper

logger = logging.getLogger(__name__)

# Seletores centralizados (ajuste quando o layout do portal mudar)
SELECTORS = {
    "card": "[data-type='property'], .property-card",
    "title": "h2, .property-card__title",
    "price": ".property-card__price, [data-type='price']",
}


class VivaRealScraper(BasePortalScraper):
    fonte = "vivareal"
    fixture_name = "listings_demo.json"

    def scrape_live(self) -> list[Listing]:
        # URL ilustrativa — substitua por busca real com filtros de SP
        start_url = (
            "https://www.vivareal.com.br/venda/sp/sao-paulo/"
            "?tipos=casa,apartamento,sobrado"
        )
        raw_cards = self.intercept_json_listings(start_url, url_substring="/api/")
        listings: list[Listing] = []
        for raw in raw_cards:
            try:
                listings.append(listing_from_dict(self.fonte, raw))
            except ValueError as exc:
                logger.warning("Card ignorado: %s", exc)
        return listings

    def parse_api_payloads(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extrai listagens de payloads JSON interceptados (estrutura varia por portal)."""
        out: list[dict[str, Any]] = []
        for item in payloads:
            data = item.get("data") or {}
            # Tentativas comuns de caminhos em APIs de listagem
            candidates = []
            if isinstance(data, list):
                candidates = data
            elif isinstance(data, dict):
                for key in ("search", "listings", "results", "hits"):
                    node = data.get(key)
                    if isinstance(node, dict) and "result" in node:
                        candidates = node.get("result") or []
                        break
                    if isinstance(node, list):
                        candidates = node
                        break
            for c in candidates:
                mapped = self._map_api_card(c)
                if mapped:
                    out.append(mapped)
        return out

    def parse_html_listings(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for i, card in enumerate(soup.select(SELECTORS["card"])):
            title_el = card.select_one(SELECTORS["title"])
            price_el = card.select_one(SELECTORS["price"])
            out.append(
                {
                    "id_externo": f"html-{i}",
                    "titulo": title_el.get_text(strip=True) if title_el else None,
                    "preco": _parse_price(price_el.get_text() if price_el else None),
                    "tipo_imovel": "apartamento",
                    "bairro": None,
                }
            )
        return out

    def _map_api_card(self, card: Any) -> dict[str, Any] | None:
        if not isinstance(card, dict):
            return None
        listing = card.get("listing") or card
        ext_id = listing.get("id") or listing.get("listingId")
        if not ext_id:
            return None
        pricing = listing.get("pricingInfos") or [{}]
        price = None
        if pricing and isinstance(pricing, list):
            price = pricing[0].get("price")
        address = listing.get("address") or {}
        return {
            "id_externo": str(ext_id),
            "titulo": listing.get("title") or listing.get("name"),
            "tipo_imovel": (listing.get("unitTypes") or ["apartamento"])[0],
            "bairro": address.get("neighborhood") or address.get("district"),
            "distrito": address.get("district") or address.get("neighborhood"),
            "endereco": address.get("street"),
            "preco": price,
            "area_m2": (listing.get("usableAreas") or [None])[0],
            "quartos": (listing.get("bedrooms") or [None])[0],
            "banheiros": (listing.get("bathrooms") or [None])[0],
            "vagas": (listing.get("parkingSpaces") or [None])[0],
            "lat": (address.get("point") or {}).get("lat"),
            "lon": (address.get("point") or {}).get("lon"),
            "url": (listing.get("link") or {}).get("href"),
        }


def _parse_price(text: str | None) -> float | None:
    if not text:
        return None
    digits = "".join(c for c in text if c.isdigit())
    return float(digits) if digits else None
