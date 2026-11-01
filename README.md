# Mobi-SP — Mapear São Paulo

MVP de inteligência imobiliária **cidade-first** para o município de São Paulo.

## O que este MVP faz

1. **Camada cidade** — distritos + malha de **metrô**, **CPTM** e amostra de **ônibus**
2. **Camada mercado** — ITBI (preços reais agregados) + anúncios `casa` / `apartamento` / `sobrado`
3. **Filtros** por tipo, distrito, características e **linhas** de transporte
4. **Observabilidade** — `python main.py --resumo-cidade`

**Fora do escopo:** motor preditivo / preço justo / alertas de desconto.

### Jardim ≠ quintal

| Campo | Significado |
|-------|-------------|
| `tem_jardim` | Área ajardinada / paisagística |
| `tem_quintal` | Pátio/fundo utilitário |
| `tem_espaco_externo` | Derivado: jardim **OU** quintal **OU** varanda **OU** sacada |

Anúncios que só dizem “área externa” **não** forçam jardim nem quintal.

## Estrutura

```
mobi-sp/
├── schema.sql
├── docker-compose.yml
├── main.py
├── config.py
├── ingestion/          # portais, ITBI, leilões
├── spatial/            # seed cidade + malha + amenities + histórico
├── query/              # filtros + resumo
└── data/fixtures/      # distritos, transporte SP, listings, ITBI
```

## Sem Docker (validação offline)

Enquanto o Docker/PostGIS não estiver disponível, dá para validar a camada cidade:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py --validate-fixtures
```

Isso checa distritos, linhas metrô/CPTM/ônibus e consistência com os listings.  
Seed, ingestão e filtros SQL exigem o banco (`docker compose up -d`).

## Setup

```bash
# 1) Banco PostGIS (requer Docker Desktop rodando)
docker compose up -d

# 2) Python
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env

# 3) Pipeline demo (fixtures, sem scrape)
python main.py --demo --step all
```

O `schema.sql` é aplicado automaticamente na primeira subida do container. Se o volume já existir:

```bash
docker compose exec -T db psql -U mobi -d mobi_sp < schema.sql
```

## Comandos úteis

```bash
# Cobertura da cidade / mercado
python main.py --resumo-cidade

# Casas com jardim perto da Linha 2-Verde
python main.py --filter --tipo casa --tem-jardim --linha-metro 2-Verde

# Só quintal (não jardim)
python main.py --filter --tem-quintal --distrito Saúde

# Qualquer espaço externo
python main.py --filter --espaco-externo --max-preco 1500000

# Apartamento + elevador + linha de ônibus
python main.py --filter --tipo apartamento --tem-elevador --linha-onibus 177Y-10

# CPTM 9-Esmeralda
python main.py --filter --linha-cptm 9-Esmeralda --max-dist-metro 1200
```

Etapas isoladas:

```bash
python main.py --demo --step seed      # distritos + malha
python main.py --demo --step ingest    # anúncios + ITBI + leilões
python main.py --demo --step spatial   # distâncias + historico_precos
```

## Fontes (MVP)

| Camada | Fonte atual | Próximo passo |
|--------|-------------|----------------|
| Distritos | fixture (~48 distritos) | GeoSampa polígonos oficiais |
| Metrô/CPTM | fixture com linhas principais e estações | GeoSampa / dados oficiais |
| Ônibus | amostra de paradas/linhas | GTFS SP |
| ITBI | CSV demo | download dados abertos Pref. SP |
| Anúncios | fixture + esqueleto Playwright | portal real com rate-limit |

## Conformidade

Scrapers usam User-Agent identificável, delay e fallback para fixture. Respeite robots/ToS dos portais. Sem bypass de CAPTCHA/WAF.
