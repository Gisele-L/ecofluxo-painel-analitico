"""Métricas territoriais, simulação e privacidade."""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Point, box

from src import modelo
from src.config import OUTPUTS, PROCESSED
from src.etl import read_cadinsan
from src.metrics import coverage_by_neighborhood, quintile_labels_population, safe_ratio, summarize_quintiles


@pytest.fixture(scope="module")
def data():
    base = modelo.bairros()
    ind = json.loads((OUTPUTS / "indicadores.json").read_text(encoding="utf-8"))
    return base, ind


def test_bases_e_conciliacao(data):
    b, m = data
    assert len(b) == 94 and b.cod_bairro_ibge.nunique() == 94
    assert b.moradores_domicilios_responsaveis.sum() == 1479478
    assert m["pontos_csv_total"] == 244 and m["pontos_recife_todos"] == 225 and m["pontos_reciclaveis_secos"] == 144


def test_cobertura_500m_e_1km(data):
    b, m = data
    pop = b.moradores_domicilios_responsaveis.sum()
    assert b.moradores_cobertos_500m.sum() / pop * 100 == pytest.approx(32.803865, abs=.01)
    assert b.moradores_cobertos_1000m.sum() / pop * 100 == pytest.approx(68.4830, abs=.02)
    assert m["moradores_bairros_sem_ponto"] == 544161


def test_quintis(data):
    b, m = data
    assert quintile_labels_population(b).value_counts().sort_index().tolist() == [21, 20, 14, 17, 22]
    assert summarize_quintiles(b).moradores.tolist() == [285756, 303057, 260275, 314280, 316110]
    assert m["razao_q5_q1"] == pytest.approx(2.2, abs=.04)


def test_ipv_top10(data):
    b, m = data
    assert b.ipv.notna().sum() == 72
    assert b.dropna(subset=["ipv"]).sort_values("ipv", ascending=False).head(10).bairro.tolist() == [
        "Córrego do Jenipapo", "Alto Santa Terezinha", "Brejo da Guabiraba", "Coqueiral", "Nova Descoberta",
        "Mangueira", "Água Fria", "Beberibe", "Alto José do Pinho", "Alto José Bonifácio"]
    assert m["top10_ipv_moradores"] == 138861
    assert m["sensibilidade_ipv"] == {"sobreposicao_top10_sem_zeis": 6, "sobreposicao_top10_lacuna_peso_duplo": 8}


def test_cadunico_somente_agregado(data):
    c = data[1]["cadunico_municipal"]
    assert c["familias"] == 36340 and c["pessoas"] == 82346
    assert c["pct_mediana_gasto_sobre_renda_declarada"] == pytest.approx(65.7, abs=.1)
    assert not any(k in c for k in ("cod_familiar", "cpf", "nome", "endereco"))


def test_cadinsan():
    c = read_cadinsan()
    assert c["familias_cadunico"] == 133594 and c["familias_em_risco_inseguranca_alimentar_grave"] == 23687
    assert c["pct_recalculado"] == pytest.approx(17.73059, abs=.01)


def test_simulacao_deterministica():
    from src.scenario import run_scenario
    base, pontos = modelo.bairros(), modelo.pontos()
    assert run_scenario(base, pontos, 3) == run_scenario(base, pontos, 3)
    sc = json.loads((OUTPUTS / "simulacao_pontos.json").read_text(encoding="utf-8"))
    for v in sc.values():
        seq = list(v["cobertura_por_qtd_pontos"].values())
        assert all(a <= b for a, b in zip(seq, seq[1:]))


def test_buffers_sem_dupla_contagem():
    square = gpd.GeoDataFrame({"bairro_key": ["b"], "moradores_domicilios_responsaveis": [100]},
                              geometry=[box(0, 0, 1000, 1000)], crs="EPSG:31985")
    pts = gpd.GeoDataFrame({"id": [1, 2]}, geometry=[Point(500, 500), Point(500, 500)], crs="EPSG:31985")
    z = gpd.GeoDataFrame({"id": [1]}, geometry=[box(0, 0, 500, 500)], crs="EPSG:31985")
    out = coverage_by_neighborhood(square, pts, z, 100)
    assert out.area_coberta_km2.iloc[0] == pytest.approx(Point(500, 500).buffer(100).area / 1e6, rel=1e-8)
    assert out.registros_no_bairro.iloc[0] == 2


def test_cobertura_de_area_e_de_moradores_sao_diferentes(data):
    b, m = data
    assert np.isnan(safe_ratio(5, 0)) and safe_ratio(5, 2) == 2.5
    territorial = (b.area_km2 * b.cobertura_area_500m_pct / 100).sum() / b.area_km2.sum() * 100
    assert territorial == pytest.approx(22.2645, abs=.02)
    assert abs(territorial - m["cobertura_populacional_500m_pct"]) > 9


def test_sem_microdados_do_cadunico():
    root = Path(__file__).resolve().parents[1]
    assert not any("cadastro-unico-2023" in p.name.lower() for p in root.rglob("*") if p.is_file())
    c = json.loads((PROCESSED / "cadunico_agregado_municipal_2023.json").read_text(encoding="utf-8"))
    assert not any(k in c for k in ("cod_familiar", "cpf", "nome", "endereco"))


def test_mapa_funciona_offline(data):
    from src.charts import mapa_cobertura
    assert {t.type for t in mapa_cobertura(data[0], 500).data} == {"scatter"}
