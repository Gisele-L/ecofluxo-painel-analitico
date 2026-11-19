"""Simulação de novos pontos de recicláveis (cenário analítico, não operação)."""
from __future__ import annotations

import json

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import contains_xy
from shapely.ops import unary_union

from .config import CRS_METRIC, OUTPUTS

CELL_M = 50.0
CANDIDATE_STEP_M = 150.0
RADIUS_M = 500.0
MAX_SITES = 7

AGRUPAMENTOS = {
    "Agrupamento RPA 3": ["Brejo da Guabiraba", "Córrego do Jenipapo", "Nova Descoberta"],
    "Agrupamento RPAs 2 e 3": ["Alto Santa Terezinha", "Água Fria", "Beberibe", "Alto José do Pinho",
                               "Alto José Bonifácio"],
}
COMBINADO = "Dois agrupamentos (pontos por agrupamento)"
TOP10 = "10 bairros prioritários (IPV)"


def demand_grid(region: gpd.GeoDataFrame, cell_m: float = CELL_M):
    region = region.to_crs(CRS_METRIC)
    minx, miny, maxx, maxy = unary_union(region.geometry.to_list()).bounds
    gx, gy = np.meshgrid(np.arange(minx + cell_m / 2, maxx, cell_m), np.arange(miny + cell_m / 2, maxy, cell_m))
    gx, gy = gx.ravel(), gy.ravel()
    weight = np.zeros(gx.size)
    inside = np.zeros(gx.size, dtype=bool)
    for _, row in region.iterrows():
        mask = contains_xy(row.geometry, gx, gy) & ~inside
        weight[mask] = float(row.moradores_domicilios_responsaveis) / row.geometry.area * cell_m ** 2
        inside |= mask
    return gx[inside], gy[inside], weight[inside]


def covered_mask(cx: np.ndarray, cy: np.ndarray, xy: np.ndarray, radius_m: float = RADIUS_M) -> np.ndarray:
    covered = np.zeros(cx.size, dtype=bool)
    for x, y in xy:
        covered |= (cx - x) ** 2 + (cy - y) ** 2 <= radius_m ** 2
    return covered


def grid_coverage_pct(region: gpd.GeoDataFrame, points: gpd.GeoDataFrame) -> float:
    pts = points.to_crs(CRS_METRIC)
    cx, cy, w = demand_grid(region)
    cov = covered_mask(cx, cy, np.c_[pts.geometry.x, pts.geometry.y])
    return float(100 * w[cov].sum() / w.sum())


def greedy(region: gpd.GeoDataFrame, points: gpd.GeoDataFrame, max_sites: int = MAX_SITES) -> dict:
    pts = points.to_crs(CRS_METRIC)
    cx, cy, w = demand_grid(region)
    cov = covered_mask(cx, cy, np.c_[pts.geometry.x, pts.geometry.y])
    step = int(round(CANDIDATE_STEP_M / CELL_M))
    pick = (np.round((cx - cx.min()) / CELL_M) % step == 0) & (np.round((cy - cy.min()) / CELL_M) % step == 0)
    cand = np.c_[cx[pick], cy[pick]]
    covered_people = [float(w[cov].sum())]
    chosen = []
    for _ in range(max_sites):
        gains = np.array([w[((cx - x) ** 2 + (cy - y) ** 2 <= RADIUS_M ** 2) & ~cov].sum() for x, y in cand])
        j = int(np.argmax(gains))
        if gains[j] <= 0:
            break
        x, y = cand[j]
        cov |= (cx - x) ** 2 + (cy - y) ** 2 <= RADIUS_M ** 2
        chosen.append((float(x), float(y)))
        covered_people.append(float(w[cov].sum()))
    return {"moradores_grade": float(w.sum()), "moradores_cobertos_grade": covered_people, "pontos_utm": chosen}


def run_scenario(base: gpd.GeoDataFrame, points: gpd.GeoDataFrame, max_sites: int = MAX_SITES) -> dict:
    base = base.to_crs(CRS_METRIC)
    top10 = list(base.dropna(subset=["ipv"]).sort_values(["ipv", "bairro"], ascending=[False, True]).head(10).bairro)
    cases = {TOP10: top10} | AGRUPAMENTOS
    raw, final = {}, {}
    for name, bairros in cases.items():
        region = base.loc[base.bairro.isin(bairros)]
        if len(region) != len(bairros):
            raise ValueError(f"Bairros não encontrados no recorte {name}")
        r = greedy(region, points, max_sites)
        raw[name] = r
        pos = gpd.GeoSeries(gpd.points_from_xy(*zip(*r["pontos_utm"])), crs=CRS_METRIC).to_crs("EPSG:4326") \
            if r["pontos_utm"] else []
        final[name] = {
            "bairros": bairros, "moradores": int(region.moradores_domicilios_responsaveis.sum()),
            "cobertura_por_qtd_pontos": {str(n): 100 * c / r["moradores_grade"] for n, c in enumerate(r["moradores_cobertos_grade"])},
            "posicoes_teoricas": [{"ordem": i + 1, "longitude": round(p.x, 6), "latitude": round(p.y, 6)} for i, p in enumerate(pos)],
        }
    a, b = (raw[k] for k in AGRUPAMENTOS)
    n = min(len(a["moradores_cobertos_grade"]), len(b["moradores_cobertos_grade"]))
    total = a["moradores_grade"] + b["moradores_grade"]
    final[COMBINADO] = {
        "bairros": sum(AGRUPAMENTOS.values(), []),
        "moradores": sum(final[k]["moradores"] for k in AGRUPAMENTOS),
        "cobertura_por_qtd_pontos": {str(i): 100 * (a["moradores_cobertos_grade"][i] + b["moradores_cobertos_grade"][i]) / total for i in range(n)},
        "posicoes_teoricas": [],
    }
    for v in final.values():
        v.update({"cobertura_inicial_pct": v["cobertura_por_qtd_pontos"]["0"], "grade_m": CELL_M,
                  "candidatos_a_cada_m": CANDIDATE_STEP_M, "raio_m": RADIUS_M,
                  "nota": "SIMULAÇÃO: grade de 50 m, candidatos a cada 150 m, linha reta, população uniforme por bairro."})
    return final


def export() -> dict:
    from . import modelo
    result = run_scenario(modelo.bairros(), modelo.pontos())
    (OUTPUTS / "simulacao_pontos.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [{"recorte": name, "novos_pontos": int(n), "moradores": s["moradores"], "cobertura_estimada_pct": v,
             "classificacao": "SIMULAÇÃO"}
            for name, s in result.items() for n, v in s["cobertura_por_qtd_pontos"].items()]
    pd.DataFrame(rows).to_csv(OUTPUTS / "simulacao_cobertura.csv", index=False, encoding="utf-8-sig")
    return result
