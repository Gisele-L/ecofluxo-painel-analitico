"""Leitura e validação das bases públicas em data/raw."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from zipfile import ZipFile

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.validation import make_valid

from .config import RAW, CENSO_CITY_PREFIX

AJUSTES_NOME = {"cohabiburadecima": "cohab", "sitiodospintos": "sitiodospintossaobras"}


def locate(pattern: str) -> Path:
    found = sorted(RAW.glob(pattern))
    if len(found) != 1:
        raise FileNotFoundError(f"Esperado 1 arquivo para {pattern}: encontrados {len(found)} em {RAW}")
    return found[0]


def key(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text).casefold())
    return re.sub("[^a-z0-9]", "", "".join(c for c in text if not unicodedata.combining(c)))


def to_numeric(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip()
    has_comma = s.str.contains(",", regex=False)
    s.loc[has_comma] = s.loc[has_comma].str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def load_zip_csv(zip_path: Path, **kwargs) -> pd.DataFrame:
    with ZipFile(zip_path) as archive:
        files = [f for f in archive.namelist() if f.lower().endswith(".csv")]
        if len(files) != 1:
            raise ValueError(f"ZIP sem exatamente um CSV: {zip_path}")
        with archive.open(files[0]) as handle:
            return pd.read_csv(handle, sep=";", encoding="latin1", dtype=str, **kwargs)


def is_compatible_residue(value: str) -> bool:
    t = key(value)
    return any(token in t for token in ("reciclav", "plastico", "pastico", "papel", "vidro", "metal", "isopor"))


def tipo_local(value) -> str:
    if pd.isna(value):
        return "Não informado"
    t = key(value)
    for prefixo, rotulo in (("ecoestacao", "Ecoestação"), ("ecoponto", "Ecoponto"), ("pev", "PEV"),
                            ("cooperativa", "Cooperativa")):
        if t.startswith(prefixo):
            return rotulo
    return "Outro"


def nome_local(row: pd.Series) -> str:
    partes = [str(row[c]).strip() for c in ("endereco", "complemento") if pd.notna(row[c]) and str(row[c]).strip()]
    return ", ".join(partes) or "Endereço não informado"


def read_points() -> gpd.GeoDataFrame:
    raw = pd.read_csv(locate("*pontos-de-coleta.csv"), sep=";", encoding="utf-8-sig")
    dictionary = json.loads(locate("*dicionario-de-dados-pontos-de-coleta.json").read_text(encoding="utf-8"))
    required = {"tiporesiduo", "bairro", "latitude", "longitude"}
    if not required.issubset({f["codigo"] for f in dictionary["metadados"]["campos"]}):
        raise ValueError("Campos obrigatórios ausentes do dicionário de coleta.")
    if not required.issubset(raw.columns):
        raise ValueError("CSV de coleta sem os campos " + str(required - set(raw.columns)))
    raw["registro_id"] = np.arange(1, len(raw) + 1)
    raw["latitude"] = pd.to_numeric(raw["latitude"], errors="coerce")
    raw["longitude"] = pd.to_numeric(raw["longitude"], errors="coerce")
    raw["coord_valida"] = raw["latitude"].between(-90, 90) & raw["longitude"].between(-180, 180)
    raw["compativel_reciclagem"] = raw["tiporesiduo"].map(is_compatible_residue)
    raw["tipo_local"] = raw["observacao"].map(tipo_local)
    raw["nome_local"] = raw.apply(nome_local, axis=1)
    return gpd.GeoDataFrame(raw, geometry=gpd.points_from_xy(raw["longitude"], raw["latitude"]), crs="EPSG:4326")


def read_census_neighborhoods() -> pd.DataFrame:
    df = load_zip_csv(locate("Agregados_por_bairros*renda*.zip"))
    df = df[df["CD_BAIRRO"].str.startswith(CENSO_CITY_PREFIX, na=False)].copy()
    if len(df) != 94:
        raise ValueError(f"Agregados IBGE Recife: esperados 94 bairros, encontrados {len(df)}")
    df["bairro_key"] = df["NM_BAIRRO"].map(key)
    for column in ["V06001", "V06002", "V06004", "V06006"]:
        df[column] = to_numeric(df[column])
    return df.rename(columns={
        "CD_BAIRRO": "codigo_bairro_ibge",
        "NM_BAIRRO": "nome_bairro_ibge",
        "V06001": "responsaveis_domicilios",
        "V06002": "moradores_domicilios_responsaveis",
        "V06004": "renda_media_responsavel",
        "V06006": "renda_mediana_responsavel",
    })[["bairro_key", "codigo_bairro_ibge", "nome_bairro_ibge", "responsaveis_domicilios",
        "moradores_domicilios_responsaveis", "renda_media_responsavel", "renda_mediana_responsavel"]]


def read_cadinsan() -> dict:
    import pymupdf

    pdf = pymupdf.open(locate("relatorio_cadinsan.pdf"))
    regex = re.compile(r"Recife\s+Pernambuco\s+([\d.]+)\s+([\d.]+)\s+([\d,]+)%", flags=re.I)
    for index, page in enumerate(pdf):
        result = regex.search(page.get_text())
        if result:
            cadastradas = int(result.group(1).replace(".", ""))
            em_risco = int(result.group(2).replace(".", ""))
            return {
                "municipio": "Recife", "uf": "PE", "referencia": "jan/2024",
                "familias_cadunico": cadastradas,
                "familias_em_risco_inseguranca_alimentar_grave": em_risco,
                "pct_recalculado": 100 * em_risco / cadastradas,
                "pct_publicado_arredondado": float(result.group(3).replace(",", ".")),
                "pagina_pdf": index + 1,
            }
    raise ValueError("Linha de Recife não encontrada no PDF do CadINSAN.")


def make_neighborhood_base() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame, dict]:
    bairros = gpd.read_file(locate("*bairros-do-recife.geojson")).to_crs("EPSG:4326")
    zeis = gpd.read_file(locate("*zoneamento-plano-diretor-zeis.geojson")).to_crs("EPSG:4326")
    if len(bairros) != 94 or len(zeis) != 92:
        raise ValueError("Número inesperado de feições de bairros ou ZEIS.")
    invalid_bairros = int((~bairros.is_valid).sum())
    invalid_zeis = int((~zeis.is_valid).sum())
    bairros.loc[~bairros.is_valid, "geometry"] = bairros.loc[~bairros.is_valid, "geometry"].map(make_valid)
    zeis.loc[~zeis.is_valid, "geometry"] = zeis.loc[~zeis.is_valid, "geometry"].map(make_valid)
    if not bairros.is_valid.all() or not zeis.is_valid.all():
        raise ValueError("Geometrias inválidas após make_valid.")
    bairros = bairros[["EBAIRRNOMEOF", "CRPAAACODI", "geometry"]].rename(
        columns={"EBAIRRNOMEOF": "bairro", "CRPAAACODI": "rpa"})
    bairros["bairro_key"] = bairros["bairro"].map(key).replace(AJUSTES_NOME)
    bairros["rpa"] = bairros["rpa"].astype(int)
    if bairros["bairro_key"].duplicated().any():
        raise ValueError("Bairros com identificador duplicado.")
    b = bairros.merge(read_census_neighborhoods(), on="bairro_key", how="left", validate="one_to_one")
    if b["codigo_bairro_ibge"].isna().any():
        raise ValueError("Bairros sem conciliação com o IBGE: " + str(b.loc[b.codigo_bairro_ibge.isna(), "bairro"].tolist()))
    aux = pd.read_csv(locate("*bairros-e-rpas-do-recife.csv"), sep=";", encoding="utf-8-sig")
    aux["bairro_key"] = aux["Bairro"].map(key).replace(AJUSTES_NOME)
    joined_aux = b.merge(aux[["bairro_key", "rpa"]].rename(columns={"rpa": "rpa_aux"}), on="bairro_key", how="left")
    disagree = int(((joined_aux["rpa_aux"].notna()) & (joined_aux["rpa"] != joined_aux["rpa_aux"])).sum())
    points = read_points()
    valid = points[points["coord_valida"]].copy()
    assigned = gpd.sjoin(valid, b[["bairro_key", "geometry"]], predicate="within", how="left").set_index("registro_id")
    points["dentro_recife"] = points["registro_id"].map(assigned["bairro_key"].notna()).fillna(False).astype(bool)
    points["bairro_key"] = points["registro_id"].map(assigned["bairro_key"])
    points["bairro_geo"] = points["bairro_key"].map(b.set_index("bairro_key")["bairro"])
    audit = {
        "total_pontos_arquivo": int(len(points)),
        "pontos_coordenadas_validas": int(points["coord_valida"].sum()),
        "registros_dentro_recife_todos_residuos": int(points["dentro_recife"].sum()),
        "registros_fora_recife": int((~points["dentro_recife"]).sum()),
        "registros_compativeis_reciclagem": int(points["compativel_reciclagem"].sum()),
        "registros_compativeis_dentro_recife": int((points["compativel_reciclagem"] & points["dentro_recife"]).sum()),
        "bairros_geograficos": int(len(b)),
        "bairros_ibge_com_renda": int(b["renda_mediana_responsavel"].notna().sum()),
        "feicoes_zeis": int(len(zeis)),
        "geometrias_zeis_reparadas_make_valid": invalid_zeis,
        "geometrias_bairro_reparadas_make_valid": invalid_bairros,
        "rpa_divergencia_aux_vs_geo": disagree,
        "bairros_aux_nao_conciliados": sorted(set(aux["bairro_key"]) - set(b["bairro_key"])),
    }
    return gpd.GeoDataFrame(b, geometry="geometry", crs="EPSG:4326"), points, zeis, audit


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
