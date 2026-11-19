"""Pipeline: bases públicas -> indicadores territoriais -> tabelas do modelo dimensional (CSV)."""
from __future__ import annotations

import json
from zipfile import ZipFile

import geopandas as gpd
import pandas as pd

from .config import (DATA_CENSO, DATA_EXTRACAO, FONTES, OUTPUTS, PROCESSED, RAW, VERSAO_CARGA,
                     CENSO_CITY_PREFIX)
from .etl import locate, make_neighborhood_base, read_cadinsan, sha256_file, to_numeric
from .metrics import (calculate_ipv, coverage_by_neighborhood, enrich_population, quintile_labels_population,
                      territorial_kpis, zeis_coverage_city)
from .scenario import grid_coverage_pct

INDICADORES = [
    ("MORADORES", "Moradores em domicílios particulares permanentes ocupados", "pessoas", "soma", "IBGE_CENSO_2022"),
    ("DOMICILIOS", "Domicílios com responsáveis (V06001)", "domicílios", "soma", "IBGE_CENSO_2022"),
    ("RENDA_MEDIA_RESP", "Rendimento nominal médio do responsável (V06004)", "R$", "ponderar_por_domicilios",
     "IBGE_CENSO_2022"),
    ("RENDA_MEDIANA_RESP", "Rendimento nominal mediano do responsável (V06006)", "R$", "nao_aditivo", "IBGE_CENSO_2022"),
    ("AREA_KM2", "Área do bairro", "km²", "soma", "RECIFE_MALHA"),
    ("AREA_ZEIS_KM2", "Área do bairro em ZEIS", "km²", "soma", "RECIFE_ZEIS"),
    ("PONTOS_TOTAIS", "Pontos de coleta de qualquer resíduo no bairro", "pontos", "soma", "RECIFE_COLETA"),
    ("PONTOS_RECICLAVEIS", "Pontos que aceitam recicláveis secos no bairro", "pontos", "soma", "RECIFE_COLETA"),
    ("MORADORES_COBERTOS_500M", "Moradores estimados a até 500 m de um ponto de recicláveis", "pessoas (estimativa)",
     "soma", "ECOFLUXO_COBERTURA"),
    ("MORADORES_COBERTOS_1000M", "Moradores estimados a até 1 km de um ponto de recicláveis", "pessoas (estimativa)",
     "soma", "ECOFLUXO_COBERTURA"),
]
COLUNA_DO_INDICADOR = {
    "MORADORES": "moradores_domicilios_responsaveis", "DOMICILIOS": "responsaveis_domicilios",
    "RENDA_MEDIA_RESP": "renda_media_responsavel", "RENDA_MEDIANA_RESP": "renda_mediana_responsavel",
    "AREA_KM2": "area_km2", "AREA_ZEIS_KM2": "area_zeis_km2", "PONTOS_TOTAIS": "registros_todos",
    "PONTOS_RECICLAVEIS": "registros_no_bairro", "MORADORES_COBERTOS_500M": "moradores_cobertos_500m",
    "MORADORES_COBERTOS_1000M": "moradores_cobertos_1000m",
}
DATA_DO_INDICADOR = {codigo: (DATA_CENSO if fonte == "IBGE_CENSO_2022" else DATA_EXTRACAO)
                     for codigo, _, _, _, fonte in INDICADORES}


def id_tempo(data: str) -> int:
    return int(data.replace("-", ""))


def sector_households_low_income() -> dict:
    total = baixa = 0
    with ZipFile(locate("Agregados_por_setores*renda*.zip")) as z, z.open(z.namelist()[0]) as file:
        for part in pd.read_csv(file, sep=";", encoding="latin1", dtype=str, chunksize=50000,
                                usecols=["CD_SETOR", "V06001", "V06006"]):
            p = part.loc[part.CD_SETOR.str.startswith(CENSO_CITY_PREFIX, na=False)]
            domicilios = to_numeric(p.V06001).fillna(0)
            total += domicilios.sum()
            baixa += domicilios[to_numeric(p.V06006).le(1212)].sum()
    return {"domicilios_total_setores": int(total), "domicilios_setores_renda_mediana_ate_1212": int(baixa),
            "pct": 100 * baixa / total}


