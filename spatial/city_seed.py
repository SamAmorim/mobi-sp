"""Carrega a camada cidade: distritos + malha metrô/CPTM/ônibus (+ amenities leves)."""

from __future__ import annotations

import json
import logging

from config import FIXTURES_DIR
from db.connection import db_cursor

logger = logging.getLogger(__name__)


def seed_city() -> dict:
    from spatial.validate_fixtures import validate_city_fixtures

    check = validate_city_fixtures()
    if not check["ok"]:
        raise RuntimeError(f"Fixtures inválidas: {check['errors']}")

    n_dist = seed_distritos()
    n_linhas, n_pontos = seed_transporte()
    n_amen = seed_amenities()
    summary = {
        "distritos": n_dist,
        "linhas": n_linhas,
        "pontos": n_pontos,
        "amenities": n_amen,
        "linhas_por_modo": check["linhas"],
    }
    logger.info("Seed cidade: %s", summary)
    return summary


def seed_distritos() -> int:
    path = FIXTURES_DIR / "distritos_sp.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    with db_cursor() as cur:
        for d in data:
            cur.execute(
                """
                INSERT INTO distritos (nome, zona, geom, fonte)
                VALUES (
                    %s, %s,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    'fixture'
                )
                ON CONFLICT (nome) DO UPDATE SET
                    zona = EXCLUDED.zona,
                    geom = EXCLUDED.geom
                """,
                (d["nome"], d.get("zona"), d["lon"], d["lat"]),
            )
    return len(data)


def seed_transporte() -> tuple[int, int]:
    path = FIXTURES_DIR / "transporte_sp.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    linhas = payload.get("linhas") or []
    pontos = payload.get("pontos") or []

    codigo_to_id: dict[tuple[str, str], int] = {}
    with db_cursor() as cur:
        # Re-seed idempotente das fixtures de transporte
        cur.execute("DELETE FROM imovel_linhas_transporte")
        cur.execute("DELETE FROM ponto_linhas")
        cur.execute("DELETE FROM pontos_transporte WHERE fonte = 'fixture'")

        for ln in linhas:
            cur.execute(
                """
                INSERT INTO linhas_transporte (codigo, nome, modo, cor, destino, tipo_linha, fonte)
                VALUES (%s, %s, %s, %s, %s, %s, 'fixture')
                ON CONFLICT (modo, codigo) DO UPDATE SET
                    nome = EXCLUDED.nome,
                    cor = EXCLUDED.cor,
                    destino = EXCLUDED.destino,
                    tipo_linha = EXCLUDED.tipo_linha
                RETURNING id, modo, codigo
                """,
                (
                    ln["codigo"],
                    ln.get("nome"),
                    ln["modo"],
                    ln.get("cor"),
                    ln.get("destino"),
                    ln.get("tipo_linha"),
                ),
            )
            row = cur.fetchone()
            codigo_to_id[(row["modo"], row["codigo"])] = int(row["id"])

        # Recarrega mapa se ON CONFLICT não retornou em algum edge case
        cur.execute("SELECT id, modo, codigo FROM linhas_transporte")
        for row in cur.fetchall():
            codigo_to_id[(row["modo"], row["codigo"])] = int(row["id"])

        n_pontos = 0
        for pt in pontos:
            modo = pt["modo"]
            cur.execute(
                """
                INSERT INTO pontos_transporte (nome, endereco, modo, geom, fonte)
                VALUES (
                    %s, %s, %s,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    'fixture'
                )
                RETURNING id
                """,
                (pt.get("nome"), pt.get("endereco"), modo, pt["lon"], pt["lat"]),
            )
            ponto_id = int(cur.fetchone()["id"])
            n_pontos += 1
            for cod in pt.get("linhas") or []:
                linha_id = codigo_to_id.get((modo, cod))
                # ônibus/metrô: modo do ponto deve bater com a linha
                if linha_id is None:
                    # tenta achar só pelo código (ex.: tipagem)
                    cur.execute(
                        "SELECT id FROM linhas_transporte WHERE codigo = %s LIMIT 1",
                        (cod,),
                    )
                    r = cur.fetchone()
                    linha_id = int(r["id"]) if r else None
                if linha_id is None:
                    logger.warning("Linha não encontrada para ponto %s: %s", pt.get("nome"), cod)
                    continue
                cur.execute(
                    """
                    INSERT INTO ponto_linhas (ponto_id, linha_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (ponto_id, linha_id),
                )
    return len(linhas), n_pontos


def seed_amenities() -> int:
    path = FIXTURES_DIR / "amenities_demo.json"
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    with db_cursor() as cur:
        cur.execute("DELETE FROM amenities WHERE fonte = 'fixture'")
        for a in data:
            cur.execute(
                """
                INSERT INTO amenities (nome, categoria, geom, fonte)
                VALUES (
                    %s, %s,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    'fixture'
                )
                """,
                (a.get("nome"), a["categoria"], a["lon"], a["lat"]),
            )
    return len(data)
