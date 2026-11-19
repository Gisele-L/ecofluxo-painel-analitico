"""Relatório HTML autocontido, com as mesmas seções do painel, gerado a partir do Data Warehouse."""
import base64
import io
import json

import pandas as pd
from PIL import Image
import plotly.io as pio

from src import charts as ch
from src import modelo
from src.config import DW_PATH, OUTPUTS, ROOT
from src.metrics import aggregate_rpa, summarize_quintiles
from src.ui import tema_css, cabecalho, rodape, kpi, kpis, secao, aviso, tabela, br, titulo_cartao as ct


def main():
    b = modelo.bairros()
    pts = modelo.pontos()
    m = json.loads((OUTPUTS / "indicadores.json").read_text(encoding="utf-8"))
    m.update(modelo.indicadores(b))
    s = json.loads((OUTPUTS / "simulacao_pontos.json").read_text(encoding="utf-8"))
    r = aggregate_rpa(b, 500).rename(columns={"moradores_cobertos": "moradores_cobertos_500m",
                                              "cobertura_populacional_pct": "cobertura_populacional_500m_pct"})
    q = summarize_quintiles(b)
    tabs = modelo.tabelas()
    figura = Image.open(ROOT / "assets" / "modelo_snowflake.png").convert("RGB")
    figura.thumbnail((1100, 1400))
    buffer = io.BytesIO()
    figura.save(buffer, "JPEG", quality=82, optimize=True)
    figura_b64 = base64.b64encode(buffer.getvalue()).decode()
    cad, cun = m["cadinsan_municipal"], m.get("cadunico_municipal") or {}
    top = b.dropna(subset=["ipv"]).sort_values("ipv", ascending=False).head(10)
    figs = [ch.mapa_cobertura(b, 500, pts), ch.barras_rpa(r, 500), ch.quintis(q), ch.dispersao_renda(b, m["top10_ipv_bairros"]),
            ch.barras_ipv(top), ch.mapa_cobertura(b, 500, None, m["top10_ipv_bairros"], colorir=False, height=470),
            ch.linhas_cenario(s)]
    g = [pio.to_html(f, include_plotlyjs=("inline" if i == 0 else False), full_html=False, config={"displayModeBar": False,
                                                                                                    "responsive": True})
         for i, f in enumerate(figs)]
    comb = s["Dois agrupamentos (pontos por agrupamento)"]["cobertura_por_qtd_pontos"]
    t10 = s["10 bairros prioritários (IPV)"]["cobertura_por_qtd_pontos"]

    tq = q[["quintil_renda", "renda_min", "renda_max", "bairros", "moradores", "cobertura_populacional_500m_pct",
            "cobertura_populacional_1000m_pct"]].copy()
    tq["renda_min"] = tq.apply(lambda x: f"R$ {br(x.renda_min, 0)} a R$ {br(x.renda_max, 0)}", axis=1)
    tq = tq.drop(columns="renda_max")
    tq.columns = ["Quintil", "Rendimento médio do responsável", "Bairros", "Moradores", "A até 500 m", "A até 1 km"]
    tt = top.assign(posicao_ipv=top.posicao_ipv.astype(int).astype(str))[
        ["posicao_ipv", "bairro", "rpa", "moradores_domicilios_responsaveis", "renda_media_responsavel",
         "cobertura_area_500m_pct", "zeis_area_pct", "ipv"]]
    tt.columns = ["#", "Bairro", "RPA", "Moradores", "Rendimento médio (R$)", "Área a até 500 m", "Área em ZEIS", "IPV"]
    ts = pd.DataFrame([[k, s[k]["moradores"]] + [s[k]["cobertura_por_qtd_pontos"][str(n)] for n in (0, 2, 3, 4)]
                       for k in ["Agrupamento RPA 3", "Agrupamento RPAs 2 e 3", "Dois agrupamentos (pontos por agrupamento)"]],
                      columns=["Recorte simulado", "Moradores", "Hoje", "Com 2 pontos", "Com 3 pontos", "Com 4 pontos"])
    pct = {c: "%" for c in ["Hoje", "Com 2 pontos", "Com 3 pontos", "Com 4 pontos", "A até 500 m", "A até 1 km",
                            "Área a até 500 m", "Área em ZEIS"]}

    tt6 = tabs.assign(situacao=tabs.linhas.map(lambda n: "carregada" if n else "vazia até o piloto"))
    tt6.columns = ["Tabela", "Linhas", "Tipo", "Situação"]

    def card(titulo, conteudo):
        return f'<div class="eco-card">{ct(titulo)}{conteudo}</div>'

    corpo = f"""
{cabecalho("Relatório analítico")}
<div class="eco-h1">Por que o EcoFluxo e por onde começar</div>
<div class="eco-sub">Recife · Bases públicas (Censo 2022, Prefeitura do Recife, CadÚnico 2023 e CadINSAN) organizadas no
Data Warehouse do projeto. Valores estimados e simulados aparecem sinalizados. Mesmo conteúdo do painel, para a cidade inteira
e raio de 500 m.</div>

{secao("1 · Reciclagem e fome no mesmo território", "Recife, dados municipais")}
{kpis([kpi(f"{br(cad['pct_recalculado'])}%", "das famílias do CadÚnico em risco de insegurança alimentar grave", "MDS, CadINSAN, jan/2024", "dark"),
       kpi(f"{br(cun['pct_mediana_gasto_sobre_renda_declarada'])}%", "da renda declarada vai para alimentação (mediana)", "CadÚnico 2023"),
       kpi(f"R$ {br(cun['renda_per_capita_mediana_brl'], 0)}", "de renda per capita declarada (mediana)", "CadÚnico 2023"),
       kpi(f"{br(m['setores_renda_ate_1sm']['pct'])}%", "dos domicílios em setores com renda mediana do responsável até 1 salário mínimo", "IBGE, Censo 2022")])}
{aviso("<b>Leitura:</b> o acesso à reciclagem e a pressão do gasto com comida se concentram nos mesmos bairros de menor renda. "
       "Os dados do CadÚnico e do CadINSAN são municipais; não existem por bairro.")}

{secao("2 · Quem mora perto de um ponto de recicláveis", "Resultados calculados")}
{kpis([kpi(f"{br(m['cobertura_populacional_500m_pct'])}%", "dos moradores a até 500 m de um ponto", f"{br(m['moradores_cobertos_500m_estimados'], 0)} de {br(m['moradores_total'], 0)}"),
       kpi(f"{m['bairros_sem_ponto']} de {m['bairros_total']}", "bairros sem ponto de recicláveis", f"{br(m['moradores_bairros_sem_ponto'], 0)} moradores"),
       kpi(br(m['pontos_reciclaveis_secos'], 0), "pontos de recicláveis secos", "Base pública; não indica credenciamento"),
       kpi(br(m['pontos_por_10mil'], 2), "pontos por 10 mil moradores", "Contagem ÷ moradores × 10.000")])}
<div class="cols">{card("Área de cada bairro a até 500 m de um ponto", g[0])}{card("Moradores a até 500 m, por RPA", g[1])}</div>
{aviso("Estimativa: moradores do Censo 2022 × fração da área do bairro a até 500 m (linha reta) de algum ponto; moradores uniformes no bairro.")}

{secao("3 · O acesso cresce com a renda", "Resultados calculados")}
{kpis([kpi(f"{br(m['razao_q5_q1'])}×", "mais moradores cobertos no quintil de maior renda", f"Q5 {br(m['cobertura_500m_q5_pct'])}% · Q1 {br(m['cobertura_500m_q1_pct'])}%", "dark"),
       kpi(f"{br(m['cobertura_area_zeis_500m_pct'])}%", "da área de ZEIS a até 500 m de um ponto", f"ZEIS ocupam {br(m['area_zeis_pct_cidade'])}% da cidade"),
       kpi(f"{br(m['cobertura_500m_bairros_zeis_50pct_ou_mais_pct'])}% × {br(m['cobertura_500m_demais_bairros_pct'])}%",
           f"cobertura nos {m['bairros_zeis_50pct_ou_mais']} bairros com metade ou mais em ZEIS × demais", "")])}
<div class="cols">{card("Moradores cobertos por quintil de renda", g[2])}{card("Renda e cobertura, bairro a bairro", g[3])}</div>
{tabela(tq, {"Bairros": 0, "Moradores": 0, "A até 500 m": 1, "A até 1 km": 1}, pct)}

{secao("4 · Índice de Prioridade para Validação (IPV)", "Apoio à decisão")}
<div class="eco-formula"><b>IPV</b> = 100 × média de: (1) parte do bairro sem ponto a até 500 m · (2) renda média do responsável,
invertida em escala logarítmica · (3) parte da área em ZEIS. Calculado para os {m['bairros_eligible_ipv']} bairros com 5 mil moradores ou mais.</div>
{kpis([kpi(br(m['top10_ipv_moradores'], 0), "moradores nos 10 bairros prioritários", "Censo 2022", "dark"),
       kpi(f"{br(m['top10_ipv_cobertura_populacional_500m_pct'])}%", "deles vivem a até 500 m de um ponto", f"Grade de 50 m da simulação (exato: {br(m['top10_ipv_cobertura_populacional_500m_exata_pct'], 2)}%)"),
       kpi(f"{m['sensibilidade_ipv']['sobreposicao_top10_sem_zeis']}/10 e {m['sensibilidade_ipv']['sobreposicao_top10_lacuna_peso_duplo']}/10",
           "continuam no topo sem ZEIS e com a lacuna em dobro", "Teste de sensibilidade")])}
<div class="cols">{card("Os 10 bairros com maior IPV", g[4])}{card("Onde ficam", g[5])}</div>
{tabela(tt, {"Moradores": 0, "Rendimento médio (R$)": 0, "Área a até 500 m": 1, "Área em ZEIS": 1, "IPV": 1}, pct, destaque="IPV")}

{secao("5 · Quantos pontos mudariam o acesso", "Simulação", "sim")}
{aviso("<b>SIMULAÇÃO.</b> Posições teóricas escolhidas por algoritmo guloso numa grade de 50 m (candidatos a cada 150 m), "
       "linha reta e moradores uniformes no bairro. Não considera ladeiras, escadarias, imóveis, segurança nem credenciamento.", "sim")}
{kpis([kpi(f"{br(comb['0'])}% → {br(comb['3'])}%", "nos dois agrupamentos contíguos, com 3 pontos em cada", f"{br(s['Dois agrupamentos (pontos por agrupamento)']['moradores'], 0)} moradores · com 4 pontos: {br(comb['4'])}%", "sim"),
       kpi(f"{br(t10['0'])}% → {br(t10['7'])}%", "nos 10 bairros prioritários, com 7 pontos", f"{br(s['10 bairros prioritários (IPV)']['moradores'], 0)} moradores", "sim")])}
{card("Cobertura a 500 m conforme os pontos são adicionados", g[6])}
<div style="height:12px"></div>
{tabela(ts, {"Moradores": 0, "Hoje": 1, "Com 2 pontos": 1, "Com 3 pontos": 1, "Com 4 pontos": 1}, pct, destaque="Com 3 pontos")}

{secao("6 · Modelo e fontes", "Data Warehouse")}
<div class="cols">{card("Tabelas do modelo Snowflake (" + DW_PATH.name + ")", tabela(tt6, {"Linhas": 0}))}
{card("Como os números chegam aqui", "<p style='margin:6px 2px;line-height:1.55'>As bases públicas são tratadas em Python e "
      "gravadas na Fato_Indicador_Territorial (94 bairros × 10 indicadores) e nas dimensões Dim_Bairro → Dim_RPA → "
      "Dim_Municipio, Dim_Local, Dim_Tempo, Dim_Indicador e Dim_Fonte_Dado. O relatório lê a visão vw_bairro_indicadores "
      "e calcula cobertura percentual, quintis e IPV a partir dessas linhas. Os fatos operacionais existem no banco e ficam "
      "vazios até o piloto.</p>"
      f"<img alt='Modelo Snowflake' style='width:100%;margin-top:8px' src='data:image/jpeg;base64,{figura_b64}'>")}</div>
{aviso("Fontes: Prefeitura do Recife (pontos de coleta, bairros, RPAs, ZEIS e CadÚnico 2023 anonimizado, só agregados "
       "municipais), IBGE (Censo 2022) e MDS (CadINSAN jan/2024). Distância em linha reta (EPSG:31985) e moradores uniformes "
       "no bairro. Ponto na base pública não significa ponto ativo nem credenciado.", "note")}
{rodape()}
"""
    html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EcoFluxo · Relatório analítico</title><style>{tema_css()}
body{{margin:0;background:var(--papel);color:var(--mata);font-family:Inter,'Segoe UI',Arial,sans-serif}}
main{{max-width:1320px;margin:0 auto;padding:28px 28px 40px}}.cols{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:14px 0}}
@media(max-width:900px){{.cols{{grid-template-columns:1fr}}.eco-kpis{{grid-template-columns:1fr 1fr!important}}}}
</style></head><body><main>{corpo}</main></body></html>"""
    path = OUTPUTS / "EcoFluxo_Relatorio_Analitico.html"
    path.write_text(html, encoding="utf-8")
    print("HTML criado:", path, "bytes", path.stat().st_size)


if __name__ == "__main__":
    main()