def validate(base: pd.DataFrame) -> dict:
    errors = []
    if len(base) != 94:
        errors.append("quantidade_bairros")
    if int(base["registros_no_bairro"].sum()) != 144:
        errors.append("contagem_reciclaveis")
    if int(base["registros_todos"].sum()) != 225:
        errors.append("contagem_todos")
    if int(base["moradores_domicilios_responsaveis"].sum()) != 1479478:
        errors.append("populacao_ibge")
    if int(base["posicao_ipv"].notna().sum()) != 72:
        errors.append("bairros_elegiveis_ipv")
    for radius in (500, 1000):
        if not base[f"cobertura_area_{radius}m_pct"].between(-1e-7, 100 + 1e-7).all():
            errors.append(f"cobertura_{radius}")
    if base["bairro_key"].duplicated().any():
        errors.append("bairro_duplicado")
    return {"status": "APROVADO" if not errors else "REPROVADO", "erros": errors, "testes_executados": 7}


def territorial_base() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame, dict]:
    bairros, pontos, zeis, audit = make_neighborhood_base()
    pts_rec = pontos.loc[pontos.compativel_reciclagem & pontos.dentro_recife]
    pts_all = pontos.loc[pontos.dentro_recife]
    b500 = enrich_population(coverage_by_neighborhood(bairros, pts_rec, zeis, 500))
    b1000 = enrich_population(coverage_by_neighborhood(bairros, pts_rec, zeis, 1000))
    d = b500.copy()
    d["cobertura_area_500m_pct"] = d["cobertura_area_pct"]
    d["moradores_cobertos_500m"] = d["moradores_cobertos_estimados"]
    d["cobertura_area_1000m_pct"] = b1000["cobertura_area_pct"].to_numpy()
    d["moradores_cobertos_1000m"] = b1000["moradores_cobertos_estimados"].to_numpy()
    d["registros_todos"] = coverage_by_neighborhood(bairros, pts_all, zeis, 500)["registros_no_bairro"].to_numpy()
    d["renda_ponderada"] = d["renda_media_responsavel"] * d["responsaveis_domicilios"]
    d = calculate_ipv(d)
    d["quintil_renda"] = quintile_labels_population(d)
    d["elegivel_ipv"] = d.moradores_domicilios_responsaveis.ge(5000)
    d = d.drop(columns=["area_coberta_km2", "area_zeis_coberta_km2", "cobertura_area_pct", "cobertura_area_zeis_pct",
                        "moradores_cobertos_estimados", "moradores_descobertos_estimados"])
    return d, pontos, zeis, audit


def summarize(d: gpd.GeoDataFrame, pontos: gpd.GeoDataFrame, zeis: gpd.GeoDataFrame) -> dict:
    pts_rec = pontos.loc[pontos.compativel_reciclagem & pontos.dentro_recife]
    top10 = d.dropna(subset=["ipv"]).sort_values(["ipv", "bairro"], ascending=[False, True]).head(10)
    zeis_city = zeis_coverage_city(zeis, pts_rec, 500)
    summary = {"pontos_csv_total": int(len(pontos)), **territorial_kpis(d)}
    summary.update({
        "pontos_recife_todos": int(pontos.dentro_recife.sum()),
        "pontos_reciclaveis_secos": int(len(pts_rec)),
        "area_total_km2": float(d.area_km2.sum()),
        "area_zeis_km2": zeis_city["area_zeis_km2"],
        "area_zeis_pct_cidade": 100 * zeis_city["area_zeis_km2"] / float(d.area_km2.sum()),
        "cobertura_area_zeis_500m_pct": zeis_city["cobertura_area_zeis_pct"],
        "top10_ipv_cobertura_populacional_500m_pct": grid_coverage_pct(d.loc[d.bairro_key.isin(top10.bairro_key)], pts_rec),
        "setores_renda_ate_1sm": sector_households_low_income(),
        "cadinsan_municipal": read_cadinsan(),
        "cadunico_municipal": None,
    })
    cadunico = PROCESSED / "cadunico_agregado_municipal_2023.json"
    if cadunico.exists():
        summary["cadunico_municipal"] = json.loads(cadunico.read_text(encoding="utf-8"))
    return summary


