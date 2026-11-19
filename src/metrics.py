"""Cálculos territoriais: cobertura, quintis de renda e IPV."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.ops import unary_union

from .config import CRS_METRIC


def safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator) / float(denominator) if denominator else float("nan")


def coverage_by_neighborhood(bairros: gpd.GeoDataFrame, pontos: gpd.GeoDataFrame, zeis: gpd.GeoDataFrame,
                             radius_m: int = 500) -> gpd.GeoDataFrame:
    if radius_m <= 0 or radius_m > 10000:
        raise ValueError("O raio deve ser positivo e de no máximo 10 km.")
    b = bairros.to_crs(CRS_METRIC).copy()
    pts = pontos.to_crs(CRS_METRIC)
    z = zeis.to_crs(CRS_METRIC)
    b["area_km2"] = b.geometry.area / 1_000_000
    buffer_union = unary_union(pts.geometry.buffer(radius_m).to_list()) if len(pts) else None
    zeis_union = unary_union(z.geometry.to_list()) if len(z) else None
    b["area_coberta_km2"] = 0.0 if buffer_union is None else b.geometry.intersection(buffer_union).area / 1_000_000
    if zeis_union is None:
        b["area_zeis_km2"] = 0.0
        b["area_zeis_coberta_km2"] = 0.0
    else:
        zeis_part = b.geometry.intersection(zeis_union)
        b["area_zeis_km2"] = zeis_part.area / 1_000_000
        b["area_zeis_coberta_km2"] = (zeis_part.intersection(buffer_union).area / 1_000_000
                                      if buffer_union is not None else 0.0)
    b["cobertura_area_pct"] = 100 * b["area_coberta_km2"] / b["area_km2"].replace(0, np.nan)
    b["zeis_area_pct"] = 100 * b["area_zeis_km2"] / b["area_km2"].replace(0, np.nan)
    b["cobertura_area_zeis_pct"] = 100 * b["area_zeis_coberta_km2"] / b["area_zeis_km2"].replace(0, np.nan)
    join = gpd.sjoin(pts[["geometry"]], b[["bairro_key", "geometry"]], how="left", predicate="within")
    b["registros_no_bairro"] = b["bairro_key"].map(join.groupby("bairro_key").size()).fillna(0).astype(int)
    return b.to_crs("EPSG:4326")


def enrich_population(base: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    result = base.copy()
    result["moradores_cobertos_estimados"] = result["moradores_domicilios_responsaveis"] * result["cobertura_area_pct"] / 100
    result["moradores_descobertos_estimados"] = (result["moradores_domicilios_responsaveis"]
                                                 - result["moradores_cobertos_estimados"])
    return result


def population_summary(base: pd.DataFrame) -> dict:
    pop = float(base["moradores_domicilios_responsaveis"].sum())
    covered = float(base["moradores_cobertos_estimados"].sum())
    return {"moradores": int(pop), "moradores_cobertos_estimados": covered,
            "cobertura_populacional_estimada_pct": 100 * safe_ratio(covered, pop),
            "pontos_por_10mil": 10000 * safe_ratio(float(base.registros_no_bairro.sum()), pop),
            "moradores_bairros_sem_ponto": int(base.loc[base.registros_no_bairro.eq(0),
                                                       "moradores_domicilios_responsaveis"].sum())}


def quintile_labels_population(df: pd.DataFrame) -> pd.Series:
    d = df.sort_values(["renda_media_responsavel", "bairro_key"]).copy()
    cum = d["moradores_domicilios_responsaveis"].cumsum().to_numpy()
    total = float(cum[-1])
    cuts = [int(np.searchsorted(cum, total * i / 5, side="left")) for i in range(1, 5)]
    result = pd.Series(index=d.index, dtype="object")
    start = 0
    for group, stop in enumerate(cuts + [len(d)], 1):
        result.loc[d.iloc[start:stop].index] = f"Q{group}"
        start = stop
    return result.reindex(df.index)


def summarize_quintiles(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["quintil_renda"] = quintile_labels_population(d)
    g = d.groupby("quintil_renda", as_index=False).agg(
        bairros=("bairro_key", "count"), moradores=("moradores_domicilios_responsaveis", "sum"),
        pontos=("registros_no_bairro", "sum"),
        moradores_cobertos_500m=("moradores_cobertos_500m", "sum"),
        moradores_cobertos_1000m=("moradores_cobertos_1000m", "sum"),
        area_zeis_km2=("area_zeis_km2", "sum"), area_km2=("area_km2", "sum"),
        renda_min=("renda_media_responsavel", "min"), renda_max=("renda_media_responsavel", "max"),
    )
    for raio in (500, 1000):
        g[f"cobertura_populacional_{raio}m_pct"] = 100 * g[f"moradores_cobertos_{raio}m"] / g.moradores
    g["pontos_por_10mil"] = 1e4 * g.pontos / g.moradores
    g["area_zeis_pct"] = 100 * g.area_zeis_km2 / g.area_km2
    return g.sort_values("quintil_renda")


def calculate_ipv(df: pd.DataFrame, min_population: int = 5000) -> pd.DataFrame:
    d = df.copy()
    log_income = np.log(d["renda_media_responsavel"].astype(float))
    d["ipv_lacuna"] = 1 - d["cobertura_area_500m_pct"] / 100
    d["ipv_renda"] = 1 - (log_income - log_income.min()) / (log_income.max() - log_income.min())
    d["ipv_zeis"] = d["zeis_area_pct"] / 100
    d["ipv"] = 100 * (d["ipv_lacuna"] + d["ipv_renda"] + d["ipv_zeis"]) / 3
    d.loc[d["moradores_domicilios_responsaveis"] < min_population, "ipv"] = np.nan
    d["posicao_ipv"] = d["ipv"].rank(method="first", ascending=False).astype("Int64")
    return d


def ipv_sensitivity(d: pd.DataFrame) -> dict:
    eligible = d.loc[d.elegivel_ipv].copy()
    eligible["sem_zeis"] = 100 * (eligible.ipv_lacuna + eligible.ipv_renda) / 2
    eligible["lacuna_dobrada"] = 100 * (2 * eligible.ipv_lacuna + eligible.ipv_renda + eligible.ipv_zeis) / 4
    top10 = set(d.dropna(subset=["ipv"]).sort_values(["ipv", "bairro"], ascending=[False, True]).head(10).bairro_key)
    return {"sobreposicao_top10_sem_zeis": len(top10 & set(eligible.nlargest(10, "sem_zeis").bairro_key)),
            "sobreposicao_top10_lacuna_peso_duplo": len(top10 & set(eligible.nlargest(10, "lacuna_dobrada").bairro_key))}


def territorial_kpis(d: pd.DataFrame) -> dict:
    pop = d.moradores_domicilios_responsaveis
    sem_ponto = d.registros_no_bairro.eq(0)
    quin = summarize_quintiles(d)
    q1, q5 = quin.iloc[0], quin.iloc[-1]
    zeis50 = d.zeis_area_pct.ge(50)
    top10 = d.dropna(subset=["ipv"]).sort_values(["ipv", "bairro"], ascending=[False, True]).head(10)
    return {
        "bairros_total": int(len(d)),
        "moradores_total": int(pop.sum()),
        "pontos_reciclaveis_secos": int(d.registros_no_bairro.sum()),
        "pontos_recife_todos": int(d.registros_todos.sum()),
        "bairros_sem_ponto": int(sem_ponto.sum()),
        "moradores_bairros_sem_ponto": int(pop[sem_ponto].sum()),
        "pct_moradores_bairros_sem_ponto": 100 * float(pop[sem_ponto].sum()) / float(pop.sum()),
        "moradores_cobertos_500m_estimados": float(d.moradores_cobertos_500m.sum()),
        "cobertura_populacional_500m_pct": 100 * safe_ratio(d.moradores_cobertos_500m.sum(), pop.sum()),
        "cobertura_populacional_1000m_pct": 100 * safe_ratio(d.moradores_cobertos_1000m.sum(), pop.sum()),
        "pontos_por_10mil": 10000 * safe_ratio(d.registros_no_bairro.sum(), pop.sum()),
        "cobertura_500m_q1_pct": float(q1.cobertura_populacional_500m_pct),
        "cobertura_500m_q5_pct": float(q5.cobertura_populacional_500m_pct),
        "razao_q5_q1": float(q5.cobertura_populacional_500m_pct / q1.cobertura_populacional_500m_pct),
        "pontos_por_10mil_q1": float(q1.pontos_por_10mil),
        "pontos_por_10mil_q5": float(q5.pontos_por_10mil),
        "spearman_renda_media_cobertura_area": float(
            d[["renda_media_responsavel", "cobertura_area_500m_pct"]].corr(method="spearman").iloc[0, 1]),
        "spearman_zeis_cobertura_area": float(d[["zeis_area_pct", "cobertura_area_500m_pct"]].corr(method="spearman").iloc[0, 1]),
        "bairros_zeis_50pct_ou_mais": int(zeis50.sum()),
        "moradores_bairros_zeis_50pct_ou_mais": int(pop[zeis50].sum()),
        "cobertura_500m_bairros_zeis_50pct_ou_mais_pct": 100 * safe_ratio(d.loc[zeis50, "moradores_cobertos_500m"].sum(),
                                                                          pop[zeis50].sum()),
        "cobertura_500m_demais_bairros_pct": 100 * safe_ratio(d.loc[~zeis50, "moradores_cobertos_500m"].sum(),
                                                              pop[~zeis50].sum()),
        "bairros_eligible_ipv": int(d.elegivel_ipv.sum()),
        "top10_ipv_bairros": list(top10.bairro),
        "top10_ipv_moradores": int(top10.moradores_domicilios_responsaveis.sum()),
        "top10_ipv_cobertura_populacional_500m_exata_pct": 100 * safe_ratio(
            top10.moradores_cobertos_500m.sum(), top10.moradores_domicilios_responsaveis.sum()),
        "sensibilidade_ipv": ipv_sensitivity(d),
    }


def aggregate_rpa(df: pd.DataFrame, radius_m: int = 500) -> pd.DataFrame:
    g = df.groupby("rpa", as_index=False).agg(
        bairros=("bairro_key", "count"), moradores=("moradores_domicilios_responsaveis", "sum"),
        responsaveis=("responsaveis_domicilios", "sum"), soma_renda_ponderada=("renda_ponderada", "sum"),
        pontos=("registros_no_bairro", "sum"), moradores_cobertos=(f"moradores_cobertos_{radius_m}m", "sum"),
        area_zeis_km2=("area_zeis_km2", "sum"), area_km2=("area_km2", "sum"))
    g["pontos_por_10mil"] = 1e4 * g.pontos / g.moradores
    g["cobertura_populacional_pct"] = 100 * g.moradores_cobertos / g.moradores
    g["rendimento_medio_responsavel"] = g.soma_renda_ponderada / g.responsaveis
    g["area_zeis_pct"] = 100 * g.area_zeis_km2 / g.area_km2
    return g


def zeis_coverage_city(zeis: gpd.GeoDataFrame, pontos: gpd.GeoDataFrame, radius_m: int = 500) -> dict:
    z = unary_union(zeis.to_crs(CRS_METRIC).geometry.to_list())
    buf = unary_union(pontos.to_crs(CRS_METRIC).geometry.buffer(radius_m).to_list())
    return {"area_zeis_km2": z.area / 1e6, "area_zeis_coberta_km2": z.intersection(buf).area / 1e6,
            "cobertura_area_zeis_pct": 100 * z.intersection(buf).area / z.area}
