"""Densidade de comércio, parques e escolas em raio configurável."""

from __future__ import annotations

import logging

from config import AMENITY_RADIUS_M
from db.connection import db_cursor, fetchall

logger = logging.getLogger(__name__)


def enrich_amenities(radius_m: float | None = None) -> int:
    radius = radius_m or AMENITY_RADIUS_M
    imoveis = fetchall("SELECT id FROM imoveis WHERE geom IS NOT NULL")
    with db_cursor() as cur:
        for row in imoveis:
            imovel_id = int(row["id"])
            counts = {}
            for cat in ("comercio", "parque", "escola"):
                cur.execute(
                    """
                    SELECT COUNT(*) AS n
                    FROM amenities a
                    JOIN imoveis i ON i.id = %s
                    WHERE a.categoria = %s AND ST_DWithin(i.geom, a.geom, %s)
                    """,
                    (imovel_id, cat, radius),
                )
                counts[cat] = int(cur.fetchone()["n"])
            score = counts["comercio"] * 1.0 + counts["parque"] * 2.0 + counts["escola"] * 1.5
            cur.execute(
                """
                INSERT INTO imovel_features (
                    imovel_id, n_comercios_500m, n_parques_500m, n_escolas_500m,
                    score_infra_500m, atualizado_em
                ) VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (imovel_id) DO UPDATE SET
                    n_comercios_500m = EXCLUDED.n_comercios_500m,
                    n_parques_500m = EXCLUDED.n_parques_500m,
                    n_escolas_500m = EXCLUDED.n_escolas_500m,
                    score_infra_500m = EXCLUDED.score_infra_500m,
                    atualizado_em = NOW()
                """,
                (
                    imovel_id,
                    counts["comercio"],
                    counts["parque"],
                    counts["escola"],
                    score,
                ),
            )
    logger.info("Amenities enriquecidos para %s imóveis (raio=%sm)", len(imoveis), radius)
    return len(imoveis)