def model_tables(d: gpd.GeoDataFrame, pontos: gpd.GeoDataFrame) -> dict[str, pd.DataFrame]:
    d = d.reset_index(drop=True)
    datas = sorted(set(DATA_DO_INDICADOR.values()))
    tempo = pd.DataFrame({"data": pd.to_datetime(datas)})
    dim_tempo = pd.DataFrame({
        "id_tempo": [id_tempo(x) for x in datas], "data": datas, "dia": tempo.data.dt.day,
        "mes": tempo.data.dt.month, "trimestre": tempo.data.dt.quarter, "ano": tempo.data.dt.year})
    dim_bairro = pd.DataFrame({"id_bairro": d.index + 1, "id_rpa": d.rpa.astype(int),
                               "cod_bairro_ibge": d.codigo_bairro_ibge.astype(str), "nome": d.bairro})
    id_por_chave = dict(zip(d.bairro_key, dim_bairro.id_bairro))
    locais = pontos.loc[pontos.dentro_recife].sort_values("registro_id")
    dim_local = pd.DataFrame({
        "id_local": locais.registro_id.astype(int), "id_bairro": locais.bairro_key.map(id_por_chave).astype(int),
        "nome": locais.nome_local, "tipo_local": locais.tipo_local,
        "origem_cadastro": "Base pública da Prefeitura do Recife",
        "aceita_reciclavel": locais.compativel_reciclagem.astype(int),
        "latitude": locais.latitude.round(6), "longitude": locais.longitude.round(6)})
    dim_indicador = pd.DataFrame([
        {"id_indicador": i + 1, "id_fonte_dado": fonte, "codigo": codigo, "nome": nome, "unidade": unidade,
         "regra_agregacao": regra} for i, (codigo, nome, unidade, regra, fonte) in enumerate(INDICADORES)])
    fato = [{"id_bairro": id_por_chave[row.bairro_key], "id_indicador": i + 1,
             "id_tempo_referencia": id_tempo(DATA_DO_INDICADOR[codigo]), "versao_carga": VERSAO_CARGA,
             "valor": float(row[COLUNA_DO_INDICADOR[codigo]])}
            for _, row in d.iterrows() for i, (codigo, *_rest) in enumerate(INDICADORES)]
    fato = pd.DataFrame(fato)
    fato.insert(0, "id_fato_indicador", range(1, len(fato) + 1))
    if len(fato) != 940 or fato.duplicated(["id_bairro", "id_indicador", "id_tempo_referencia", "versao_carga"]).any():
        raise AssertionError("Fato_Indicador_Territorial deve ter 940 linhas com grão único.")
    return {
        "Dim_Municipio": pd.DataFrame([{"id_municipio": 1, "codigo_ibge": CENSO_CITY_PREFIX, "nome": "Recife", "uf": "PE"}]),
        "Dim_RPA": pd.DataFrame([{"id_rpa": i, "id_municipio": 1, "nome": f"RPA {i}"} for i in range(1, 7)]),
        "Dim_Bairro": dim_bairro,
        "Dim_Local": dim_local,
        "Dim_Tempo": dim_tempo,
        "Dim_Fonte_Dado": pd.DataFrame(FONTES),
        "Dim_Indicador": dim_indicador,
        "Fato_Indicador_Territorial": fato,
    }


def build() -> dict:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    d, pontos, zeis, audit = territorial_base()
    summary = summarize(d, pontos, zeis)
    tables = model_tables(d, pontos)
    for name, table in tables.items():
        table.to_csv(PROCESSED / f"{name}.csv", index=False, encoding="utf-8")
    geometria = gpd.GeoDataFrame({"id_bairro": tables["Dim_Bairro"].id_bairro}, geometry=d.geometry.values, crs=d.crs)
    geometria.to_file(PROCESSED / "bairros_geometria.geojson", driver="GeoJSON")
    audit.update({"fato_indicador_territorial_linhas": len(tables["Fato_Indicador_Territorial"]),
                  "dim_local_linhas": len(tables["Dim_Local"])})
    qc = validate(d)
    if qc["status"] != "APROVADO":
        raise AssertionError(qc)
    (OUTPUTS / "indicadores.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUTS / "controle_qualidade.json").write_text(
        json.dumps({"checagens": qc, "auditoria": audit}, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame([{"arquivo": p.name, "bytes": p.stat().st_size, "sha256": sha256_file(p)}
                  for p in sorted(RAW.glob("*")) if p.is_file()]).to_csv(OUTPUTS / "manifesto_fontes_sha256.csv", index=False)
    return summary
