"""Cria o Data Warehouse em SQLite a partir do DDL e carrega as tabelas do modelo."""
from __future__ import annotations

import sqlite3

import pandas as pd

from .config import DW_PATH, PROCESSED, SQL

ORDEM_CARGA = ["Dim_Municipio", "Dim_RPA", "Dim_Bairro", "Dim_Local", "Dim_Tempo", "Dim_Fonte_Dado",
               "Dim_Indicador", "Fato_Indicador_Territorial"]
TIPOS_TEXTO = {"cod_bairro_ibge": str, "codigo_ibge": str, "id_fonte_dado": str}


def construir(caminho=DW_PATH) -> dict[str, int]:
    caminho.unlink(missing_ok=True)
    with sqlite3.connect(caminho) as con:
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript((SQL / "modelo_snowflake.sql").read_text(encoding="utf-8"))
        for tabela in ORDEM_CARGA:
            df = pd.read_csv(PROCESSED / f"{tabela}.csv", dtype=TIPOS_TEXTO, keep_default_na=False, na_values=[""])
            df.to_sql(tabela, con, if_exists="append", index=False)
        violacoes = con.execute("PRAGMA foreign_key_check").fetchall()
        if violacoes:
            raise AssertionError(f"Chaves estrangeiras inválidas: {violacoes[:5]}")
        tabelas = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        contagem = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tabelas}
    return contagem
