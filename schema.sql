-- Mobi-SP MVP — Mapear a cidade de São Paulo (PostgreSQL + PostGIS)
-- Camada cidade: distritos + malha metrô/CPTM/ônibus
-- Camada mercado: ITBI (preços reais) + anúncios tipados
-- Sem motor preditivo.

CREATE EXTENSION IF NOT EXISTS postgis;

DO $$ BEGIN
    CREATE TYPE tipo_imovel_enum AS ENUM ('casa', 'apartamento', 'sobrado');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE modo_transporte_enum AS ENUM ('metro', 'cptm', 'onibus');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ===========================================================================
-- CAMADA CIDADE
-- ===========================================================================

-- Distritos oficiais do município (identidade geográfica estável)
CREATE TABLE IF NOT EXISTS distritos (
    id              SERIAL PRIMARY KEY,
    codigo          TEXT UNIQUE,          -- código oficial quando disponível
    nome            TEXT NOT NULL UNIQUE,
    zona            TEXT,                 -- Norte/Sul/Leste/Oeste/Centro
    geom            GEOGRAPHY(POINT, 4326), -- centroid no MVP; polígono depois
    fonte           TEXT DEFAULT 'fixture'
);

CREATE INDEX IF NOT EXISTS idx_distritos_nome ON distritos (nome);
CREATE INDEX IF NOT EXISTS idx_distritos_geom ON distritos USING GIST (geom);

-- Linhas da malha (metrô, CPTM, ônibus)
CREATE TABLE IF NOT EXISTS linhas_transporte (
    id          BIGSERIAL PRIMARY KEY,
    codigo      TEXT NOT NULL,
    nome        TEXT,
    modo        modo_transporte_enum NOT NULL,
    cor         TEXT,
    destino     TEXT,
    tipo_linha  TEXT,                     -- comum | noturno | corredor | expresso
    fonte       TEXT DEFAULT 'fixture',
    UNIQUE (modo, codigo)
);

CREATE INDEX IF NOT EXISTS idx_linhas_modo ON linhas_transporte (modo);
CREATE INDEX IF NOT EXISTS idx_linhas_codigo ON linhas_transporte (codigo);

-- Estações (metrô/CPTM) e paradas (ônibus)
CREATE TABLE IF NOT EXISTS pontos_transporte (
    id          BIGSERIAL PRIMARY KEY,
    nome        TEXT,
    endereco    TEXT,
    modo        modo_transporte_enum NOT NULL,
    geom        GEOGRAPHY(POINT, 4326) NOT NULL,
    fonte       TEXT DEFAULT 'fixture'
);

CREATE INDEX IF NOT EXISTS idx_pontos_modo ON pontos_transporte (modo);
CREATE INDEX IF NOT EXISTS idx_pontos_geom ON pontos_transporte USING GIST (geom);

CREATE TABLE IF NOT EXISTS ponto_linhas (
    ponto_id    BIGINT NOT NULL REFERENCES pontos_transporte (id) ON DELETE CASCADE,
    linha_id    BIGINT NOT NULL REFERENCES linhas_transporte (id) ON DELETE CASCADE,
    PRIMARY KEY (ponto_id, linha_id)
);

CREATE OR REPLACE VIEW estacoes_transporte AS
SELECT id, nome, modo AS tipo, geom, fonte
FROM pontos_transporte
WHERE modo IN ('metro', 'cptm');

CREATE OR REPLACE VIEW linhas_onibus AS
SELECT id, codigo, nome, destino, tipo_linha AS tipo, fonte
FROM linhas_transporte
WHERE modo = 'onibus';

CREATE OR REPLACE VIEW pontos_parada AS
SELECT id, nome, endereco, geom, fonte
FROM pontos_transporte
WHERE modo = 'onibus';

-- Amenities (camada leve; expansão depois)
CREATE TABLE IF NOT EXISTS amenities (
    id          BIGSERIAL PRIMARY KEY,
    nome        TEXT,
    categoria   TEXT NOT NULL CHECK (categoria IN ('comercio', 'parque', 'escola')),
    geom        GEOGRAPHY(POINT, 4326) NOT NULL,
    fonte       TEXT DEFAULT 'fixture'
);

