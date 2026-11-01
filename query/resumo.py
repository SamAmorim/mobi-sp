"""Observabilidade: cobertura da cidade e do mercado."""

from __future__ import annotations

from db.connection import fetchall, fetchone


def resumo_cidade() -> None:
    print("\n=== RESUMO CIDADE — São Paulo ===\n")

    d = fetchone("SELECT COUNT(*) AS n FROM distritos")
    print(f"Distritos carregados: {d['n']}")

    for modo in ("metro", "cptm", "onibus"):
        ln = fetchone(
            "SELECT COUNT(*) AS n FROM linhas_transporte WHERE modo = %s", (modo,)
        )
        pt = fetchone(
            "SELECT COUNT(*) AS n FROM pontos_transporte WHERE modo = %s", (modo,)
        )
        print(f"  {modo}: {ln['n']} linhas, {pt['n']} pontos")

    print("\n=== MERCADO ===\n")
    tot = fetchone("SELECT COUNT(*) AS n FROM imoveis")
    print(f"Imóveis: {tot['n']}")

    for row in fetchall(
        """
        SELECT tipo_imovel::text AS tipo, COUNT(*) AS n
        FROM imoveis GROUP BY tipo_imovel ORDER BY tipo
        """
    ):
        print(f"  {row['tipo']}: {row['n']}")

    cov = fetchone(
        """
        SELECT
            COUNT(*) FILTER (WHERE distrito_id IS NOT NULL) AS com_distrito,
            COUNT(*) FILTER (WHERE geom IS NOT NULL) AS com_geom,
            COUNT(*) FILTER (WHERE dentro_municipio IS TRUE) AS dentro_sp,
            COUNT(*) FILTER (WHERE tem_jardim IS TRUE) AS com_jardim,
            COUNT(*) FILTER (WHERE tem_quintal IS TRUE) AS com_quintal,
            COUNT(*) FILTER (WHERE tem_espaco_externo IS TRUE) AS com_espaco_ext
        FROM imoveis
        """
    )
    n = max(int(tot["n"] or 1), 1)
    print(
        f"\nCobertura: distrito={cov['com_distrito']}/{n} "
        f"geom={cov['com_geom']}/{n} dentro_SP={cov['dentro_sp']}/{n}"
    )
    print(
        f"Espaço externo: jardim={cov['com_jardim']} "
        f"quintal={cov['com_quintal']} qualquer={cov['com_espaco_ext']}"
    )

    malha = fetchone(
        """
        SELECT
            COUNT(*) FILTER (WHERE dist_metro_m IS NOT NULL AND dist_metro_m <= 1000) AS metro_1km,
            COUNT(*) FILTER (WHERE n_linhas_onibus_500m > 0) AS com_onibus
        FROM imovel_features
        """
    )
    feat_n = fetchone("SELECT COUNT(*) AS n FROM imovel_features")
    print(
        f"Malha: features={feat_n['n']} | metrô≤1km={malha['metro_1km']} | "
        f"c/ ônibus 500m={malha['com_onibus']}"
    )

    itbi = fetchone("SELECT COUNT(*) AS n FROM transacoes_itbi")
    hist = fetchone("SELECT COUNT(*) AS n FROM historico_precos")
    print(f"\nITBI: {itbi['n']} transações | historico_precos: {hist['n']} linhas")

    print("\nMediana R$/m² (ITBI) por distrito/tipo (amostra):")
    for row in fetchall(
        """
        SELECT d.nome AS distrito, h.tipo_imovel::text AS tipo,
               ROUND(h.preco_m2_mediano::numeric, 0) AS med, h.n_amostras
        FROM historico_precos h
        LEFT JOIN distritos d ON d.id = h.distrito_id
        WHERE h.fonte = 'itbi'
        ORDER BY d.nome, h.tipo_imovel
        LIMIT 15
        """
    ):
        print(
            f"  {(row['distrito'] or '-'):16} {row['tipo']:12} "
            f"R$ {row['med']:,.0f}/m² (n={row['n_amostras']})"
        )
    print()
