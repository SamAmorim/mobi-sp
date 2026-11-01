"""Enrichment: malha de transporte por imóvel (metrô, CPTM, ônibus)."""

from __future__ import annotations

import logging

from config import BUS_RADIUS_M, CPTM_RADIUS_M, METRO_RADIUS_M
from db.connection import db_cursor, fetchall

logger = logging.getLogger(__name__)

RADII = {
    "metro": METRO_RADIUS_M,
    "cptm": CPTM_RADIUS_M,
    "onibus": BUS_RADIUS_M,
}


def enrich_transport() -> int:
    """Calcula vínculos imóvel↔linha e agregados em imovel_features. Retorna n imóveis."""
    imoveis = fetchall("SELECT id FROM imoveis WHERE geom IS NOT NULL")
    if not imoveis:
        logger.warning("Nenhum imóvel com geom para enriquecer.")
        return 0

    with db_cursor() as cur:
        # Limpa vínculos anteriores
        cur.execute("DELETE FROM imovel_linhas_transporte")

        for modo, radius in RADII.items():
            cur.execute(
                """
                INSERT INTO imovel_linhas_transporte (imovel_id, linha_id, ponto_id, distancia_m)
                SELECT DISTINCT ON (i.id, lt.id)
                    i.id,
                    lt.id,
                    p.id,
                    ST_Distance(i.geom, p.geom) AS distancia_m
                FROM imoveis i
                JOIN pontos_transporte p ON p.modo = %s
                JOIN ponto_linhas pl ON pl.ponto_id = p.id
                JOIN linhas_transporte lt ON lt.id = pl.linha_id AND lt.modo = %s
                WHERE i.geom IS NOT NULL
                  AND ST_DWithin(i.geom, p.geom, %s)
                ORDER BY i.id, lt.id, ST_Distance(i.geom, p.geom)
                ON CONFLICT (imovel_id, linha_id) DO UPDATE SET
                    ponto_id = EXCLUDED.ponto_id,
                    distancia_m = EXCLUDED.distancia_m
                """,
                (modo, modo, radius),
            )

        # Agrega features por imóvel
        for row in imoveis:
            imovel_id = int(row["id"])
            feats = _aggregate_features(cur, imovel_id)
            cur.execute(
                """
                INSERT INTO imovel_features (
                    imovel_id,
                    dist_metro_m, estacao_metro_proxima, linha_metro_proxima,
                    n_linhas_metro_raio, linhas_metro_proximas,
                    dist_cptm_m, estacao_cptm_proxima,
                    n_linhas_cptm_raio, linhas_cptm_proximas,
                    dist_parada_mais_proxima_m, n_paradas_300m,
                    n_linhas_onibus_500m, linhas_onibus_proximas,
                    malha_resumo, atualizado_em
                ) VALUES (
                    %(imovel_id)s,
                    %(dist_metro_m)s, %(estacao_metro_proxima)s, %(linha_metro_proxima)s,
                    %(n_linhas_metro_raio)s, %(linhas_metro_proximas)s,
                    %(dist_cptm_m)s, %(estacao_cptm_proxima)s,
                    %(n_linhas_cptm_raio)s, %(linhas_cptm_proximas)s,
                    %(dist_parada_mais_proxima_m)s, %(n_paradas_300m)s,
                    %(n_linhas_onibus_500m)s, %(linhas_onibus_proximas)s,
                    %(malha_resumo)s, NOW()
                )
                ON CONFLICT (imovel_id) DO UPDATE SET
                    dist_metro_m = EXCLUDED.dist_metro_m,
                    estacao_metro_proxima = EXCLUDED.estacao_metro_proxima,
                    linha_metro_proxima = EXCLUDED.linha_metro_proxima,
                    n_linhas_metro_raio = EXCLUDED.n_linhas_metro_raio,
                    linhas_metro_proximas = EXCLUDED.linhas_metro_proximas,
                    dist_cptm_m = EXCLUDED.dist_cptm_m,
                    estacao_cptm_proxima = EXCLUDED.estacao_cptm_proxima,
                    n_linhas_cptm_raio = EXCLUDED.n_linhas_cptm_raio,
                    linhas_cptm_proximas = EXCLUDED.linhas_cptm_proximas,
                    dist_parada_mais_proxima_m = EXCLUDED.dist_parada_mais_proxima_m,
                    n_paradas_300m = EXCLUDED.n_paradas_300m,
                    n_linhas_onibus_500m = EXCLUDED.n_linhas_onibus_500m,
                    linhas_onibus_proximas = EXCLUDED.linhas_onibus_proximas,
                    malha_resumo = EXCLUDED.malha_resumo,
                    atualizado_em = NOW()
                """,
                feats,
            )

    logger.info("Transporte enriquecido para %s imóveis", len(imoveis))
    return len(imoveis)


def _aggregate_features(cur, imovel_id: int) -> dict:
    def lines_for(modo: str) -> list[dict]:
        cur.execute(
            """
            SELECT lt.codigo, p.nome AS ponto, ilt.distancia_m
            FROM imovel_linhas_transporte ilt
            JOIN linhas_transporte lt ON lt.id = ilt.linha_id
            LEFT JOIN pontos_transporte p ON p.id = ilt.ponto_id
            WHERE ilt.imovel_id = %s AND lt.modo = %s
            ORDER BY ilt.distancia_m
            """,
            (imovel_id, modo),
        )
        return list(cur.fetchall())

    metro = lines_for("metro")
    cptm = lines_for("cptm")
    bus = lines_for("onibus")

    def fmt(rows: list[dict], n: int = 5) -> str | None:
        if not rows:
            return None
        return ", ".join(
            f"{r['codigo']} ({int(r['distancia_m'])}m via {r['ponto']})" for r in rows[:n]
        )

    cur.execute(
        """
        SELECT COUNT(*) AS n
        FROM pontos_transporte p
        JOIN imoveis i ON i.id = %s
        WHERE p.modo = 'onibus' AND ST_DWithin(i.geom, p.geom, 300)
        """,
        (imovel_id,),
    )
    n_paradas_300 = int(cur.fetchone()["n"])

    malha_parts = []
    if metro:
        malha_parts.append("metrô: " + fmt(metro, 3))
    if cptm:
        malha_parts.append("CPTM: " + fmt(cptm, 2))
    if bus:
        malha_parts.append("ônibus: " + fmt(bus, 3))

    return {
        "imovel_id": imovel_id,
        "dist_metro_m": metro[0]["distancia_m"] if metro else None,
        "estacao_metro_proxima": metro[0]["ponto"] if metro else None,
        "linha_metro_proxima": metro[0]["codigo"] if metro else None,
        "n_linhas_metro_raio": len(metro),
        "linhas_metro_proximas": fmt(metro),
        "dist_cptm_m": cptm[0]["distancia_m"] if cptm else None,
        "estacao_cptm_proxima": cptm[0]["ponto"] if cptm else None,
        "n_linhas_cptm_raio": len(cptm),
        "linhas_cptm_proximas": fmt(cptm),
        "dist_parada_mais_proxima_m": bus[0]["distancia_m"] if bus else None,
        "n_paradas_300m": n_paradas_300,
        "n_linhas_onibus_500m": len(bus),
        "linhas_onibus_proximas": fmt(bus),
        "malha_resumo": " | ".join(malha_parts) if malha_parts else None,
    }