CREATE INDEX IF NOT EXISTS idx_amenities_cat ON amenities (categoria);
CREATE INDEX IF NOT EXISTS idx_amenities_geom ON amenities USING GIST (geom);

-- ===========================================================================
-- CAMADA MERCADO
-- ===========================================================================

CREATE TABLE IF NOT EXISTS imoveis (
    id                  BIGSERIAL PRIMARY KEY,
    fonte               TEXT NOT NULL,
    id_externo          TEXT NOT NULL,
    titulo              TEXT,
    tipo_imovel         tipo_imovel_enum NOT NULL,
    distrito_id         INTEGER REFERENCES distritos (id),
    bairro              TEXT,                 -- texto do anúncio (não oficial)
    endereco            TEXT,
    preco               NUMERIC(14, 2),
    preco_m2            NUMERIC(14, 2),
    area_m2             NUMERIC(10, 2),
    quartos             INTEGER,
    banheiros           INTEGER,
    vagas               INTEGER,
    aceita_pets         BOOLEAN,
    mobiliado           BOOLEAN,
    ano_construcao      INTEGER,
    zoneamento          TEXT,
    -- Casa / sobrado — jardim ≠ quintal
    area_terreno_m2     NUMERIC(10, 2),
    tem_jardim          BOOLEAN,              -- área ajardinada / paisagística
    tem_quintal         BOOLEAN,              -- pátio/fundo utilitário
    tem_piscina         BOOLEAN,
    tem_churrasqueira   BOOLEAN,
    andares             INTEGER,
    tem_garagem_coberta BOOLEAN,
    tem_area_servico    BOOLEAN,
    tem_varanda         BOOLEAN,
    -- Apartamento
    andar               INTEGER,
    total_andares_predio INTEGER,
    tem_elevador        BOOLEAN,
    valor_condominio    NUMERIC(12, 2),
    tem_sacada          BOOLEAN,
    tem_portaria        BOOLEAN,
    unidades_por_andar  INTEGER,
    -- Qualquer área externa (jardim OR quintal OR varanda OR sacada)
    tem_espaco_externo  BOOLEAN GENERATED ALWAYS AS (
        COALESCE(tem_jardim, false)
        OR COALESCE(tem_quintal, false)
        OR COALESCE(tem_varanda, false)
        OR COALESCE(tem_sacada, false)
    ) STORED,
    caracteristicas     JSONB NOT NULL DEFAULT '{}'::jsonb,
    url                 TEXT,
    geom                GEOGRAPHY(POINT, 4326),
    dentro_municipio    BOOLEAN,              -- validação SP
    scraped_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadados           JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (fonte, id_externo)
);

CREATE INDEX IF NOT EXISTS idx_imoveis_tipo ON imoveis (tipo_imovel);
CREATE INDEX IF NOT EXISTS idx_imoveis_distrito ON imoveis (distrito_id);
CREATE INDEX IF NOT EXISTS idx_imoveis_bairro ON imoveis (bairro);
CREATE INDEX IF NOT EXISTS idx_imoveis_preco ON imoveis (preco);
CREATE INDEX IF NOT EXISTS idx_imoveis_quartos ON imoveis (quartos);
CREATE INDEX IF NOT EXISTS idx_imoveis_jardim ON imoveis (tem_jardim);
CREATE INDEX IF NOT EXISTS idx_imoveis_quintal ON imoveis (tem_quintal);
CREATE INDEX IF NOT EXISTS idx_imoveis_espaco_ext ON imoveis (tem_espaco_externo);
CREATE INDEX IF NOT EXISTS idx_imoveis_elevador ON imoveis (tem_elevador);
CREATE INDEX IF NOT EXISTS idx_imoveis_geom ON imoveis USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_imoveis_caracteristicas ON imoveis USING GIN (caracteristicas);

-- Vínculo imóvel ↔ linha (estação/parada mais próxima daquela linha)
CREATE TABLE IF NOT EXISTS imovel_linhas_transporte (
    imovel_id       BIGINT NOT NULL REFERENCES imoveis (id) ON DELETE CASCADE,
    linha_id        BIGINT NOT NULL REFERENCES linhas_transporte (id) ON DELETE CASCADE,
    ponto_id        BIGINT REFERENCES pontos_transporte (id) ON DELETE SET NULL,
    distancia_m     NUMERIC(10, 2) NOT NULL,
    PRIMARY KEY (imovel_id, linha_id)
);

