-- EcoFluxo · Modelo dimensional Snowflake (Figura 6 da documentação)
-- Executa em PostgreSQL 16 e em SQLite 3. Os fatos operacionais ficam vazios até o piloto.

CREATE TABLE Dim_Municipio (
    id_municipio  INTEGER PRIMARY KEY,
    codigo_ibge   CHAR(7) NOT NULL UNIQUE,
    nome          TEXT NOT NULL,
    uf            CHAR(2) NOT NULL
);

CREATE TABLE Dim_RPA (
    id_rpa        INTEGER PRIMARY KEY,
    id_municipio  INTEGER NOT NULL REFERENCES Dim_Municipio (id_municipio),
    nome          TEXT NOT NULL
);

CREATE TABLE Dim_Bairro (
    id_bairro        INTEGER PRIMARY KEY,
    id_rpa           INTEGER NOT NULL REFERENCES Dim_RPA (id_rpa),
    cod_bairro_ibge  CHAR(10) NOT NULL UNIQUE,
    nome             TEXT NOT NULL
);

CREATE TABLE Dim_Local (
    id_local           INTEGER PRIMARY KEY,
    id_bairro          INTEGER NOT NULL REFERENCES Dim_Bairro (id_bairro),
    nome               TEXT NOT NULL,
    tipo_local         TEXT NOT NULL,
    origem_cadastro    TEXT NOT NULL,
    aceita_reciclavel  BOOLEAN NOT NULL,
    latitude           DOUBLE PRECISION NOT NULL,
    longitude          DOUBLE PRECISION NOT NULL
);

CREATE TABLE Dim_Tempo (
    id_tempo   INTEGER PRIMARY KEY,
    data       DATE NOT NULL UNIQUE,
    dia        SMALLINT NOT NULL,
    mes        SMALLINT NOT NULL,
    trimestre  SMALLINT NOT NULL,
    ano        SMALLINT NOT NULL
);

CREATE TABLE Dim_Cidadao (
    id_cidadao_sk         BIGINT PRIMARY KEY,
    codigo_cidadao        TEXT NOT NULL,
    id_bairro_referencia  INTEGER REFERENCES Dim_Bairro (id_bairro),
    canal_cadastro        TEXT NOT NULL,
    vigencia_inicio       TIMESTAMP NOT NULL,
    vigencia_fim          TIMESTAMP,
    registro_atual        BOOLEAN NOT NULL,
    CHECK (vigencia_fim IS NULL OR vigencia_fim > vigencia_inicio)
);

CREATE TABLE Dim_Material (
    id_material  INTEGER PRIMARY KEY,
    tipo         TEXT NOT NULL,
    categoria    TEXT NOT NULL,
    unidade      TEXT NOT NULL
);

CREATE TABLE Dim_Regra_Tickets (
    id_regra_tickets  INTEGER PRIMARY KEY,
    id_material       INTEGER NOT NULL REFERENCES Dim_Material (id_material),
    taxa_por_kg       NUMERIC(12, 4) NOT NULL CHECK (taxa_por_kg >= 0),
    versao            INTEGER NOT NULL,
    vigencia_inicio   TIMESTAMP NOT NULL,
    vigencia_fim      TIMESTAMP,
    CHECK (vigencia_fim IS NULL OR vigencia_fim > vigencia_inicio)
);

CREATE TABLE Dim_Produto (
    id_produto  BIGINT PRIMARY KEY,
    nome        TEXT NOT NULL,
    categoria   TEXT NOT NULL,
    unidade     TEXT NOT NULL
);

CREATE TABLE Dim_Produtor (
    id_produtor      BIGINT PRIMARY KEY,
    codigo_produtor  TEXT NOT NULL UNIQUE,
    categoria        TEXT NOT NULL
);

CREATE TABLE Dim_Tipo_Movimento (
    id_tipo_movimento  INTEGER PRIMARY KEY,
    categoria          TEXT NOT NULL,
    direcao            TEXT NOT NULL CHECK (direcao IN ('ENTRADA', 'SAIDA'))
);

