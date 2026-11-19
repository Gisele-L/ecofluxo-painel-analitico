-- EcoFluxo · Consultas analíticas sobre o modelo Snowflake (PostgreSQL ou SQLite)

-- 1. Roll-up bairro -> RPA: moradores, pontos e cobertura a 500 m
SELECT
    r.nome AS rpa,
    SUM(CASE WHEN i.codigo = 'MORADORES' THEN f.valor END) AS moradores,
    SUM(CASE WHEN i.codigo = 'PONTOS_RECICLAVEIS' THEN f.valor END) AS pontos_reciclaveis,
    ROUND(100.0 * SUM(CASE WHEN i.codigo = 'MORADORES_COBERTOS_500M' THEN f.valor END)
          / SUM(CASE WHEN i.codigo = 'MORADORES' THEN f.valor END), 1) AS cobertura_500m_pct
FROM Fato_Indicador_Territorial f
JOIN Dim_Indicador i ON i.id_indicador = f.id_indicador
JOIN Dim_Bairro b ON b.id_bairro = f.id_bairro
JOIN Dim_RPA r ON r.id_rpa = b.id_rpa
GROUP BY r.id_rpa, r.nome
ORDER BY r.id_rpa;

-- 2. Rendimento médio do responsável por RPA, ponderado por domicílios (regra da Dim_Indicador)
SELECT
    v.rpa,
    ROUND(SUM(v.renda_media_resp * v.domicilios) / SUM(v.domicilios), 2) AS rendimento_medio_resp
FROM vw_bairro_indicadores v
GROUP BY v.rpa
ORDER BY v.rpa;

-- 3. Bairros sem ponto de recicláveis, do mais ao menos populoso
SELECT v.bairro, v.rpa, v.moradores
FROM vw_bairro_indicadores v
WHERE v.pontos_reciclaveis = 0
ORDER BY v.moradores DESC;

-- 4. Pontos da base pública por tipo de local e RPA
SELECT r.nome AS rpa, l.tipo_local, COUNT(*) AS pontos,
       SUM(CASE WHEN l.aceita_reciclavel THEN 1 ELSE 0 END) AS aceitam_reciclavel
FROM Dim_Local l
JOIN Dim_Bairro b ON b.id_bairro = l.id_bairro
JOIN Dim_RPA r ON r.id_rpa = b.id_rpa
GROUP BY r.id_rpa, r.nome, l.tipo_local
ORDER BY r.id_rpa, pontos DESC;

-- 5. Linhagem: cada indicador com sua fonte e data de referência
SELECT i.codigo, i.regra_agregacao, d.instituicao, d.conjunto, d.licenca,
       t.data AS data_referencia, t.ano, COUNT(*) AS linhas_na_fato
FROM Fato_Indicador_Territorial f
JOIN Dim_Indicador i ON i.id_indicador = f.id_indicador
JOIN Dim_Fonte_Dado d ON d.id_fonte_dado = i.id_fonte_dado
JOIN Dim_Tempo t ON t.id_tempo = f.id_tempo_referencia
GROUP BY i.id_indicador, i.codigo, i.regra_agregacao, d.instituicao, d.conjunto, d.licenca, t.data, t.ano
ORDER BY i.id_indicador;
