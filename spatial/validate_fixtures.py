"""
Validação offline da camada cidade (sem PostgreSQL/Docker).

Garante que fixtures de distritos e malha metrô/CPTM/ônibus estão
consistentes antes do seed no PostGIS.
"""

from __future__ import annotations

import json
import logging
from collections import Counter

from config import FIXTURES_DIR

logger = logging.getLogger(__name__)


def validate_city_fixtures() -> dict:
    distritos_path = FIXTURES_DIR / "distritos_sp.json"
    transporte_path = FIXTURES_DIR / "transporte_sp.json"
    listings_path = FIXTURES_DIR / "listings_demo.json"

    distritos = json.loads(distritos_path.read_text(encoding="utf-8"))
    transporte = json.loads(transporte_path.read_text(encoding="utf-8"))
    listings = json.loads(listings_path.read_text(encoding="utf-8"))

    errors: list[str] = []
    warnings: list[str] = []

    nomes_dist = {d["nome"] for d in distritos}
    if len(nomes_dist) != len(distritos):
        errors.append("Distritos com nome duplicado")

    for d in distritos:
        if "lat" not in d or "lon" not in d:
            errors.append(f"Distrito sem coordenadas: {d.get('nome')}")

    linhas = transporte.get("linhas") or []
    pontos = transporte.get("pontos") or []
    codes = {(ln["modo"], ln["codigo"]) for ln in linhas}
    by_modo = Counter(ln["modo"] for ln in linhas)

    if by_modo.get("metro", 0) < 1:
        errors.append("Nenhuma linha de metrô na fixture")
    if by_modo.get("cptm", 0) < 1:
        errors.append("Nenhuma linha CPTM na fixture")
    if by_modo.get("onibus", 0) < 1:
        warnings.append("Nenhuma linha de ônibus na fixture")

    for pt in pontos:
        modo = pt.get("modo")
        for cod in pt.get("linhas") or []:
            if (modo, cod) not in codes:
                # fallback por código único
                if not any(c == cod for _, c in codes):
                    errors.append(f"Ponto {pt.get('nome')}: linha {cod} inexistente")

    for item in listings:
        dist = item.get("distrito") or item.get("bairro")
        if dist and dist not in nomes_dist:
            warnings.append(f"Listing {item.get('id_externo')}: distrito '{dist}' fora do seed")

    summary = {
        "distritos": len(distritos),
        "linhas": dict(by_modo),
        "pontos": len(pontos),
        "listings": len(listings),
        "errors": errors,
        "warnings": warnings,
        "ok": len(errors) == 0,
    }
    if errors:
        for e in errors:
            logger.error("Fixture: %s", e)
    for w in warnings:
        logger.warning("Fixture: %s", w)
    logger.info(
        "Fixtures OK=%s | distritos=%s linhas=%s pontos=%s",
        summary["ok"],
        summary["distritos"],
        summary["linhas"],
        summary["pontos"],
    )
    return summary


def print_validation(summary: dict) -> None:
    print("\n=== Validação offline (sem Docker) ===")
    print(f"Distritos: {summary['distritos']}")
    print(f"Linhas:    {summary['linhas']}")
    print(f"Pontos:    {summary['pontos']}")
    print(f"Listings:  {summary['listings']}")
    if summary["warnings"]:
        print("Avisos:")
        for w in summary["warnings"]:
            print(f"  - {w}")
    if summary["errors"]:
        print("Erros:")
        for e in summary["errors"]:
            print(f"  - {e}")
    else:
        print("Status: fixtures da camada cidade consistentes.")
    print()
