"""Conexão e helpers SQL para o Mobi-SP."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterable, Iterator, Optional, Sequence

import psycopg2
import psycopg2.extras

from config import DATABASE_URL


def get_connection():
    return psycopg2.connect(DATABASE_URL)


@contextmanager
def db_cursor(commit: bool = True) -> Iterator[Any]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
            if commit:
                conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute(sql: str, params: Optional[Sequence[Any]] = None) -> None:
    with db_cursor() as cur:
        cur.execute(sql, params)


def fetchall(sql: str, params: Optional[Sequence[Any]] = None) -> list[dict]:
    with db_cursor(commit=False) as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def fetchone(sql: str, params: Optional[Sequence[Any]] = None) -> Optional[dict]:
    with db_cursor(commit=False) as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None


def resolve_distrito_id(nome: Optional[str]) -> Optional[int]:
    if not nome:
        return None
    row = fetchone(
        "SELECT id FROM distritos WHERE lower(nome) = lower(%s)",
        (nome.strip(),),
    )
    return int(row["id"]) if row else None


def upsert_imovel(row: dict) -> int:
    """Insere ou atualiza imóvel; retorna id."""
    sql = """
    INSERT INTO imoveis (
        fonte, id_externo, titulo, tipo_imovel, distrito_id, bairro, endereco,
        preco, preco_m2, area_m2, quartos, banheiros, vagas,
        aceita_pets, mobiliado, ano_construcao, zoneamento,
        area_terreno_m2, tem_jardim, tem_quintal, tem_piscina, tem_churrasqueira,
        andares, tem_garagem_coberta, tem_area_servico, tem_varanda,
        andar, total_andares_predio, tem_elevador, valor_condominio,
        tem_sacada, tem_portaria, unidades_por_andar,
        caracteristicas, url, geom, dentro_municipio, metadados
    ) VALUES (
        %(fonte)s, %(id_externo)s, %(titulo)s, %(tipo_imovel)s, %(distrito_id)s,
        %(bairro)s, %(endereco)s,
        %(preco)s, %(preco_m2)s, %(area_m2)s, %(quartos)s, %(banheiros)s, %(vagas)s,
        %(aceita_pets)s, %(mobiliado)s, %(ano_construcao)s, %(zoneamento)s,
        %(area_terreno_m2)s, %(tem_jardim)s, %(tem_quintal)s, %(tem_piscina)s,
        %(tem_churrasqueira)s,
        %(andares)s, %(tem_garagem_coberta)s, %(tem_area_servico)s, %(tem_varanda)s,
        %(andar)s, %(total_andares_predio)s, %(tem_elevador)s, %(valor_condominio)s,
        %(tem_sacada)s, %(tem_portaria)s, %(unidades_por_andar)s,
        %(caracteristicas)s::jsonb, %(url)s,
        CASE WHEN %(lon)s IS NOT NULL AND %(lat)s IS NOT NULL
             THEN ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography
             ELSE NULL END,
        %(dentro_municipio)s,
        %(metadados)s::jsonb
    )
    ON CONFLICT (fonte, id_externo) DO UPDATE SET
        titulo = EXCLUDED.titulo,
        tipo_imovel = EXCLUDED.tipo_imovel,
        distrito_id = COALESCE(EXCLUDED.distrito_id, imoveis.distrito_id),
        bairro = EXCLUDED.bairro,
        endereco = EXCLUDED.endereco,
        preco = EXCLUDED.preco,
        preco_m2 = EXCLUDED.preco_m2,
        area_m2 = EXCLUDED.area_m2,
        quartos = EXCLUDED.quartos,
        banheiros = EXCLUDED.banheiros,
        vagas = EXCLUDED.vagas,
        aceita_pets = EXCLUDED.aceita_pets,
        mobiliado = EXCLUDED.mobiliado,
        ano_construcao = EXCLUDED.ano_construcao,
        zoneamento = EXCLUDED.zoneamento,
        area_terreno_m2 = EXCLUDED.area_terreno_m2,
        tem_jardim = EXCLUDED.tem_jardim,
        tem_quintal = EXCLUDED.tem_quintal,
        tem_piscina = EXCLUDED.tem_piscina,
        tem_churrasqueira = EXCLUDED.tem_churrasqueira,
        andares = EXCLUDED.andares,
        tem_garagem_coberta = EXCLUDED.tem_garagem_coberta,
        tem_area_servico = EXCLUDED.tem_area_servico,
        tem_varanda = EXCLUDED.tem_varanda,
        andar = EXCLUDED.andar,
        total_andares_predio = EXCLUDED.total_andares_predio,
        tem_elevador = EXCLUDED.tem_elevador,
        valor_condominio = EXCLUDED.valor_condominio,
        tem_sacada = EXCLUDED.tem_sacada,
        tem_portaria = EXCLUDED.tem_portaria,
        unidades_por_andar = EXCLUDED.unidades_por_andar,
        caracteristicas = EXCLUDED.caracteristicas,
        url = EXCLUDED.url,
        geom = COALESCE(EXCLUDED.geom, imoveis.geom),
        dentro_municipio = EXCLUDED.dentro_municipio,
        metadados = EXCLUDED.metadados,
        scraped_at = NOW()
    RETURNING id;
    """
    payload = {
        **row,
        "caracteristicas": json.dumps(row.get("caracteristicas") or {}, ensure_ascii=False),
        "metadados": json.dumps(row.get("metadados") or {}, ensure_ascii=False),
    }
    with db_cursor() as cur:
        cur.execute(sql, payload)
        return int(cur.fetchone()["id"])
