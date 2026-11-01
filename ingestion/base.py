"""Contrato de anúncio e normalização (tipo + espaço externo).

Jardim ≠ quintal:
- jardim = área ajardinada/paisagística
- quintal = pátio/fundo utilitário
Se o anúncio só diz "área externa", não forçamos nenhum dos dois.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from config import ponto_dentro_sp

TIPO_SINONIMOS = {
    "casa": "casa",
    "house": "casa",
    "home": "casa",
    "apartamento": "apartamento",
    "apto": "apartamento",
    "apartment": "apartamento",
    "flat": "apartamento",
    "sobrado": "sobrado",
    "townhouse": "sobrado",
    "town house": "sobrado",
}

# Sinônimos NÃO cruzam jardim ↔ quintal
JARDIM_KEYS = {"jardim", "garden", "jardim paisagistico", "jardim paisagístico", "frente ajardinada"}
QUINTAL_KEYS = {"quintal", "backyard", "yard", "fundo", "pátio", "patio"}
AREA_EXTERNA_GENERICA = {
    "area externa",
    "área externa",
    "espaco externo",
    "espaço externo",
    "outdoor",
}


def normalize_tipo(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    key = str(raw).strip().lower()
    return TIPO_SINONIMOS.get(key, key if key in {"casa", "apartamento", "sobrado"} else None)


def infer_espaco_externo(raw: dict[str, Any]) -> tuple[Optional[bool], Optional[bool], dict]:
    """Retorna (tem_jardim, tem_quintal, extras_caracteristicas)."""
    extras: dict[str, Any] = {}
    tem_jardim = _bool(raw.get("tem_jardim"))
    tem_quintal = _bool(raw.get("tem_quintal"))

    tags = raw.get("tags") or (raw.get("caracteristicas") or {}).get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    blob = " ".join(str(t).lower() for t in tags)
    for key in ("descricao", "titulo"):
        if raw.get(key):
            blob += " " + str(raw[key]).lower()

    if tem_jardim is None:
        if any(k in blob for k in JARDIM_KEYS):
            tem_jardim = True
    if tem_quintal is None:
        if any(k in blob for k in QUINTAL_KEYS):
            tem_quintal = True

    # Genérico: não atribui jardim nem quintal
    if tem_jardim is None and tem_quintal is None:
        if any(k in blob for k in AREA_EXTERNA_GENERICA) or raw.get("area_externa_generica"):
            extras["area_externa_generica"] = True
        if (raw.get("caracteristicas") or {}).get("area_externa_generica"):
            extras["area_externa_generica"] = True

    return tem_jardim, tem_quintal, extras


@dataclass
class Listing:
    fonte: str
    id_externo: str
    tipo_imovel: str
    titulo: Optional[str] = None
    distrito: Optional[str] = None
    bairro: Optional[str] = None
    endereco: Optional[str] = None
    preco: Optional[float] = None
    area_m2: Optional[float] = None
    quartos: Optional[int] = None
    banheiros: Optional[int] = None
    vagas: Optional[int] = None
    aceita_pets: Optional[bool] = None
    mobiliado: Optional[bool] = None
    ano_construcao: Optional[int] = None
    zoneamento: Optional[str] = None
    area_terreno_m2: Optional[float] = None
    tem_jardim: Optional[bool] = None
    tem_quintal: Optional[bool] = None
    tem_piscina: Optional[bool] = None
    tem_churrasqueira: Optional[bool] = None
    andares: Optional[int] = None
    tem_garagem_coberta: Optional[bool] = None
    tem_area_servico: Optional[bool] = None
    tem_varanda: Optional[bool] = None
    andar: Optional[int] = None
    total_andares_predio: Optional[int] = None
    tem_elevador: Optional[bool] = None
    valor_condominio: Optional[float] = None
    tem_sacada: Optional[bool] = None
    tem_portaria: Optional[bool] = None
    unidades_por_andar: Optional[int] = None
    caracteristicas: dict = field(default_factory=dict)
    url: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    metadados: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        tipo = normalize_tipo(self.tipo_imovel)
        if tipo is None:
            raise ValueError(f"tipo_imovel inválido: {self.tipo_imovel}")
        self.tipo_imovel = tipo

    @property
    def preco_m2(self) -> Optional[float]:
        if self.preco and self.area_m2 and self.area_m2 > 0:
            return round(float(self.preco) / float(self.area_m2), 2)
        return None

    def to_db_row(self, distrito_id: Optional[int] = None) -> dict[str, Any]:
        data = asdict(self)
        data.pop("distrito", None)
        data["distrito_id"] = distrito_id
        data["preco_m2"] = self.preco_m2
        data["dentro_municipio"] = ponto_dentro_sp(self.lat, self.lon)
        data["caracteristicas"] = self.caracteristicas or {}
        data["metadados"] = self.metadados or {}
        return data


def listing_from_dict(fonte: str, raw: dict[str, Any]) -> Listing:
    tipo = normalize_tipo(raw.get("tipo_imovel") or raw.get("tipo") or raw.get("propertyType"))
    if not tipo:
        raise ValueError(f"Não foi possível inferir tipo_imovel em: {raw.get('id_externo')}")

    tem_jardim, tem_quintal, extras = infer_espaco_externo(raw)
    caracteristicas = dict(raw.get("caracteristicas") or {})
    caracteristicas.update(extras)
    for key in ("tem_piscina", "tem_jardim", "tem_quintal", "tem_elevador", "lazer_predio", "tags"):
        if key in raw and key not in caracteristicas:
            caracteristicas[key] = raw[key]

    return Listing(
        fonte=fonte,
        id_externo=str(raw["id_externo"]),
        tipo_imovel=tipo,
        titulo=raw.get("titulo"),
        distrito=raw.get("distrito") or raw.get("bairro"),
        bairro=raw.get("bairro"),
        endereco=raw.get("endereco"),
        preco=_num(raw.get("preco")),
        area_m2=_num(raw.get("area_m2")),
        quartos=_int(raw.get("quartos")),
        banheiros=_int(raw.get("banheiros")),
        vagas=_int(raw.get("vagas")),
        aceita_pets=_bool(raw.get("aceita_pets")),
        mobiliado=_bool(raw.get("mobiliado")),
        ano_construcao=_int(raw.get("ano_construcao")),
        zoneamento=raw.get("zoneamento"),
        area_terreno_m2=_num(raw.get("area_terreno_m2")),
        tem_jardim=tem_jardim if tem_jardim is not None else _bool(raw.get("tem_jardim")),
        tem_quintal=tem_quintal if tem_quintal is not None else _bool(raw.get("tem_quintal")),
        tem_piscina=_bool(raw.get("tem_piscina")),
        tem_churrasqueira=_bool(raw.get("tem_churrasqueira")),
        andares=_int(raw.get("andares")),
        tem_garagem_coberta=_bool(raw.get("tem_garagem_coberta")),
        tem_area_servico=_bool(raw.get("tem_area_servico")),
        tem_varanda=_bool(raw.get("tem_varanda")),
        andar=_int(raw.get("andar")),
        total_andares_predio=_int(raw.get("total_andares_predio")),
        tem_elevador=_bool(raw.get("tem_elevador")),
        valor_condominio=_num(raw.get("valor_condominio")),
        tem_sacada=_bool(raw.get("tem_sacada")),
        tem_portaria=_bool(raw.get("tem_portaria")),
        unidades_por_andar=_int(raw.get("unidades_por_andar")),
        caracteristicas=caracteristicas,
        url=raw.get("url"),
        lat=_num(raw.get("lat")),
        lon=_num(raw.get("lon")),
        metadados=dict(raw.get("metadados") or {}),
    )


def _num(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _int(v: Any) -> Optional[int]:
    n = _num(v)
    return int(n) if n is not None else None


def _bool(v: Any) -> Optional[bool]:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "sim"}
