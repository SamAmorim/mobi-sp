"""Filtros tipados sobre imóveis + malha de transporte."""

from __future__ import annotations

from typing import Any, Optional

from db.connection import fetchall


def filter_imoveis(
    *,
    tipo: Optional[str] = None,
    distrito: Optional[str] = None,
    bairro: Optional[str] = None,
    min_quartos: Optional[int] = None,
    max_preco: Optional[float] = None,
    min_preco: Optional[float] = None,
    min_area: Optional[float] = None,
    tem_jardim: Optional[bool] = None,
    tem_quintal: Optional[bool] = None,
    espaco_externo: Optional[bool] = None,
    tem_elevador: Optional[bool] = None,
    max_condominio: Optional[float] = None,
    min_vagas: Optional[int] = None,
    linha_metro: Optional[str] = None,
    linha_cptm: Optional[str] = None,
    linha_onibus: Optional[str] = None,
    max_dist_metro: Optional[float] = None,
    max_dist_onibus: Optional[float] = None,
    max_dist_parada: Optional[float] = None,
    min_linhas_onibus: Optional[int] = None,
    tag: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    joins = [
        "FROM imoveis i",
        "LEFT JOIN distritos d ON d.id = i.distrito_id",
        "LEFT JOIN imovel_features f ON f.imovel_id = i.id",
    ]
    clauses = ["1=1"]
    join_params: list[Any] = []
    where_params: list[Any] = []

    def add_w(clause: str, *vals: Any) -> None:
        clauses.append(clause)
        where_params.extend(vals)

    if tipo:
        add_w("i.tipo_imovel = %s::tipo_imovel_enum", tipo)
    if distrito:
        add_w("lower(d.nome) = lower(%s)", distrito)
    if bairro:
        add_w("i.bairro ILIKE %s", f"%{bairro}%")
    if min_quartos is not None:
        add_w("i.quartos >= %s", min_quartos)
    if max_preco is not None:
        add_w("i.preco <= %s", max_preco)
    if min_preco is not None:
        add_w("i.preco >= %s", min_preco)
    if min_area is not None:
        add_w("i.area_m2 >= %s", min_area)
    if tem_jardim:
        add_w("i.tem_jardim IS TRUE")
    if tem_quintal:
        add_w("i.tem_quintal IS TRUE")
    if espaco_externo:
        add_w("i.tem_espaco_externo IS TRUE")
    if tem_elevador:
        add_w("i.tem_elevador IS TRUE")
    if max_condominio is not None:
        add_w("i.valor_condominio <= %s", max_condominio)
    if min_vagas is not None:
        add_w("i.vagas >= %s", min_vagas)
    if max_dist_metro is not None:
        add_w("f.dist_metro_m <= %s", max_dist_metro)
    if max_dist_parada is not None:
        add_w("f.dist_parada_mais_proxima_m <= %s", max_dist_parada)
    if min_linhas_onibus is not None:
        add_w("f.n_linhas_onibus_500m >= %s", min_linhas_onibus)
    if tag:
        add_w("i.caracteristicas->'tags' ? %s", tag)

    if linha_metro:
        joins.append(
            "JOIN imovel_linhas_transporte ilm ON ilm.imovel_id = i.id "
            "JOIN linhas_transporte ltm ON ltm.id = ilm.linha_id "
            "AND ltm.modo = 'metro' AND ltm.codigo = %s"
        )
        join_params.append(linha_metro)
    if linha_cptm:
        joins.append(
            "JOIN imovel_linhas_transporte ilc ON ilc.imovel_id = i.id "
            "JOIN linhas_transporte ltc ON ltc.id = ilc.linha_id "
            "AND ltc.modo = 'cptm' AND ltc.codigo = %s"
        )
        join_params.append(linha_cptm)
    if linha_onibus:
        joins.append(
            "JOIN imovel_linhas_transporte ilo ON ilo.imovel_id = i.id "
            "JOIN linhas_transporte lto ON lto.id = ilo.linha_id "
            "AND lto.modo = 'onibus' AND lto.codigo = %s"
        )
        join_params.append(linha_onibus)
        if max_dist_onibus is not None:
            add_w("ilo.distancia_m <= %s", max_dist_onibus)

    sql = f"""
        SELECT DISTINCT
            i.id, i.tipo_imovel, d.nome AS distrito, i.bairro,
            i.preco, i.area_m2, i.quartos, i.vagas,
            i.tem_jardim, i.tem_quintal, i.tem_espaco_externo, i.tem_elevador,
            f.dist_metro_m, f.linhas_metro_proximas,
            f.linhas_cptm_proximas, f.linhas_onibus_proximas,
            f.malha_resumo
        {' '.join(joins)}
        WHERE {' AND '.join(clauses)}
        ORDER BY i.preco NULLS LAST
        LIMIT %s
    """
    return fetchall(sql, join_params + where_params + [limit])


def print_results(rows: list[dict]) -> None:
    if not rows:
        print("Nenhum imóvel encontrado.")
        return
    print(
        f"{'id':>4} {'tipo':12} {'distrito':16} {'preço':>12} "
        f"{'m²':>6} {'jardim':6} {'quintal':7} malha"
    )
    print("-" * 110)
    for r in rows:
        print(
            f"{r['id']:>4} {r['tipo_imovel']:12} {(r.get('distrito') or '-'):16} "
            f"{float(r['preco'] or 0):>12,.0f} {float(r['area_m2'] or 0):>6.0f} "
            f"{str(r.get('tem_jardim')):6} {str(r.get('tem_quintal')):7} "
            f"{(r.get('malha_resumo') or '')[:55]}"
        )