CREATE INDEX IF NOT EXISTS idx_imovel_linhas_dist ON imovel_linhas_transporte (linha_id, distancia_m);

CREATE OR REPLACE VIEW imovel_linhas_onibus AS
SELECT ilt.imovel_id, ilt.linha_id, ilt.ponto_id, ilt.distancia_m
FROM imovel_linhas_transporte ilt
JOIN linhas_transporte lt ON lt.id = ilt.linha_id
WHERE lt.modo = 'onibus';

CREATE OR REPLACE VIEW imovel_linhas_metro AS
SELECT ilt.imovel_id, ilt.linha_id, ilt.ponto_id, ilt.distancia_m
FROM imovel_linhas_transporte ilt
JOIN linhas_transporte lt ON lt.id = ilt.linha_id
WHERE lt.modo = 'metro';

-- Features agregadas (malha + entorno)
CREATE TABLE IF NOT EXISTS imovel_features (
    imovel_id                       BIGINT PRIMARY KEY REFERENCES imoveis (id) ON DELETE CASCADE,
    dist_metro_m                    NUMERIC(10, 2),
    estacao_metro_proxima           TEXT,
    linha_metro_proxima             TEXT,
    n_linhas_metro_raio             INTEGER,
    linhas_metro_proximas           TEXT,
    dist_cptm_m                     NUMERIC(10, 2),
    estacao_cptm_proxima            TEXT,
    n_linhas_cptm_raio              INTEGER,
    linhas_cptm_proximas            TEXT,
    dist_parada_mais_proxima_m      NUMERIC(10, 2),
    n_paradas_300m                  INTEGER,
    n_linhas_onibus_500m            INTEGER,
    linhas_onibus_proximas          TEXT,
    malha_resumo                    TEXT,     -- metrô + CPTM + ônibus compacto
    n_comercios_500m                INTEGER,
    n_parques_500m                  INTEGER,
    n_escolas_500m                  INTEGER,
    score_infra_500m                NUMERIC(8, 2),
    atualizado_em                   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ITBI — ground truth de preços transacionados
CREATE TABLE IF NOT EXISTS transacoes_itbi (
    id                  BIGSERIAL PRIMARY KEY,
    inscricao           TEXT,
    distrito_id         INTEGER REFERENCES distritos (id),
    bairro              TEXT,
    valor_transacao     NUMERIC(14, 2),
    area_m2             NUMERIC(10, 2),
    data_transacao      DATE,
    tipo_imovel         tipo_imovel_enum,
    geom                GEOGRAPHY(POINT, 4326),
    fonte_arquivo       TEXT,
    metadados           JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_itbi_distrito ON transacoes_itbi (distrito_id);
CREATE INDEX IF NOT EXISTS idx_itbi_bairro ON transacoes_itbi (bairro);
CREATE INDEX IF NOT EXISTS idx_itbi_data ON transacoes_itbi (data_transacao);
CREATE INDEX IF NOT EXISTS idx_itbi_tipo ON transacoes_itbi (tipo_imovel);
CREATE INDEX IF NOT EXISTS idx_itbi_geom ON transacoes_itbi USING GIST (geom);

-- Mapa de preços (agregação — não é ML)
CREATE TABLE IF NOT EXISTS historico_precos (
    id                  BIGSERIAL PRIMARY KEY,
    distrito_id         INTEGER REFERENCES distritos (id),
    bairro              TEXT NOT NULL DEFAULT '',
    tipo_imovel         tipo_imovel_enum,
    mes_ref             DATE NOT NULL,
    preco_m2_mediano    NUMERIC(14, 2),
    n_amostras          INTEGER NOT NULL DEFAULT 0,
    fonte               TEXT NOT NULL CHECK (fonte IN ('anuncio', 'itbi')),
    UNIQUE (distrito_id, bairro, tipo_imovel, mes_ref, fonte)
);

COMMENT ON COLUMN imoveis.tem_jardim IS 'Área ajardinada/paisagística — distinto de quintal';
COMMENT ON COLUMN imoveis.tem_quintal IS 'Pátio/fundo utilitário — distinto de jardim';
COMMENT ON COLUMN imoveis.tem_espaco_externo IS 'Derivado: jardim OR quintal OR varanda OR sacada';
