from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
SQL = ROOT / "sql"
DW_PATH = PROCESSED / "ecofluxo_dw.sqlite"

CRS_METRIC = "EPSG:31985"
CENSO_CITY_PREFIX = "2611606"
VERSAO_CARGA = "v1.3"
DATA_CENSO = "2022-07-31"
DATA_EXTRACAO = "2026-11-17"

LINKS = {
    "relatorio": "https://gisele-l.github.io/ecofluxo-painel-analitico/",
    "painel": "https://ecofluxo-neosync.streamlit.app",
    "repositorio": "https://github.com/Gisele-L/ecofluxo-painel-analitico",
}

FONTES = [
    {"id_fonte_dado": "IBGE_CENSO_2022", "instituicao": "IBGE",
     "conjunto": "Censo Demográfico 2022: agregados de rendimento do responsável por bairro e por setor censitário",
     "url": "https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html",
     "licenca": "Dados públicos; reprodução com citação da fonte",
     "data_referencia": DATA_CENSO, "data_extracao": DATA_EXTRACAO},
    {"id_fonte_dado": "RECIFE_COLETA", "instituicao": "Prefeitura do Recife",
     "conjunto": "Pontos de coleta seletiva e resíduos",
     "url": "https://dados.recife.pe.gov.br/dataset/pontos-de-coleta-seletiva",
     "licenca": "ODbL", "data_referencia": DATA_EXTRACAO, "data_extracao": DATA_EXTRACAO},
    {"id_fonte_dado": "RECIFE_MALHA", "instituicao": "Prefeitura do Recife",
     "conjunto": "Bairros e RPAs do Recife",
     "url": "https://dados.recife.pe.gov.br/dataset/area-urbana",
     "licenca": "ODbL", "data_referencia": DATA_EXTRACAO, "data_extracao": DATA_EXTRACAO},
    {"id_fonte_dado": "RECIFE_ZEIS", "instituicao": "Prefeitura do Recife",
     "conjunto": "Zoneamento do Plano Diretor: ZEIS",
     "url": "https://dados.recife.pe.gov.br/dataset/zoneamento",
     "licenca": "ODbL", "data_referencia": DATA_EXTRACAO, "data_extracao": DATA_EXTRACAO},
    {"id_fonte_dado": "ECOFLUXO_COBERTURA", "instituicao": "EcoFluxo (cálculo sobre Prefeitura do Recife e IBGE)",
     "conjunto": "Moradores estimados a 500 m e a 1 km de pontos de recicláveis",
     "url": LINKS["repositorio"],
     "licenca": "Derivado de RECIFE_COLETA, RECIFE_MALHA e IBGE_CENSO_2022",
     "data_referencia": DATA_EXTRACAO, "data_extracao": DATA_EXTRACAO},
    {"id_fonte_dado": "MDS_CADINSAN", "instituicao": "MDS",
     "conjunto": "CadINSAN: risco de insegurança alimentar grave entre famílias do CadÚnico (municipal)",
     "url": "https://www.gov.br/mds/pt-br/Sisan/vigilancia-do-sisan/CADinsan/",
     "licenca": "Conteúdo público do Governo Federal; citar a fonte",
     "data_referencia": "2024-01-31", "data_extracao": DATA_EXTRACAO},
    {"id_fonte_dado": "RECIFE_CADUNICO_2023", "instituicao": "Prefeitura do Recife",
     "conjunto": "Cadastro Único 2023, base anonimizada (usada só em agregados municipais)",
     "url": "https://dados.recife.pe.gov.br/dataset/cadastro-unico-para-programas-sociais",
     "licenca": "ODbL; microdados mantidos fora do repositório",
     "data_referencia": "2023-09-16", "data_extracao": DATA_EXTRACAO},
]

CORES = {
    "mata": "#173F32", "folha": "#236448", "broto": "#DDF59A", "salvia": "#86B596", "musgo": "#52675B",
    "orvalho": "#EAF1E5", "papel": "#F4F6F0", "areia": "#F5EBD6", "terra": "#624A2B",
    "linha": "#DFE5DB", "branco": "#FFFFFF",
}
RAMPA = ["#E3EBDD", "#BCD6B8", "#86B596", "#4B8768", "#173F32"]
CLASSES_COBERTURA = [(0, 0, "0%"), (0, 10, "0,1 a 10%"), (10, 30, "10 a 30%"), (30, 60, "30 a 60%"), (60, 100, "60 a 100%")]
IDENTIFICACAO = {
    "autora": "Gisele Santos de Lima", "grupo": "Grupo NeoSync", "turma": "2TSCOR",
    "evento": "FIAP · Global Solution 2026.2 · CitizenTech · Data Science",
    "assinatura": "Reciclar transforma. Alimentar conecta.",
}
