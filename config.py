"""Configuração central do Mobi-SP (mapear São Paulo)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
FIXTURES_DIR = DATA_DIR / "fixtures"
RAW_DIR = DATA_DIR / "raw"

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://mobi:mobi@localhost:5432/mobi_sp"
)
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() in {"1", "true", "yes"}
TIPOS_INGESTAO = [
    t.strip().lower()
    for t in os.getenv("TIPOS_INGESTAO", "casa,apartamento,sobrado").split(",")
    if t.strip()
]
ITBI_URL = os.getenv("ITBI_URL", "")

# Raios da malha (metros)
BUS_RADIUS_M = float(os.getenv("BUS_RADIUS_M", "500"))
METRO_RADIUS_M = float(os.getenv("METRO_RADIUS_M", "1500"))
CPTM_RADIUS_M = float(os.getenv("CPTM_RADIUS_M", "2000"))
AMENITY_RADIUS_M = float(os.getenv("AMENITY_RADIUS_M", "500"))

# Bounding box aproximado do município de São Paulo (validação)
SP_BBOX = {
    "lat_min": -23.95,
    "lat_max": -23.35,
    "lon_min": -46.85,
    "lon_max": -46.35,
}


def ponto_dentro_sp(lat: float | None, lon: float | None) -> bool | None:
    if lat is None or lon is None:
        return None
    return (
        SP_BBOX["lat_min"] <= lat <= SP_BBOX["lat_max"]
        and SP_BBOX["lon_min"] <= lon <= SP_BBOX["lon_max"]
    )
