"""Carga ITBI — ground truth de preços transacionados em São Paulo."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from config import FIXTURES_DIR, ITBI_URL, RAW_DIR, ponto_dentro_sp
from db.connection import db_cursor, resolve_distrito_id
from ingestion.base import normalize_tipo

logger = logging.getLogger(__name__)


def load_itbi(demo: bool = True, url: Optional[str] = None) -> int:
    """
    Baixa/lê ITBI e grava em transacoes_itbi.
    Retorna quantidade de linhas inseridas.
    """
    path = _resolve_source(demo=demo, url=url or ITBI_URL)
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    colmap = {
        "inscricao": _first(df, ["inscricao", "inscrição", "sql"]),
        "distrito": _first(df, ["distrito"]),
        "bairro": _first(df, ["bairro", "bairro_imovel"]),
        "valor": _first(df, ["valor_transacao", "valor", "valor_venal"]),
        "area": _first(df, ["area_m2", "area", "área"]),
        "data": _first(df, ["data_transacao", "data", "data_transacao"]),
        "tipo": _first(df, ["tipo_imovel", "tipo", "tipo_imovel"]),
        "lat": _first(df, ["lat", "latitude"]),
        "lon": _first(df, ["lon", "longitude", "lng"]),
    }

    inserted = 0
    with db_cursor() as cur:
        for _, row in df.iterrows():
            tipo = normalize_tipo(row.get(colmap["tipo"])) if colmap["tipo"] else None
            distrito_nome = row.get(colmap["distrito"]) if colmap["distrito"] else None
            if distrito_nome is None and colmap["bairro"]:
                distrito_nome = row.get(colmap["bairro"])
            distrito_id = resolve_distrito_id(str(distrito_nome) if pd.notna(distrito_nome) else None)

            lat = _f(row.get(colmap["lat"])) if colmap["lat"] else None
            lon = _f(row.get(colmap["lon"])) if colmap["lon"] else None
            # Validação geográfica (log; ainda assim grava)
            if ponto_dentro_sp(lat, lon) is False:
                logger.warning("ITBI fora do bbox SP: %s", row.get(colmap["inscricao"]))

            cur.execute(
                """
                INSERT INTO transacoes_itbi (
                    inscricao, distrito_id, bairro, valor_transacao, area_m2,
                    data_transacao, tipo_imovel, geom, fonte_arquivo
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    CASE WHEN %s IS NOT NULL AND %s IS NOT NULL
                         THEN ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                         ELSE NULL END,
                    %s
                )
                """,
                (
                    str(row.get(colmap["inscricao"])) if colmap["inscricao"] else None,
                    distrito_id,
                    str(row.get(colmap["bairro"])) if colmap["bairro"] and pd.notna(row.get(colmap["bairro"])) else None,
                    _f(row.get(colmap["valor"])) if colmap["valor"] else None,
                    _f(row.get(colmap["area"])) if colmap["area"] else None,
                    row.get(colmap["data"]) if colmap["data"] else None,
                    tipo,
                    lon,
                    lat,
                    lon,
                    lat,
                    path.name,
                ),
            )
            inserted += 1
    logger.info("ITBI: %s transações carregadas de %s", inserted, path.name)
    return inserted


def _resolve_source(demo: bool, url: str) -> Path:
    fixture = FIXTURES_DIR / "itbi_demo.csv"
    if demo or not url:
        return fixture
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DIR / "itbi_download.csv"
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return dest
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha no download ITBI (%s). Usando fixture.", exc)
        return fixture


def _first(df: pd.DataFrame, names: list[str]) -> Optional[str]:
    for n in names:
        if n in df.columns:
            return n
    return None


def _f(v) -> Optional[float]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
