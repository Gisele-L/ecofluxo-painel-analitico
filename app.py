"""EcoFluxo · Painel analítico (Streamlit). Lê o Data Warehouse e calcula as medidas na camada semântica."""
from __future__ import annotations

import io
import json
import zipfile

import geopandas as gpd
import pandas as pd
import streamlit as st

from src.config import DW_PATH, OUTPUTS, PROCESSED, ROOT
from src import charts as ch
from src import modelo
from src.ui import (tema_css, cabecalho, rodape, kpi, kpis, secao, aviso, tabela, br, titulo_cartao as ct)

st.set_page_config(page_title="EcoFluxo · Painel analítico", page_icon="assets/simbolo.svg", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown(f"<style>{tema_css()}</style>", unsafe_allow_html=True)
CFG = {"displayModeBar": False}

if not (OUTPUTS / "indicadores.json").exists() or not (OUTPUTS / "simulacao_pontos.json").exists():
    st.error("Saídas não encontradas. Rode o pipeline descrito no README.")
    st.stop()


@st.cache_data
def carregar():
    base = modelo.bairros()
    pontos = modelo.pontos()
    ind = json.loads((OUTPUTS / "indicadores.json").read_text(encoding="utf-8"))
    ind.update(modelo.indicadores(base))
    sim = json.loads((OUTPUTS / "simulacao_pontos.json").read_text(encoding="utf-8"))
    qc = json.loads((OUTPUTS / "controle_qualidade.json").read_text(encoding="utf-8"))
    return base, pontos, ind, sim, qc, modelo.tabelas(), modelo.indicadores_do_modelo(), modelo.fontes()


@st.cache_data
def pacote_modelo() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for csv in sorted(PROCESSED.glob("*_*.csv")):
            if csv.name.startswith(("Dim_", "Fato_")):
                z.write(csv, csv.name)
        z.write(ROOT / "sql" / "modelo_snowflake.sql", "modelo_snowflake.sql")
        z.write(ROOT / "sql" / "consultas_analiticas.sql", "consultas_analiticas.sql")
    return buffer.getvalue()


base, pontos, ind, sim, qc, tabelas_dw, indicadores_dw, fontes_dw = carregar()
cad, cun = ind["cadinsan_municipal"], ind.get("cadunico_municipal") or {}
top10 = ind["top10_ipv_bairros"]

st.markdown(cabecalho(), unsafe_allow_html=True)
st.markdown('<div class="eco-h1">Por que o EcoFluxo e por onde começar</div>', unsafe_allow_html=True)
st.markdown('<div class="eco-sub">Recife · Bases públicas (Censo 2022, Prefeitura do Recife, CadÚnico 2023 e CadINSAN) '
            'organizadas no Data Warehouse do projeto. Valores estimados e simulados aparecem sinalizados.</div>',
            unsafe_allow_html=True)

with st.sidebar:
    st.header("Filtros do território")
    rpas = st.multiselect("Regiões político-administrativas (RPA)", [1, 2, 3, 4, 5, 6], default=[1, 2, 3, 4, 5, 6],
                          format_func=lambda a: f"RPA {a}")
    raio = st.radio("Distância em linha reta até o ponto", [500, 1000], horizontal=True,
                    format_func=lambda x: "500 m" if x == 500 else "1 km")
    st.caption("Os filtros valem para as abas **Acesso** e **Desigualdade**. Quintis, IPV e simulação usam "
               "sempre os 94 bairros de Recife, como na documentação.")
    st.divider()
    st.caption("Dados lidos da Fato_Indicador_Territorial e das dimensões do modelo Snowflake. "
               "Bases consultadas em nov/2026 · Censo 2022 · CadÚnico 2023 · CadINSAN jan/2024.")
if not rpas:
    st.warning("Escolha ao menos uma RPA.")
    st.stop()

view = base[base.rpa.isin(rpas)].copy()
pts_view = pontos[pontos.bairro_geo.isin(view.bairro)]
pop = float(view.moradores_domicilios_responsaveis.sum())
cob = float(view[f"moradores_cobertos_{raio}m"].sum())
raio_txt = "500 m" if raio == 500 else "1 km"

abas = st.tabs(["1 · O problema", "2 · Acesso", "3 · Desigualdade", "4 · Onde começar (IPV)",
                "5 · Cenário simulado", "6 · Método e fontes"])

with abas[0]:
    st.markdown(secao("Reciclagem e fome no mesmo território", "Recife, dados municipais"), unsafe_allow_html=True)
    st.markdown(kpis([
        kpi(f"{br(cad['pct_recalculado'])}%", "das famílias do CadÚnico em risco de insegurança alimentar grave",
            f"MDS, CadINSAN, jan/2024 · {br(cad['familias_em_risco_inseguranca_alimentar_grave'], 0)} de "
            f"{br(cad['familias_cadunico'], 0)} famílias", "dark"),
        kpi(f"{br(cun['pct_mediana_gasto_sobre_renda_declarada'])}%" if cun else "–",
            "da renda declarada vai para alimentação (mediana)",
            f"CadÚnico 2023 · {br(cun['pct_gasto_sobre_renda_ge_50_entre_validos'])}% das famílias gastam metade ou mais" if cun else ""),
        kpi(f"R$ {br(cun['renda_per_capita_mediana_brl'], 0)}" if cun else "–", "de renda per capita declarada (mediana)",
            f"CadÚnico 2023 · {br(cun['pct_familias_renda_pc_ate_218'])}% até R$ 218 por pessoa" if cun else ""),
        kpi(f"{br(ind['setores_renda_ate_1sm']['pct'])}%", "dos domicílios estão em setores com renda mediana do responsável até 1 salário mínimo",
            "IBGE, Censo 2022, setores censitários"),
    ]), unsafe_allow_html=True)
    st.markdown(kpis([
        kpi(f"{br(ind['cobertura_populacional_500m_pct'])}%", "dos moradores vivem a até 500 m de um ponto de recicláveis",
            "Estimativa: Censo 2022 + pontos da Prefeitura"),
        kpi(f"{ind['bairros_sem_ponto']} de {ind['bairros_total']}", "bairros não têm nenhum ponto de recicláveis",
            f"{br(ind['moradores_bairros_sem_ponto'], 0)} moradores ({br(ind['pct_moradores_bairros_sem_ponto'])}%)"),
        kpi(f"{br(ind['razao_q5_q1'])}×", "mais cobertura nos bairros de maior renda",
            f"Q5 {br(ind['cobertura_500m_q5_pct'])}% contra Q1 {br(ind['cobertura_500m_q1_pct'])}%"),
        kpi(f"{br(cun['pct_pessoas_15mais_nao_leem'])}%" if cun else "–", "das pessoas com 15 anos ou mais declaram não saber ler",
            "CadÚnico 2023 · motiva cadastro assistido e leitura em áudio"),
    ]), unsafe_allow_html=True)
    st.markdown(aviso(
        "<b>Leitura:</b> o acesso à reciclagem e a pressão do gasto com comida se concentram nos mesmos bairros de menor renda. "
        "O EcoFluxo junta as duas pontas: recicláveis entregues em pontos credenciados viram EcoTickets, trocados por alimentos "
        "de produtores locais. Os dados do CadÚnico e do CadINSAN são <b>municipais</b>; não existem por bairro."), unsafe_allow_html=True)
    st.markdown(aviso("Dado citado na documentação, sem cálculo neste repositório: Recife recicla em média 1,3% dos resíduos "
                      "(TCE-PE, Acórdão 1418/2025).", "note"), unsafe_allow_html=True)

with abas[1]:
    st.markdown(secao(f"Quem mora perto de um ponto de recicláveis", "Resultados calculados"), unsafe_allow_html=True)
    st.markdown(kpis([
        kpi(f"{br(100 * cob / pop)}%", f"dos moradores a até {raio_txt} de um ponto", f"{br(cob, 0)} de {br(pop, 0)} moradores"),
        kpi(f"{int(view.registros_no_bairro.eq(0).sum())} de {len(view)}", "bairros sem ponto de recicláveis",
            "Um ponto vizinho ainda pode alcançar parte do bairro"),
        kpi(br(view.registros_no_bairro.sum(), 0), "pontos de recicláveis secos", "Base pública; não indica credenciamento"),
        kpi(br(10000 * view.registros_no_bairro.sum() / pop, 2), "pontos por 10 mil moradores", "Contagem ÷ moradores × 10.000"),
    ]), unsafe_allow_html=True)
    c1, c2 = st.columns([1.15, 1])
    with c1:
        with st.container(border=True):
            st.markdown(ct(f"Área de cada bairro a até {raio_txt} de um ponto"), unsafe_allow_html=True)
            st.plotly_chart(ch.mapa_cobertura(view, raio, pts_view), use_container_width=True, config=CFG)
    with c2:
        with st.container(border=True):
            st.markdown(ct(f"Moradores a até {raio_txt}, por RPA"), unsafe_allow_html=True)
            g = view.groupby("rpa", as_index=False).agg(moradores=("moradores_domicilios_responsaveis", "sum"),
                                                       pontos=("registros_no_bairro", "sum"),
                                                       moradores_cobertos_500m=("moradores_cobertos_500m", "sum"),
                                                       moradores_cobertos_1000m=("moradores_cobertos_1000m", "sum"))
            for r_ in (500, 1000):
                g[f"cobertura_populacional_{r_}m_pct"] = 100 * g[f"moradores_cobertos_{r_}m"] / g.moradores
            st.plotly_chart(ch.barras_rpa(g, raio), use_container_width=True, config=CFG)
        with st.container(border=True):
            st.markdown(ct(f"Da base municipal aos pontos usados na análise"), unsafe_allow_html=True)
            st.plotly_chart(ch.funil_pontos(ind["pontos_csv_total"], ind["pontos_recife_todos"], ind["pontos_reciclaveis_secos"]),
                            use_container_width=True, config=CFG)
    st.markdown(aviso("<b>Como se estima:</b> para cada bairro, moradores do Censo 2022 × fração da área do bairro a até "
                      f"{raio_txt} (linha reta) de algum ponto. Supõe moradores distribuídos de forma uniforme no bairro; "
                      "não mede trajeto a pé nem confirma se o ponto funciona."), unsafe_allow_html=True)
    with st.expander("Ver os indicadores de cada bairro"):
        t = view.sort_values("bairro")[["bairro", "rpa", "moradores_domicilios_responsaveis", "registros_no_bairro",
                                        f"cobertura_area_{raio}m_pct", f"moradores_cobertos_{raio}m", "zeis_area_pct"]]
        t.columns = ["Bairro", "RPA", "Moradores", "Pontos", f"Área a até {raio_txt}", "Moradores próximos (estim.)", "Área em ZEIS"]
        st.markdown(tabela(t, {"Moradores": 0, "Pontos": 0, f"Área a até {raio_txt}": 1, "Moradores próximos (estim.)": 0, "Área em ZEIS": 1},
                           {f"Área a até {raio_txt}": "%", "Área em ZEIS": "%"}), unsafe_allow_html=True)

with abas[2]:
    st.markdown(secao("O acesso cresce com a renda", "Resultados calculados"), unsafe_allow_html=True)
    q = view.groupby("quintil_renda", as_index=False).agg(
        bairros=("bairro_key", "count"), moradores=("moradores_domicilios_responsaveis", "sum"),
        pontos=("registros_no_bairro", "sum"), moradores_cobertos_500m=("moradores_cobertos_500m", "sum"),
        moradores_cobertos_1000m=("moradores_cobertos_1000m", "sum"), renda_min=("renda_media_responsavel", "min"),
        renda_max=("renda_media_responsavel", "max"))
    for r_ in (500, 1000):
        q[f"cobertura_populacional_{r_}m_pct"] = 100 * q[f"moradores_cobertos_{r_}m"] / q.moradores
    cards = [kpi(f"{br(ind['razao_q5_q1'])}×", "mais moradores cobertos no quintil de maior renda (Recife)",
                 f"Q5 {br(ind['cobertura_500m_q5_pct'])}% · Q1 {br(ind['cobertura_500m_q1_pct'])}%", "dark"),
             kpi(f"{br(ind['pontos_por_10mil_q1'], 2)} × {br(ind['pontos_por_10mil_q5'], 2)}", "pontos por 10 mil moradores, Q1 contra Q5", "Recife"),
             kpi(f"{br(ind['cobertura_area_zeis_500m_pct'])}%", "da área de ZEIS fica a até 500 m de um ponto",
                 f"ZEIS ocupam {br(ind['area_zeis_pct_cidade'])}% da área da cidade"),
             kpi(f"{br(ind['cobertura_500m_bairros_zeis_50pct_ou_mais_pct'])}% × {br(ind['cobertura_500m_demais_bairros_pct'])}%",
                 f"cobertura nos {ind['bairros_zeis_50pct_ou_mais']} bairros com metade ou mais em ZEIS × demais",
                 f"{br(ind['moradores_bairros_zeis_50pct_ou_mais'], 0)} moradores nesses bairros")]
    st.markdown(kpis(cards), unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown(ct(f"Moradores cobertos por quintil de renda"), unsafe_allow_html=True)
            st.plotly_chart(ch.quintis(q), use_container_width=True, config=CFG)
    with c2:
        with st.container(border=True):
            st.markdown(ct(f"Renda e cobertura, bairro a bairro"), unsafe_allow_html=True)
            st.plotly_chart(ch.dispersao_renda(view, top10), use_container_width=True, config=CFG)
    qt = q[["quintil_renda", "renda_min", "renda_max", "bairros", "moradores", "cobertura_populacional_500m_pct",
            "cobertura_populacional_1000m_pct"]].copy()
    qt["renda_min"] = qt.apply(lambda r: f"R$ {br(r.renda_min, 0)} a R$ {br(r.renda_max, 0)}", axis=1)
    qt = qt.drop(columns="renda_max")
    qt.columns = ["Quintil", "Rendimento médio do responsável", "Bairros", "Moradores", "A até 500 m", "A até 1 km"]
    st.markdown(tabela(qt, {"Bairros": 0, "Moradores": 0, "A até 500 m": 1, "A até 1 km": 1}, {"A até 500 m": "%", "A até 1 km": "%"}),
                unsafe_allow_html=True)
    st.markdown(aviso(f"Quintis formados com os 94 bairros ordenados pelo rendimento médio do responsável, cerca de 20% dos moradores "
                      f"em cada grupo. Correlação de Spearman entre renda e cobertura: {br(ind['spearman_renda_media_cobertura_area'], 2)}. "
                      "Rendimento do responsável não é renda familiar nem medida de fome."), unsafe_allow_html=True)

with abas[3]:
    st.markdown(secao("Índice de Prioridade para Validação (IPV)", "Apoio à decisão"), unsafe_allow_html=True)
    st.markdown('<div class="eco-formula"><b>IPV</b> = 100 × média de três componentes de 0 a 1: '
                '(1) parte do bairro <b>sem</b> ponto a até 500 m · (2) renda média do responsável, invertida em escala logarítmica · '
                f'(3) parte da área em ZEIS. Calculado para os {ind["bairros_eligible_ipv"]} bairros com 5 mil moradores ou mais.</div>',
                unsafe_allow_html=True)
    st.markdown(kpis([
        kpi(br(ind["top10_ipv_moradores"], 0), "moradores nos 10 bairros prioritários", "Censo 2022", "dark"),
        kpi(f"{br(ind['top10_ipv_cobertura_populacional_500m_pct'])}%", "deles vivem a até 500 m de um ponto",
            "Grade de 50 m, mesma base da simulação (exato: " + br(ind["top10_ipv_cobertura_populacional_500m_exata_pct"], 2) + "%)"),
        kpi(f"{ind['sensibilidade_ipv']['sobreposicao_top10_sem_zeis']}/10", "continuam no topo sem o componente ZEIS", "Teste de sensibilidade"),
        kpi(f"{ind['sensibilidade_ipv']['sobreposicao_top10_lacuna_peso_duplo']}/10", "continuam no topo com peso dobrado na falta de cobertura",
            "Teste de sensibilidade"),
    ]), unsafe_allow_html=True)
    top = base.dropna(subset=["ipv"]).sort_values("ipv", ascending=False).head(10)
    c1, c2 = st.columns([1, 1.1])
    with c1:
        with st.container(border=True):
            st.markdown(ct(f"Os 10 bairros com maior IPV"), unsafe_allow_html=True)
            st.plotly_chart(ch.barras_ipv(top), use_container_width=True, config=CFG)
    with c2:
        with st.container(border=True):
            st.markdown(ct(f"Onde ficam"), unsafe_allow_html=True)
            st.plotly_chart(ch.mapa_cobertura(base, 500, None, top10, colorir=False, height=470), use_container_width=True, config=CFG)
    top = top.assign(posicao_ipv=top.posicao_ipv.astype(int).astype(str))
    t = top[["posicao_ipv", "bairro", "rpa", "moradores_domicilios_responsaveis", "renda_media_responsavel",
             "cobertura_area_500m_pct", "zeis_area_pct", "ipv"]].copy()
    t.columns = ["#", "Bairro", "RPA", "Moradores", "Rendimento médio (R$)", "Área a até 500 m", "Área em ZEIS", "IPV"]
    st.markdown(tabela(t, {"Moradores": 0, "Rendimento médio (R$)": 0, "Área a até 500 m": 1, "Área em ZEIS": 1, "IPV": 1},
                       {"Área a até 500 m": "%", "Área em ZEIS": "%"}, destaque="IPV"), unsafe_allow_html=True)
    st.markdown(aviso("O IPV indica onde validar o piloto com moradores, cooperativas e produtores. Não mede fome nem risco de pessoas."),
                unsafe_allow_html=True)

with abas[4]:
    st.markdown(secao("Quantos pontos mudariam o acesso", "Simulação", "sim"), unsafe_allow_html=True)
    st.markdown(aviso("<b>SIMULAÇÃO.</b> Pontos em posições teóricas, escolhidos por algoritmo guloso numa grade de 50 m "
                      "(candidatos a cada 150 m), distância em linha reta e moradores uniformes no bairro. Não considera ladeiras, "
                      "escadarias, imóveis disponíveis, segurança nem credenciamento.", "sim"), unsafe_allow_html=True)
    comb = sim["Dois agrupamentos (pontos por agrupamento)"]["cobertura_por_qtd_pontos"]
    t10 = sim["10 bairros prioritários (IPV)"]["cobertura_por_qtd_pontos"]
    st.markdown(kpis([
        kpi(f"{br(comb['0'])}% → {br(comb['3'])}%", "nos dois agrupamentos contíguos, com 3 pontos em cada",
            f"{br(sim['Dois agrupamentos (pontos por agrupamento)']['moradores'], 0)} moradores · com 4 pontos: {br(comb['4'])}%", "sim"),
        kpi(f"{br(t10['0'])}% → {br(t10['7'])}%", "nos 10 bairros prioritários, com 7 pontos",
            f"{br(sim['10 bairros prioritários (IPV)']['moradores'], 0)} moradores", "sim"),
    ]), unsafe_allow_html=True)
    c1, c2 = st.columns([1.1, 1])
    with c1:
        with st.container(border=True):
            st.markdown(ct(f"Cobertura a 500 m conforme os pontos são adicionados"), unsafe_allow_html=True)
            st.plotly_chart(ch.linhas_cenario(sim), use_container_width=True, config=CFG)
    with c2:
        with st.container(border=True):
            st.markdown(ct(f"Posições teóricas: 3 pontos por agrupamento"), unsafe_allow_html=True)
            novos = []
            for k in ("Agrupamento RPA 3", "Agrupamento RPAs 2 e 3"):
                for p in sim[k]["posicoes_teoricas"][:3]:
                    novos.append({"ordem": p["ordem"], "longitude": p["longitude"], "latitude": p["latitude"]})
            nv = gpd.GeoDataFrame(novos, geometry=gpd.points_from_xy([n["longitude"] for n in novos], [n["latitude"] for n in novos]), crs="EPSG:4326")
            area = base[base.bairro.isin(sum([sim[k]["bairros"] for k in ("Agrupamento RPA 3", "Agrupamento RPAs 2 e 3")], []))]
            st.plotly_chart(ch.mapa_cobertura(area, 500, pontos[pontos.bairro_geo.isin(area.bairro)], novos=nv, height=400),
                            use_container_width=True, config=CFG)
    rows = []
    for k in ["Agrupamento RPA 3", "Agrupamento RPAs 2 e 3", "Dois agrupamentos (pontos por agrupamento)"]:
        s = sim[k]
        rows.append([k, s["moradores"]] + [s["cobertura_por_qtd_pontos"][str(n)] for n in (0, 2, 3, 4)])
    t = pd.DataFrame(rows, columns=["Recorte simulado", "Moradores", "Hoje", "Com 2 pontos", "Com 3 pontos", "Com 4 pontos"])
    st.markdown(tabela(t, {"Moradores": 0, "Hoje": 1, "Com 2 pontos": 1, "Com 3 pontos": 1, "Com 4 pontos": 1},
                       {c: "%" for c in ["Hoje", "Com 2 pontos", "Com 3 pontos", "Com 4 pontos"]}, destaque="Com 3 pontos"),
                unsafe_allow_html=True)
    st.markdown(aviso("Agrupamento RPA 3: Brejo da Guabiraba, Córrego do Jenipapo e Nova Descoberta. Agrupamento RPAs 2 e 3: "
                      "Alto Santa Terezinha, Água Fria, Beberibe, Alto José do Pinho e Alto José Bonifácio. No caso combinado, "
                      "o número de pontos vale para cada agrupamento.", "note"), unsafe_allow_html=True)

with abas[5]:
    st.markdown(secao("Modelo dimensional Snowflake", "Data Warehouse"), unsafe_allow_html=True)
    c1, c2 = st.columns([1.05, 1])
    with c1:
        with st.container(border=True):
            st.markdown(ct("4 fatos e 14 dimensões", "Figura 6 da documentação"), unsafe_allow_html=True)
            st.image(str(ROOT / "assets" / "modelo_snowflake.png"), use_container_width=True)
    with c2:
        with st.container(border=True):
            st.markdown(ct("Tabelas no banco", f"{DW_PATH.name} · criado pelo DDL, com PK e FK"), unsafe_allow_html=True)
            t = tabelas_dw.copy()
            t["situação"] = t.linhas.map(lambda n: "carregada" if n else "vazia")
            t.columns = ["Tabela", "Linhas", "Tipo", "Situação"]
            st.markdown(tabela(t, {"Linhas": 0}), unsafe_allow_html=True)
            st.caption("As tabelas vazias são da operação (entregas, resgates, finanças) e recebem carga no piloto.")
    st.markdown(aviso("O painel consulta a visão <code>vw_bairro_indicadores</code>, que junta a Fato_Indicador_Territorial "
                      "com Dim_Bairro → Dim_RPA → Dim_Municipio e Dim_Indicador. Medidas derivadas, como cobertura "
                      "percentual, quintis e IPV, são calculadas no painel a partir dessas linhas."), unsafe_allow_html=True)
    st.markdown(secao("Indicadores da tabela fato", "94 linhas por indicador"), unsafe_allow_html=True)
    t = indicadores_dw[["codigo", "nome", "regra_agregacao", "id_fonte_dado", "data_referencia"]].copy()
    t["data_referencia"] = pd.to_datetime(t.data_referencia).dt.strftime("%d/%m/%Y")
    t.columns = ["Código", "Indicador", "Agregação", "Fonte", "Referência"]
    st.markdown(tabela(t), unsafe_allow_html=True)
    st.markdown(secao("Controle de qualidade", f"{qc['checagens']['status'].capitalize()}"), unsafe_allow_html=True)
    a = qc["auditoria"]
    st.markdown(kpis([
        kpi(f"{a['registros_dentro_recife_todos_residuos']} de {a['total_pontos_arquivo']}", "registros localizados dentro de Recife",
            f"{a['registros_fora_recife']} fora dos limites"),
        kpi(f"{a['bairros_ibge_com_renda']} de {a['bairros_geograficos']}", "bairros conciliados entre malha e Censo", "Sem bairro órfão"),
        kpi(br(a["fato_indicador_territorial_linhas"], 0), "linhas na Fato_Indicador_Territorial", "94 bairros × 10 indicadores"),
        kpi(str(a["geometrias_zeis_reparadas_make_valid"]), "geometrias de ZEIS corrigidas", "make_valid, sem perda de área"),
    ]), unsafe_allow_html=True)
    st.markdown(secao("Fontes", "Dim_Fonte_Dado"), unsafe_allow_html=True)
    f = fontes_dw[["instituicao", "conjunto", "licenca", "data_referencia"]].copy()
    f["data_referencia"] = pd.to_datetime(f.data_referencia).dt.strftime("%d/%m/%Y")
    f.columns = ["Instituição", "Conjunto", "Licença", "Referência"]
    st.markdown(tabela(f), unsafe_allow_html=True)
    st.markdown(" · ".join(f"[{r.instituicao}: {r.conjunto.split(':')[0]}]({r.url})" for r in fontes_dw.itertuples() if r.url))
    st.markdown(aviso("Premissas: distância em linha reta (EPSG:31985) e moradores distribuídos de forma uniforme em cada bairro. "
                      "Ponto na base pública não significa ponto ativo nem credenciado. Os microdados do CadÚnico não estão "
                      "no repositório.", "note"), unsafe_allow_html=True)
    d1, d2, d3 = st.columns(3)
    d1.download_button("Baixar modelo (CSV + SQL)", pacote_modelo(), file_name="ecofluxo_modelo_snowflake.zip",
                       mime="application/zip", use_container_width=True)
    d2.download_button("Baixar banco SQLite", DW_PATH.read_bytes(), file_name=DW_PATH.name,
                       mime="application/octet-stream", use_container_width=True)
    d3.download_button("Baixar manifesto SHA-256", (OUTPUTS / "manifesto_fontes_sha256.csv").read_bytes(),
                       file_name="manifesto_fontes_sha256.csv", mime="text/csv", use_container_width=True)

st.markdown(rodape(), unsafe_allow_html=True)
