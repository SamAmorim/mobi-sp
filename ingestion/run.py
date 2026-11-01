"""Orquestra ingestão da camada mercado (anúncios + ITBI + leilões)."""

from __future__ import annotations

import logging

from db.connection import resolve_distrito_id, upsert_imovel
from ingestion.auctions import load_auctions
from ingestion.itbi_loader import load_itbi
from ingestion.portals.vivareal import VivaRealScraper

logger = logging.getLogger(__name__)


def run_ingestion(demo: bool = True) -> dict:
    scraper = VivaRealScraper(demo=demo)
    listings = scraper.run()
    n_listings = 0
    for item in listings:
        distrito_id = resolve_distrito_id(item.distrito)
        upsert_imovel(item.to_db_row(distrito_id=distrito_id))
        n_listings += 1

    n_itbi = load_itbi(demo=demo)
    n_auctions = load_auctions(demo=True)  # leilões: esqueleto sempre via fixture no MVP

    summary = {
        "anuncios": n_listings,
        "itbi": n_itbi,
        "leiloes": n_auctions,
    }
    logger.info("Ingestão concluída: %s", summary)
    return summary
