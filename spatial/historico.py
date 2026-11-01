"""Agrega mediana de R$/m² por distrito × tipo × mês (mapa de preços, sem ML)."""

from __future__ import annotations

import logging

from db.connection import db_cursor

logger = logging.getLogger(__name__)


def refresh_historico_precos() -> int:
    with db_cursor() as cur:
        cur.execute("DELETE FROM historico_precos")
        cur.execute(
            """
            INSERT INTO historico_precos (
                distrito_id, bairro, tipo_imovel, mes_ref, preco_m2_mediano, n_amostras, fonte
            )
            SELECT
                distrito_id,
                COALESCE(bairro, '') AS bairro,
                tipo_imovel,
                date_trunc('month', data_transacao)::date AS mes_ref,
                percentile_cont(0.5) WITHIN GROUP (
                    ORDER BY valor_transacao / NULLIF(area_m2, 0)
                ) AS preco_m2_mediano,
                COUNT(*) AS n_amostras,
                'itbi' AS fonte
            FROM transacoes_itbi
            WHERE valor_transacao IS NOT NULL
              AND area_m2 IS NOT NULL AND area_m2 > 0
              AND data_transacao IS NOT NULL
              AND tipo_imovel IS NOT NULL
            GROUP BY distrito_id, COALESCE(bairro, ''), tipo_imovel,
                     date_trunc('month', data_transacao)
            """
        )
        cur.execute(
            """
            INSERT INTO historico_precos (
                distrito_id, bairro, tipo_imovel, mes_ref, preco_m2_mediano, n_amostras, fonte
            )
            SELECT
                distrito_id,
                COALESCE(bairro, '') AS bairro,
                tipo_imovel,
                date_trunc('month', scraped_at)::date AS mes_ref,
                percentile_cont(0.5) WITHIN GROUP (ORDER BY preco_m2) AS preco_m2_mediano,
                COUNT(*) AS n_amostras,
                'anuncio' AS fonte
            FROM imoveis
            WHERE preco_m2 IS NOT NULL AND tipo_imovel IS NOT NULL
            GROUP BY distrito_id, COALESCE(bairro, ''), tipo_imovel,
                     date_trunc('month', scraped_at)
            ON CONFLICT (distrito_id, bairro, tipo_imovel, mes_ref, fonte) DO UPDATE SET
                preco_m2_mediano = EXCLUDED.preco_m2_mediano,
                n_amostras = EXCLUDED.n_amostras
            """
        )
        cur.execute("SELECT COUNT(*) AS n FROM historico_precos")
        n = int(cur.fetchone()["n"])
    logger.info("historico_precos atualizado: %s linhas", n)
    return n
