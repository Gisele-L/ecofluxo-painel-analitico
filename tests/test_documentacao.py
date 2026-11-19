"""Os 56 valores publicados na documentação v1.3, recalculados a partir do Data Warehouse."""
import json

import pytest

from src import modelo
from src.config import OUTPUTS

EXPECTED = [
    ("6.1", "Registros na base municipal de coleta", 244, 0, "pontos_csv_total"),
    ("6.1", "Registros dentro de Recife", 225, 0, "pontos_recife_todos"),
    ("6.1", "Pontos de recicláveis secos", 144, 0, "pontos_reciclaveis_secos"),
    ("6.1", "Bairros oficiais", 94, 0, "bairros_total"),
    ("6.1", "Bairros sem ponto de recicláveis", 47, 0, "bairros_sem_ponto"),
    ("6.1", "Moradores nesses bairros", 544161, 0, "moradores_bairros_sem_ponto"),
    ("6.1", "% dos moradores nesses bairros", 36.8, 1, "pct_moradores_bairros_sem_ponto"),
    ("6.1", "Moradores (Censo 2022)", 1479478, 0, "moradores_total"),
    ("6.1", "Moradores a até 500 m (%)", 32.8, 1, "cobertura_populacional_500m_pct"),
    ("6.1", "Moradores a até 1 km (%)", 68.5, 1, "cobertura_populacional_1000m_pct"),
    ("6.1", "Pontos por 10 mil moradores", 0.97, 2, "pontos_por_10mil"),
    ("Quadro 8", "Área em ZEIS na cidade (%)", 13.0, 1, "area_zeis_pct_cidade"),
    ("6.2", "Cobertura Q1 a 500 m (%)", 25.9, 1, "cobertura_500m_q1_pct"),
    ("6.2", "Cobertura Q5 a 500 m (%)", 56.2, 1, "cobertura_500m_q5_pct"),
    ("6.2", "Razão Q5 / Q1", 2.2, 1, "razao_q5_q1"),
    ("6.2", "Pontos por 10 mil, Q1", 0.66, 2, "pontos_por_10mil_q1"),
    ("6.2", "Pontos por 10 mil, Q5", 1.58, 2, "pontos_por_10mil_q5"),
    ("6.2", "Spearman renda × cobertura", 0.42, 2, "spearman_renda_media_cobertura_area"),
    ("6.2", "Spearman ZEIS × cobertura", -0.31, 2, "spearman_zeis_cobertura_area"),
    ("6.2", "Área de ZEIS a até 500 m (%)", 24.2, 1, "cobertura_area_zeis_500m_pct"),
    ("6.2", "Bairros com ≥ 50% da área em ZEIS", 23, 0, "bairros_zeis_50pct_ou_mais"),
    ("6.2", "Moradores desses bairros", 290999, 0, "moradores_bairros_zeis_50pct_ou_mais"),
    ("6.2", "Cobertura nesses bairros (%)", 23.9, 1, "cobertura_500m_bairros_zeis_50pct_ou_mais_pct"),
    ("6.2", "Cobertura nos demais bairros (%)", 35.0, 1, "cobertura_500m_demais_bairros_pct"),
    ("6.3", "CadINSAN: famílias em risco grave (%)", 17.7, 1, ("cadinsan_municipal", "pct_recalculado")),
    ("6.3", "CadÚnico: gasto alimentar ÷ renda, mediana (%)", 65.7, 1, ("cadunico_municipal", "pct_mediana_gasto_sobre_renda_declarada")),
    ("6.3", "CadÚnico: famílias com gasto ≥ 50% da renda (%)", 60.1, 1, ("cadunico_municipal", "pct_gasto_sobre_renda_ge_50_entre_validos")),
    ("6.4", "Bairros elegíveis ao IPV", 72, 0, "bairros_eligible_ipv"),
    ("6.4", "Moradores nos 10 prioritários", 138861, 0, "top10_ipv_moradores"),
    ("6.4", "Cobertura dos 10 prioritários (%, grade de 50 m)", 6.6, 1, "top10_ipv_cobertura_populacional_500m_pct"),
    ("6.4", "Sensibilidade: mantidos sem ZEIS", 6, 0, ("sensibilidade_ipv", "sobreposicao_top10_sem_zeis")),
    ("6.4", "Sensibilidade: mantidos com lacuna em dobro", 8, 0, ("sensibilidade_ipv", "sobreposicao_top10_lacuna_peso_duplo")),
]
QUADRO_11 = {"Córrego do Jenipapo": 97.5, "Alto Santa Terezinha": 97.5, "Brejo da Guabiraba": 96.9, "Coqueiral": 93.9,
             "Nova Descoberta": 92.9, "Mangueira": 92.5, "Água Fria": 85.3, "Beberibe": 85.0,
             "Alto José do Pinho": 84.7, "Alto José Bonifácio": 84.5}
QUADRO_12 = {
    "Agrupamento RPA 3": {0: 4.4, 2: 49.1, 3: 67.4, 4: 78.3},
    "Agrupamento RPAs 2 e 3": {0: 9.8, 2: 47.0, 3: 62.1, 4: 73.6},
    "Dois agrupamentos (pontos por agrupamento)": {0: 7.7, 2: 47.8, 3: 64.1, 4: 75.4},
    "10 bairros prioritários (IPV)": {0: 6.6, 7: 62.2},
}


@pytest.fixture(scope="module")
def valores():
    base = modelo.bairros()
    dados = json.loads((OUTPUTS / "indicadores.json").read_text(encoding="utf-8"))
    dados.update(modelo.indicadores(base))
    sim = json.loads((OUTPUTS / "simulacao_pontos.json").read_text(encoding="utf-8"))
    return base, dados, sim


def _valor(dados, chave):
    return dados[chave[0]][chave[1]] if isinstance(chave, tuple) else dados[chave]


@pytest.mark.parametrize("secao,nome,publicado,casas,chave", EXPECTED, ids=[e[1] for e in EXPECTED])
def test_indicadores_publicados(valores, secao, nome, publicado, casas, chave):
    assert round(float(_valor(valores[1], chave)), casas) == round(float(publicado), casas)


@pytest.mark.parametrize("bairro,publicado", QUADRO_11.items())
def test_quadro_11_ipv(valores, bairro, publicado):
    base = valores[0]
    assert round(float(base.loc[base.bairro == bairro, "ipv"].iloc[0]), 1) == publicado


@pytest.mark.parametrize("recorte,pontos,publicado",
                         [(r, n, v) for r, vals in QUADRO_12.items() for n, v in vals.items()])
def test_quadro_12_simulacao(valores, recorte, pontos, publicado):
    assert round(valores[2][recorte]["cobertura_por_qtd_pontos"][str(pontos)], 1) == publicado


def test_total_de_valores_conferidos():
    assert len(EXPECTED) + len(QUADRO_11) + sum(len(v) for v in QUADRO_12.values()) == 56
