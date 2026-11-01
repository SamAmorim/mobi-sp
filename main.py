#!/usr/bin/env python3
"""
Mobi-SP — pipeline para mapear São Paulo.

Camada cidade  → distritos + malha metrô/CPTM/ônibus
Camada mercado → ITBI + anúncios (casa/apartamento/sobrado) + leilões (esqueleto)

Uso:
  python main.py --demo --step all
  python main.py --resumo-cidade
  python main.py --filter --tipo casa --tem-jardim --linha-metro 2-Verde
  python main.py --filter --tem-quintal --distrito Saúde
  python main.py --filter --espaco-externo --linha-onibus 875A-10
"""

from __future__ import annotations

import argparse
import logging
import sys

from config import DEMO_MODE


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Mobi-SP — mapear São Paulo")
    p.add_argument(
        "--step",
        choices=["all", "seed", "ingest", "spatial", "filter", "resumo", "validate"],
        default="all",
        help="Etapa do pipeline (default: all)",
    )
    p.add_argument("--demo", action="store_true", help="Força fixtures (sem scrape/download)")
    p.add_argument("--resumo-cidade", action="store_true", help="Imprime cobertura da cidade")
    p.add_argument(
        "--validate-fixtures",
        action="store_true",
        help="Valida fixtures da cidade sem precisar do PostgreSQL/Docker",
    )

    # Filtros
    p.add_argument("--filter", action="store_true", help="Executa consulta filtrada")
    p.add_argument("--tipo", choices=["casa", "apartamento", "sobrado"])
    p.add_argument("--distrito")
    p.add_argument("--bairro")
    p.add_argument("--min-quartos", type=int)
    p.add_argument("--min-area", type=float)
    p.add_argument("--min-preco", type=float)
    p.add_argument("--max-preco", type=float)
    p.add_argument("--tem-jardim", action="store_true")
    p.add_argument("--tem-quintal", action="store_true")
    p.add_argument("--espaco-externo", action="store_true",
                   help="jardim OU quintal OU varanda OU sacada")
    p.add_argument("--tem-elevador", action="store_true")
    p.add_argument("--max-condominio", type=float)
    p.add_argument("--min-vagas", type=int)
    p.add_argument("--linha-metro", help="Ex.: 2-Verde")
    p.add_argument("--linha-cptm", help="Ex.: 9-Esmeralda")
    p.add_argument("--linha-onibus", help="Ex.: 875A-10")
    p.add_argument("--max-dist-metro", type=float)
    p.add_argument("--max-dist-onibus", type=float)
    p.add_argument("--max-dist-parada", type=float)
    p.add_argument("--min-linhas-onibus", type=int)
    p.add_argument("--tag")
    p.add_argument("--limit", type=int, default=50)
    return p


def run_seed() -> None:
    from spatial.city_seed import seed_city

    seed_city()


def run_ingest(demo: bool) -> None:
    from ingestion.run import run_ingestion

    run_ingestion(demo=demo)


def run_spatial() -> None:
    from spatial.amenities import enrich_amenities
    from spatial.historico import refresh_historico_precos
    from spatial.transport import enrich_transport

    enrich_transport()
    enrich_amenities()
    refresh_historico_precos()


def run_filter(args: argparse.Namespace) -> None:
    from query.filters import filter_imoveis, print_results

    rows = filter_imoveis(
        tipo=args.tipo,
        distrito=args.distrito,
        bairro=args.bairro,
        min_quartos=args.min_quartos,
        max_preco=args.max_preco,
        min_preco=args.min_preco,
        min_area=args.min_area,
        tem_jardim=args.tem_jardim or None,
        tem_quintal=args.tem_quintal or None,
        espaco_externo=args.espaco_externo or None,
        tem_elevador=args.tem_elevador or None,
        max_condominio=args.max_condominio,
        min_vagas=args.min_vagas,
        linha_metro=args.linha_metro,
        linha_cptm=args.linha_cptm,
        linha_onibus=args.linha_onibus,
        max_dist_metro=args.max_dist_metro,
        max_dist_onibus=args.max_dist_onibus,
        max_dist_parada=args.max_dist_parada,
        min_linhas_onibus=args.min_linhas_onibus,
        tag=args.tag,
        limit=args.limit,
    )
    print_results(rows)


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = build_parser().parse_args(argv)
    demo = True if args.demo else DEMO_MODE

    if args.validate_fixtures or args.step == "validate":
        from spatial.validate_fixtures import print_validation, validate_city_fixtures

        summary = validate_city_fixtures()
        print_validation(summary)
        return 0 if summary["ok"] else 1

    if args.resumo_cidade or args.step == "resumo":
        from query.resumo import resumo_cidade

        resumo_cidade()
        return 0

    if args.filter or args.step == "filter":
        run_filter(args)
        return 0

    if args.step in ("seed", "all"):
        run_seed()
    if args.step in ("ingest", "all"):
        run_ingest(demo=demo)
    if args.step in ("spatial", "all"):
        run_spatial()

    if args.step == "all":
        from query.resumo import resumo_cidade

        resumo_cidade()

    return 0


if __name__ == "__main__":
    sys.exit(main())
