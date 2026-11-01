"""Ingestão leve de leilões (esqueleto MVP — fase 2 pode expandir)."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from config import FIXTURES_DIR
from db.connection import resolve_distrito_id, upsert_imovel
from ingestion.base import listing_from_dict

logger = logging.getLogger(__name__)


def load_auctions(demo: bool = True) -> int:
    path = FIXTURES_DIR / "auctions_demo.csv"
    if not path.exists():
        logger.warning("Fixture de leilões ausente: %s", path)
        return 0

    df = pd.read_csv(path)
    count = 0
    for _, row in df.iterrows():
        raw = row.to_dict()
        raw["id_externo"] = str(raw.get("id_externo"))
        raw["preco"] = raw.get("preco_leilao")
        raw["distrito"] = raw.get("distrito") or raw.get("bairro")
        raw["metadados"] = {"origem": "leilao"}
        try:
            listing = listing_from_dict("leilao", raw)
        except ValueError as exc:
            logger.warning("Leilão ignorado: %s", exc)
            continue
        distrito_id = resolve_distrito_id(listing.distrito)
        upsert_imovel(listing.to_db_row(distrito_id=distrito_id))
        count += 1
    logger.info("Leilões: %s registros", count)
    return count
