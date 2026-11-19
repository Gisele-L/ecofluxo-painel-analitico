"""Gráficos Plotly do painel. O mapa usa os polígonos projetados, sem mapa-base, e funciona offline."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .config import CORES as C, RAMPA, CLASSES_COBERTURA, CRS_METRIC

FONTE = "Inter, 'Segoe UI', Arial, sans-serif"


def br(v: float, d: int = 1) -> str:
    return f"{v:,.{d}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def layout(fig: go.Figure, height: int = 360, margin: dict | None = None, legend: bool = False) -> go.Figure:
    fig.update_layout(
        paper_bgcolor=C["branco"], plot_bgcolor=C["branco"], separators=",.",
        font=dict(family=FONTE, color=C["mata"], size=13),
        height=height, margin=margin or dict(l=12, r=12, t=16, b=28), showlegend=legend,
        hoverlabel=dict(bgcolor=C["branco"], bordercolor=C["linha"], font=dict(family=FONTE, color=C["mata"], size=12)),
        legend=dict(orientation="h", y=1.08, x=0, font=dict(size=12, color=C["musgo"]), bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(showgrid=False, showline=True, linecolor=C["linha"], zeroline=False,
                     tickfont=dict(color=C["musgo"]), title_font=dict(color=C["musgo"], size=12))
    fig.update_yaxes(showgrid=True, gridcolor="#EEF2EB", zeroline=False,
                     tickfont=dict(color=C["musgo"]), title_font=dict(color=C["musgo"], size=12))
    return fig


def classe_cobertura(pct: float) -> int:
    if pct <= 1e-9:
        return 0
    for i, (lo, hi, _) in enumerate(CLASSES_COBERTURA[1:], start=1):
        if pct <= hi:
            return i
    return len(CLASSES_COBERTURA) - 1


def _rings(geom):
    polys = [geom] if geom.geom_type == "Polygon" else list(getattr(geom, "geoms", []))
    xs, ys = [], []
    for p in polys:
        if p.geom_type != "Polygon":
            continue
        x, y = p.exterior.coords.xy
        xs += list(x) + [None]
        ys += list(y) + [None]
    return xs, ys


def mapa_cobertura(bairros: gpd.GeoDataFrame, radius: int = 500, pontos: gpd.GeoDataFrame | None = None,
                   destaque: list[str] | None = None, novos: gpd.GeoDataFrame | None = None,
                   height: int = 560, colorir: bool = True) -> go.Figure:
    b = bairros.to_crs(CRS_METRIC).copy()
    b["geometry"] = b.geometry.simplify(12, preserve_topology=True)
    col = f"cobertura_area_{radius}m_pct"
    b["classe"] = b[col].map(classe_cobertura)
    fig = go.Figure()
    shown = set()
    for _, r in b.sort_values("classe").iterrows():
        xs, ys = _rings(r.geometry)
        k = int(r.classe)
        cor = RAMPA[k] if colorir else C["orvalho"]
        n = int((b.classe == k).sum())
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines", fill="toself", fillcolor=cor, line=dict(color=C["branco"], width=0.8),
            hoveron="fills", name=f"{CLASSES_COBERTURA[k][2]} · {n} bairros", legendgroup=str(k),
            showlegend=colorir and k not in shown,
            text=(f"<b>{r.bairro}</b><br>RPA {int(r.rpa)}<br>Área a até {radius} m: {br(r[col])}%"
                  f"<br>Pontos no bairro: {int(r.registros_no_bairro)}"
                  f"<br>Moradores (Censo 2022): {br(r.moradores_domicilios_responsaveis, 0)}"),
            hoverinfo="text"))
        shown.add(k)
    if destaque:
        for _, r in b[b.bairro.isin(destaque)].iterrows():
            xs, ys = _rings(r.geometry)
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=C["mata"], width=2.2),
                                     fill="toself" if not colorir else None,
                                     fillcolor=C["broto"] if not colorir else None,
                                     hoverinfo="text", hoveron="fills" if not colorir else "points",
                                     text=f"<b>{r.bairro}</b><br>Posição no IPV: {int(r.posicao_ipv)}<br>IPV: {br(r.ipv)}",
                                     showlegend=False))
    if pontos is not None and len(pontos):
        p = pontos.to_crs(CRS_METRIC)
        fig.add_trace(go.Scatter(x=p.geometry.x, y=p.geometry.y, mode="markers", name="Ponto de recicláveis (base pública)",
                                 marker=dict(size=6, color=C["mata"], line=dict(color=C["branco"], width=1)),
                                 hoverinfo="skip", showlegend=True))
    if novos is not None and len(novos):
        q = novos.to_crs(CRS_METRIC)
        fig.add_trace(go.Scatter(x=q.geometry.x, y=q.geometry.y, mode="markers+text", name="Ponto simulado",
                                 text=[str(i) for i in q["ordem"]], textposition="middle center",
                                 textfont=dict(color=C["mata"], size=10, family=FONTE),
                                 marker=dict(size=17, color=C["broto"], line=dict(color=C["mata"], width=2)),
                                 hoverinfo="skip", showlegend=True))
    fig = layout(fig, height, dict(l=0, r=0, t=6, b=0), legend=True)
    fig.update_layout(legend=dict(orientation="v", x=0.74, y=0.98, yanchor="top", itemclick=False, itemdoubleclick=False))
    fig.update_xaxes(visible=False, scaleanchor="y", scaleratio=1)
    fig.update_yaxes(visible=False)
    return fig


def barras_rpa(rpa: pd.DataFrame, radius: int = 500) -> go.Figure:
    col = f"cobertura_populacional_{radius}m_pct"
    media = 100 * rpa[f"moradores_cobertos_{radius}m"].sum() / rpa.moradores.sum()
    r = rpa.sort_values("rpa")
    acima = r[col] >= media
    fig = go.Figure(go.Bar(
        x=[f"RPA {int(v)}" for v in r.rpa], y=r[col], marker_color=np.where(acima, C["mata"], C["salvia"]),
        marker_line_width=0, text=[f"{br(v)}%" for v in r[col]], textposition="inside", insidetextanchor="end", textangle=0,
        textfont=dict(color=[C["broto"] if a else C["mata"] for a in acima], size=12), constraintext="none",
        customdata=np.c_[r.moradores, r.pontos],
        hovertemplate="%{x}<br>Moradores a até " + str(radius) + " m: %{y:.1f}%<br>Moradores: %{customdata[0]:,.0f}"
                      "<br>Pontos: %{customdata[1]}<extra></extra>"))
    fig.add_hline(y=media, line_color=C["terra"], line_dash="dot", line_width=1.5, layer="below")
    fig.add_annotation(x=0, xref="paper", y=1.07, yref="paper", showarrow=False, xanchor="left",
                       text=f"<span style='color:{C['terra']}'>┄</span> Média do recorte: <b>{br(media)}%</b>",
                       font=dict(size=12, color=C["musgo"]))
    fig.update_yaxes(range=[0, 108], ticksuffix="%")
    fig.update_traces(width=0.8)
    return layout(fig, 380, dict(l=10, r=10, t=40, b=24))


def funil_pontos(total: int, recife: int, reciclaveis: int) -> go.Figure:
    labels = ["Registros na base municipal", "Dentro dos limites de Recife", "Aceitam recicláveis secos"]
    vals = [total, recife, reciclaveis]
    fig = go.Figure(go.Bar(y=labels[::-1], x=vals[::-1], orientation="h",
                           marker_color=[C["mata"], C["salvia"], "#BCD6B8"], text=[br(v, 0) for v in vals[::-1]],
                           textposition="outside", cliponaxis=False, textfont=dict(color=C["mata"], size=13),
                           hovertemplate="%{y}: %{x}<extra></extra>"))
    fig.update_xaxes(visible=False, range=[0, max(vals) * 1.18])
    fig.update_yaxes(showgrid=False)
    fig.update_traces(width=0.6)
    return layout(fig, 200, dict(l=8, r=20, t=6, b=6))


def quintis(q: pd.DataFrame) -> go.Figure:
    d = q.sort_values("quintil_renda")
    fig = go.Figure()
    for col, nome, cor in [("cobertura_populacional_500m_pct", "Até 500 m", C["mata"]),
                           ("cobertura_populacional_1000m_pct", "Até 1 km", C["salvia"])]:
        fig.add_trace(go.Bar(name=nome, x=d.quintil_renda, y=d[col], marker_color=cor, marker_line_width=0,
                             text=[f"{br(v)}%" for v in d[col]], textposition="outside", cliponaxis=False,
                             textfont=dict(size=12, color=C["mata"]), constraintext="none",
                             hovertemplate=nome + " · %{x}: %{y:.1f}%<extra></extra>"))
    fig.update_layout(barmode="group", bargap=0.28, bargroupgap=0.08)
    fig.update_yaxes(range=[0, 108], ticksuffix="%")
    fig.update_xaxes(ticktext=["Q1<br>menor renda", "Q2", "Q3", "Q4", "Q5<br>maior renda"],
                     tickvals=["Q1", "Q2", "Q3", "Q4", "Q5"])
    return layout(fig, 380, dict(l=10, r=10, t=36, b=40), legend=True)


def dispersao_renda(b: pd.DataFrame, top10: list[str]) -> go.Figure:
    d = b.dropna(subset=["renda_media_responsavel", "cobertura_area_500m_pct"]).copy()
    d["top"] = d.bairro.isin(top10)
    size = 8 + 30 * np.sqrt(d.moradores_domicilios_responsaveis / d.moradores_domicilios_responsaveis.max())
    fig = go.Figure()
    for flag, nome, cor, borda in [(False, "Demais bairros", C["salvia"], C["branco"]),
                                   (True, "10 prioritários (IPV)", C["broto"], C["mata"])]:
        s = d[d.top == flag]
        fig.add_trace(go.Scatter(
            x=s.renda_media_responsavel, y=s.cobertura_area_500m_pct, mode="markers", name=nome,
            marker=dict(size=size[s.index], color=cor, opacity=0.9 if flag else 0.75, line=dict(color=borda, width=1.4 if flag else 1)),
            text=s.bairro, customdata=s.moradores_domicilios_responsaveis,
            hovertemplate="<b>%{text}</b><br>Rendimento médio: R$ %{x:,.0f}<br>Área a até 500 m: %{y:.1f}%"
                          "<br>Moradores: %{customdata:,.0f}<extra></extra>"))
    fig.update_xaxes(type="log", title="Rendimento médio do responsável (R$, escala logarítmica)",
                     tickvals=[1000, 1500, 2000, 3000, 5000, 7500, 10000, 15000],
                     ticktext=["1 mil", "1,5 mil", "2 mil", "3 mil", "5 mil", "7,5 mil", "10 mil", "15 mil"])
    fig.update_yaxes(range=[-4, 106], ticksuffix="%", title="Área do bairro a até 500 m")
    return layout(fig, 400, dict(l=10, r=10, t=36, b=50), legend=True)


def barras_ipv(top: pd.DataFrame) -> go.Figure:
    r = top.sort_values("ipv")
    fig = go.Figure(go.Bar(y=r.bairro, x=r.ipv, orientation="h", marker_color=C["mata"], marker_line_width=0,
                           text=[br(v) for v in r.ipv], textposition="outside", cliponaxis=False,
                           textfont=dict(color=C["mata"], size=13),
                           hovertemplate="%{y}: IPV %{x:.1f}<extra></extra>"))
    fig.update_xaxes(range=[0, 112], title="IPV (0 a 100)", showgrid=True, gridcolor="#EEF2EB")
    fig.update_yaxes(showgrid=False)
    fig.update_traces(width=0.62)
    return layout(fig, 420, dict(l=8, r=24, t=8, b=44))


def linhas_cenario(s: dict) -> go.Figure:
    estilos = {
        "Dois agrupamentos (pontos por agrupamento)": (C["mata"], 4, "solid", "Dois agrupamentos (mesmo nº de pontos em cada)"),
        "10 bairros prioritários (IPV)": (C["folha"], 3, "solid", "10 bairros prioritários"),
        "Agrupamento RPA 3": (C["salvia"], 2, "dash", "Agrupamento RPA 3"),
        "Agrupamento RPAs 2 e 3": ("#4B8768", 2, "dot", "Agrupamento RPAs 2 e 3"),
    }
    fig = go.Figure()
    for nome, (cor, w, dash, rot) in estilos.items():
        seq = s[nome]["cobertura_por_qtd_pontos"]
        fig.add_trace(go.Scatter(x=[int(k) for k in seq], y=list(seq.values()), mode="lines+markers", name=rot,
                                 line=dict(color=cor, width=w, dash=dash), marker=dict(size=8 if w > 2 else 6, color=cor),
                                 hovertemplate=rot + "<br>%{x} ponto(s) por recorte: %{y:.1f}%<extra></extra>"))
    fig.update_xaxes(title="Novos pontos simulados (por agrupamento, no caso combinado)", dtick=1)
    fig.update_yaxes(title="Moradores a até 500 m", range=[0, 102], ticksuffix="%")
    return layout(fig, 400, dict(l=10, r=10, t=56, b=48), legend=True)