CREATE TABLE Dim_Fonte_Recurso (
    id_fonte_recurso  INTEGER PRIMARY KEY,
    categoria         TEXT NOT NULL,
    codigo_fonte      TEXT NOT NULL
);

CREATE TABLE Dim_Fonte_Dado (
    id_fonte_dado    TEXT PRIMARY KEY,
    instituicao      TEXT NOT NULL,
    conjunto         TEXT NOT NULL,
    url              TEXT,
    licenca          TEXT,
    data_referencia  DATE,
    data_extracao    DATE
);

CREATE TABLE Dim_Indicador (
    id_indicador     INTEGER PRIMARY KEY,
    id_fonte_dado    TEXT NOT NULL REFERENCES Dim_Fonte_Dado (id_fonte_dado),
    codigo           TEXT NOT NULL UNIQUE,
    nome             TEXT NOT NULL,
    unidade          TEXT NOT NULL,
    regra_agregacao  TEXT NOT NULL CHECK (regra_agregacao IN ('soma', 'nao_aditivo', 'ponderar_por_domicilios'))
);

CREATE TABLE Fato_Indicador_Territorial (
    id_fato_indicador    BIGINT PRIMARY KEY,
    id_bairro            INTEGER NOT NULL REFERENCES Dim_Bairro (id_bairro),
    id_indicador         INTEGER NOT NULL REFERENCES Dim_Indicador (id_indicador),
    id_tempo_referencia  INTEGER NOT NULL REFERENCES Dim_Tempo (id_tempo),
    versao_carga         TEXT NOT NULL,
    valor                DOUBLE PRECISION NOT NULL,
    UNIQUE (id_bairro, id_indicador, id_tempo_referencia, versao_carga)
);

CREATE TABLE Fato_Entrega_Item (
    id_fato_entrega       BIGINT PRIMARY KEY,
    id_lancamento_origem  TEXT NOT NULL UNIQUE,
    id_entrega_origem     TEXT NOT NULL,
    id_item_origem        TEXT NOT NULL,
    tipo_registro         TEXT NOT NULL CHECK (tipo_registro IN ('ORIGINAL', 'AJUSTE')),
    id_fato_referenciado  BIGINT REFERENCES Fato_Entrega_Item (id_fato_entrega),
    id_tempo_evento       INTEGER NOT NULL REFERENCES Dim_Tempo (id_tempo),
    id_tempo_registro     INTEGER NOT NULL REFERENCES Dim_Tempo (id_tempo),
    id_cidadao_sk         BIGINT NOT NULL REFERENCES Dim_Cidadao (id_cidadao_sk),
    id_material           INTEGER NOT NULL REFERENCES Dim_Material (id_material),
    id_regra_tickets      INTEGER NOT NULL REFERENCES Dim_Regra_Tickets (id_regra_tickets),
    id_local              INTEGER NOT NULL REFERENCES Dim_Local (id_local),
    peso_kg               NUMERIC(12, 3) NOT NULL,
    ecotickets_emitidos   NUMERIC(14, 3) NOT NULL
);

CREATE TABLE Fato_Resgate_Item (
    id_fato_resgate       BIGINT PRIMARY KEY,
    id_lancamento_origem  TEXT NOT NULL UNIQUE,
    id_resgate_origem     TEXT NOT NULL,
    id_item_origem        TEXT NOT NULL,
    tipo_registro         TEXT NOT NULL CHECK (tipo_registro IN ('ORIGINAL', 'AJUSTE')),
    id_fato_referenciado  BIGINT REFERENCES Fato_Resgate_Item (id_fato_resgate),
    id_tempo_evento       INTEGER NOT NULL REFERENCES Dim_Tempo (id_tempo),
    id_tempo_registro     INTEGER NOT NULL REFERENCES Dim_Tempo (id_tempo),
    id_cidadao_sk         BIGINT NOT NULL REFERENCES Dim_Cidadao (id_cidadao_sk),
    id_produto            BIGINT NOT NULL REFERENCES Dim_Produto (id_produto),
    id_produtor           BIGINT NOT NULL REFERENCES Dim_Produtor (id_produtor),
    id_local              INTEGER NOT NULL REFERENCES Dim_Local (id_local),
    quantidade            NUMERIC(12, 3) NOT NULL,
    ecotickets_debitados  NUMERIC(14, 3) NOT NULL,
    custo_brl             NUMERIC(14, 2) NOT NULL
);

