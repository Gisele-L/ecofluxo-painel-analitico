"""Componentes visuais do painel e do relatório HTML."""
from __future__ import annotations

import base64
import html
from functools import lru_cache

import pandas as pd

from .config import ROOT, IDENTIFICACAO as ID

ASSETS = ROOT / "assets"


@lru_cache
def fontes_css() -> str:
    faces = [("Inter", 400, "Inter-Regular"), ("Inter", 500, "Inter-Medium"), ("Inter", 600, "Inter-SemiBold"),
             ("Inter Display", 800, "InterDisplay-ExtraBold")]
    out = []
    for fam, w, f in faces:
        data = base64.b64encode((ASSETS / "fonts" / f"{f}.woff2").read_bytes()).decode()
        out.append(f"@font-face{{font-family:'{fam}';font-weight:{w};font-style:normal;font-display:swap;"
                   f"src:url(data:font/woff2;base64,{data}) format('woff2')}}")
    return "\n".join(out)


@lru_cache
def tema_css() -> str:
    return fontes_css() + "\n" + (ASSETS / "theme.css").read_text(encoding="utf-8")


@lru_cache
def logo(nome: str = "logo_negativo.svg", altura: int = 30) -> str:
    svg = (ASSETS / nome).read_text(encoding="utf-8")
    data = base64.b64encode(svg.encode()).decode()
    return f'<img alt="EcoFluxo" src="data:image/svg+xml;base64,{data}" style="height:{altura}px;display:block">'


def br(v: float, d: int = 1) -> str:
    return f"{v:,.{d}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _autoria() -> str:
    rm = f' · {ID["rm"]}' if ID.get("rm") else ""
    return f'<b>{ID["autora"]}</b>{rm}'


def cabecalho(selo: str = "Painel analítico") -> str:
    return (f'<div class="eco-header">{logo()}<span class="eco-pill">{html.escape(selo)}</span>'
            f'<div class="eco-header-right">{_autoria()}<br>{ID["grupo"]} · {ID["turma"]} · '
            f'Global Solution 2026.2</div></div>')


def rodape() -> str:
    return (f'<div class="eco-footer">{logo("logo_positivo.svg", 22)}<div>{_autoria()} · '
            f'{ID["grupo"]} · {ID["turma"]}<br>{ID["evento"]}. '
            'Dados públicos organizados no modelo Snowflake do projeto; simulações sinalizadas.</div></div>')


def kpi(valor: str, rotulo: str, nota: str = "", tom: str = "") -> str:
    return (f'<div class="eco-kpi {tom}"><div class="num">{html.escape(valor)}</div>'
            f'<div class="lab">{html.escape(rotulo)}</div><div class="foot">{html.escape(nota)}</div></div>')


def kpis(cards: list[str]) -> str:
    return f'<div class="eco-kpis" style="grid-template-columns:repeat({len(cards)},minmax(0,1fr))">{"".join(cards)}</div>'


def secao(titulo: str, selo: str = "", tom: str = "") -> str:
    s = f'<span class="eco-tag {tom}">{html.escape(selo)}</span>' if selo else ""
    return f'<div class="eco-section">{html.escape(titulo)}{s}</div>'


def aviso(texto: str, tom: str = "info") -> str:
    return f'<div class="eco-{tom}">{texto}</div>'


def tabela(df: pd.DataFrame, numericas: dict[str, int] | None = None, sufixo: dict[str, str] | None = None,
           destaque: str | None = None) -> str:
    numericas, sufixo = numericas or {}, sufixo or {}
    th = "".join(f'<th class="{"n" if c in numericas else ""}">{html.escape(str(c))}</th>' for c in df.columns)
    rows = []
    for _, r in df.iterrows():
        tds = []
        for c in df.columns:
            v = r[c]
            if c in numericas and pd.notna(v) and not isinstance(v, str):
                txt = br(float(v), numericas[c]) + sufixo.get(c, "")
                cls = "n b" if c == destaque else "n"
            else:
                txt = "–" if (not isinstance(v, str) and pd.isna(v)) else str(v)
                cls = ""
            tds.append(f'<td class="{cls}">{html.escape(txt)}</td>')
        rows.append("<tr>" + "".join(tds) + "</tr>")
    return f'<div class="eco-table"><table><thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def titulo_cartao(titulo: str, sub: str = "") -> str:
    s = f'<div class="eco-cs">{html.escape(sub)}</div>' if sub else ""
    return f'<div class="eco-ct">{html.escape(titulo)}</div>{s}'
