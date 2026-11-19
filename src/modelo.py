"""Camada semântica: consulta o Data Warehouse e calcula as medidas derivadas usadas no painel."""
from __future__ import annotations

import sqlite3

import geopandas as gpd
import pandas as pd

from .config import DW_PATH, PROCESSED
from .etl import AJUSTES_NOME, key
from .metrics import calculate_ipv, quintile_labels_population, territorial_kpis

COLUNAS = {
    "moradores": "moradores_domicilios_responsaveis",
    "domicilios": "responsaveis_domicilios",
    "renda_media_resp": "renda_media_responsavel",
    "renda_mediana_resp": "renda_mediana_responsavel",
    "pontos_totais": "registros_todos",
    "pontos_reciclaveis": "registros_no_bairro",
}


def conectar() -> sqlite3.Connection:
    if not DW_PATH.exists():
        from .dw import construir
        construir()
    return sqlite3.connect(f"file:{DW_PATH.as_posix()}?mode=ro", uri=True)


def consultar(sql: str, params: tuple = ()) -> pd.DataFrame:
    with conectar() as con:
        return pd.read_sql_query(sql, con, params=params)


def bairros() -> gpd.GeoDataFrame:
    d = consultar("SELECT * FROM vw_bairro_indicadores ORDER BY id_bairro").rename(columns=COLUNAS)
    for coluna in ("moradores_domicilios_responsaveis", "responsaveis_domicilios", "registros_todos", "registros_no_bairro"):
        d[coluna] = d[coluna].round().astype(int)
    d["bairro_key"] = d["bairro"].map(key).replace(AJUSTES_NOME)
    moradores = d["moradores_domicilios_responsaveis"].where(lambda s: s > 0)
    d["zeis_area_pct"] = 100 * d["area_zeis_km2"] / d["area_km2"]
    d["cobertura_area_500m_pct"] = 100 * d["moradores_cobertos_500m"] / moradores
    d["cobertura_area_1000m_pct"] = 100 * d["moradores_cobertos_1000m"] / moradores
    d["renda_ponderada"] = d["renda_media_responsavel"] * d["responsaveis_domicilios"]
    d = calculate_ipv(d)
    d["quintil_renda"] = quintile_labels_population(d)
    d["elegivel_ipv"] = d["moradores_domicilios_responsaveis"].ge(5000)
    geometria = gpd.read_file(PROCESSED / "bairros_geometria.geojson")
    return gpd.GeoDataFrame(d.merge(geometria, on="id_bairro", validate="one_to_one"),
                            geometry="geometry", crs=geometria.crs)


def pontos(somente_reciclaveis: bool = True) -> gpd.GeoDataFrame:
    filtro = "WHERE l.aceita_reciclavel = 1" if somente_reciclaveis else ""
    p = consultar(f"""
        SELECT l.id_local, l.nome, l.tipo_local, l.aceita_reciclavel, l.latitude, l.longitude,
               b.nome AS bairro_geo, b.id_rpa AS rpa
        FROM Dim_Local l JOIN Dim_Bairro b ON b.id_bairro = l.id_bairro {filtro}
        ORDER BY l.id_local""")
    return gpd.GeoDataFrame(p, geometry=gpd.points_from_xy(p.longitude, p.latitude), crs="EPSG:4326")


def indicadores(base: pd.DataFrame) -> dict:
    return territorial_kpis(base)


def tabelas() -> pd.DataFrame:
    with conectar() as con:
        nomes = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        linhas = [con.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0] for n in nomes]
    t = pd.DataFrame({"tabela": nomes, "linhas": linhas})
    t["tipo"] = t.tabela.str.startswith("Fato").map({True: "Fato", False: "Dimensão"})
    return t.sort_values(["tipo", "tabela"], ascending=[False, True]).reset_index(drop=True)


def fontes() -> pd.DataFrame:
    return consultar("SELECT * FROM Dim_Fonte_Dado ORDER BY id_fonte_dado")


def indicadores_do_modelo() -> pd.DataFrame:
    return consultar("""
        SELECT i.codigo, i.nome, i.unidade, i.regra_agregacao, i.id_fonte_dado, t.data AS data_referencia,
               COUNT(*) AS linhas
        FROM Fato_Indicador_Territorial f
        JOIN Dim_Indicador i ON i.id_indicador = f.id_indicador
        JOIN Dim_Tempo t ON t.id_tempo = f.id_tempo_referencia
        GROUP BY i.id_indicador, i.codigo, i.nome, i.unidade, i.regra_agregacao, i.id_fonte_dado, t.data
        ORDER BY i.id_indicador""")