CREATE TABLE Fato_Movimento_Financeiro (
    id_movimento         BIGINT PRIMARY KEY,
    id_movimento_origem  TEXT NOT NULL UNIQUE,
    id_tempo             INTEGER NOT NULL REFERENCES Dim_Tempo (id_tempo),
    id_tipo_movimento    INTEGER NOT NULL REFERENCES Dim_Tipo_Movimento (id_tipo_movimento),
    id_fonte_recurso     INTEGER REFERENCES Dim_Fonte_Recurso (id_fonte_recurso),
    id_produtor          BIGINT REFERENCES Dim_Produtor (id_produtor),
    valor_brl            NUMERIC(14, 2) NOT NULL CHECK (valor_brl >= 0),
    CHECK (id_fonte_recurso IS NOT NULL OR id_produtor IS NOT NULL)
);

CREATE INDEX ix_fato_territorial_bairro ON Fato_Indicador_Territorial (id_bairro);
CREATE INDEX ix_fato_territorial_indicador ON Fato_Indicador_Territorial (id_indicador);
CREATE INDEX ix_dim_local_bairro ON Dim_Local (id_bairro);
CREATE INDEX ix_dim_cidadao_vigencia ON Dim_Cidadao (codigo_cidadao, vigencia_inicio);

CREATE VIEW vw_bairro_indicadores AS
SELECT
    b.id_bairro,
    b.cod_bairro_ibge,
    b.nome AS bairro,
    r.id_rpa AS rpa,
    m.nome AS municipio,
    m.uf,
    MAX(CASE WHEN i.codigo = 'MORADORES' THEN f.valor END) AS moradores,
    MAX(CASE WHEN i.codigo = 'DOMICILIOS' THEN f.valor END) AS domicilios,
    MAX(CASE WHEN i.codigo = 'RENDA_MEDIA_RESP' THEN f.valor END) AS renda_media_resp,
    MAX(CASE WHEN i.codigo = 'RENDA_MEDIANA_RESP' THEN f.valor END) AS renda_mediana_resp,
    MAX(CASE WHEN i.codigo = 'AREA_KM2' THEN f.valor END) AS area_km2,
    MAX(CASE WHEN i.codigo = 'AREA_ZEIS_KM2' THEN f.valor END) AS area_zeis_km2,
    MAX(CASE WHEN i.codigo = 'PONTOS_TOTAIS' THEN f.valor END) AS pontos_totais,
    MAX(CASE WHEN i.codigo = 'PONTOS_RECICLAVEIS' THEN f.valor END) AS pontos_reciclaveis,
    MAX(CASE WHEN i.codigo = 'MORADORES_COBERTOS_500M' THEN f.valor END) AS moradores_cobertos_500m,
    MAX(CASE WHEN i.codigo = 'MORADORES_COBERTOS_1000M' THEN f.valor END) AS moradores_cobertos_1000m
FROM Fato_Indicador_Territorial f
JOIN Dim_Indicador i ON i.id_indicador = f.id_indicador
JOIN Dim_Bairro b ON b.id_bairro = f.id_bairro
JOIN Dim_RPA r ON r.id_rpa = b.id_rpa
JOIN Dim_Municipio m ON m.id_municipio = r.id_municipio
WHERE f.versao_carga = (SELECT MAX(versao_carga) FROM Fato_Indicador_Territorial)
GROUP BY b.id_bairro, b.cod_bairro_ibge, b.nome, r.id_rpa, m.nome, m.uf;
