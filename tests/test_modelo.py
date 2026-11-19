"""Integridade do Data Warehouse e da camada semântica."""
import json
import math
import re
import sqlite3

import pandas as pd
import pytest

from src import modelo
from src.config import DW_PATH, OUTPUTS, PROCESSED, ROOT


@pytest.fixture(scope="module")
def con():
    with sqlite3.connect(DW_PATH) as c:
        yield c


def test_ddl_cria_4_fatos_e_14_dimensoes(con):
    nomes = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    assert sum(n.startswith("Fato_") for n in nomes) == 4
    assert sum(n.startswith("Dim_") for n in nomes) == 14


def test_chaves_estrangeiras_validas(con):
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_fato_territorial_tem_940_linhas_e_grao_unico(con):
    fato = pd.read_sql_query("SELECT * FROM Fato_Indicador_Territorial", con)
    assert len(fato) == 940
    assert fato.id_fato_indicador.is_unique
    assert not fato.duplicated(["id_bairro", "id_indicador", "id_tempo_referencia", "versao_carga"]).any()
    assert fato.id_bairro.nunique() == 94 and fato.id_indicador.nunique() == 10


def test_colunas_seguem_a_figura_6(con):
    esperado = {
        "Fato_Indicador_Territorial": ["id_fato_indicador", "id_bairro", "id_indicador", "id_tempo_referencia",
                                       "versao_carga", "valor"],
        "Dim_Tempo": ["id_tempo", "data", "dia", "mes", "trimestre", "ano"],
        "Dim_Bairro": ["id_bairro", "id_rpa", "cod_bairro_ibge", "nome"],
        "Dim_Municipio": ["id_municipio", "codigo_ibge", "nome", "uf"],
        "Dim_Fonte_Dado": ["id_fonte_dado", "instituicao", "conjunto", "url", "licenca", "data_referencia",
                           "data_extracao"],
        "Dim_Local": ["id_local", "id_bairro", "nome", "tipo_local", "origem_cadastro", "aceita_reciclavel",
                      "latitude", "longitude"],
    }
    for tabela, colunas in esperado.items():
        assert [r[1] for r in con.execute(f"PRAGMA table_info({tabela})")] == colunas


def test_dimensoes_completas(con):
    tempo = pd.read_sql_query("SELECT * FROM Dim_Tempo", con)
    assert tempo.notna().all().all() and set(tempo.ano) == {2022, 2026}
    fontes = pd.read_sql_query("SELECT * FROM Dim_Fonte_Dado", con)
    assert fontes[["url", "licenca", "data_referencia", "data_extracao"]].notna().all().all()
    usadas = set(pd.read_sql_query("SELECT id_fonte_dado FROM Dim_Indicador", con).id_fonte_dado)
    assert usadas <= set(fontes.id_fonte_dado)


def test_dim_local_bate_com_a_fato(con):
    v = pd.read_sql_query("SELECT id_bairro, pontos_totais, pontos_reciclaveis FROM vw_bairro_indicadores", con)
    locais = pd.read_sql_query("""SELECT id_bairro, COUNT(*) AS todos, SUM(aceita_reciclavel) AS reciclaveis
                                  FROM Dim_Local GROUP BY id_bairro""", con)
    m = v.merge(locais, on="id_bairro", how="left").fillna(0)
    assert (m.pontos_totais == m.todos).all() and (m.pontos_reciclaveis == m.reciclaveis).all()


def test_camada_semantica_reproduz_o_pipeline():
    pipeline = json.loads((OUTPUTS / "indicadores.json").read_text(encoding="utf-8"))
    for chave, valor in modelo.indicadores(modelo.bairros()).items():
        if isinstance(valor, float):
            assert math.isclose(valor, pipeline[chave], rel_tol=1e-12), chave
        else:
            assert valor == pipeline[chave], chave


def test_consultas_analiticas_executam(con):
    sql = (ROOT / "sql" / "consultas_analiticas.sql").read_text(encoding="utf-8")
    consultas = [c.strip() for c in re.split(r";\s*\n", sql) if "SELECT" in c]
    assert len(consultas) == 5
    for consulta in consultas:
        assert len(con.execute(consulta).fetchall()) > 0
    rpa = pd.read_sql_query(consultas[0], con)
    assert rpa.moradores.sum() == 1479478 and rpa.pontos_reciclaveis.sum() == 144


def test_csvs_do_modelo_estao_completos():
    for tabela in ["Dim_Municipio", "Dim_RPA", "Dim_Bairro", "Dim_Local", "Dim_Tempo", "Dim_Fonte_Dado",
                   "Dim_Indicador", "Fato_Indicador_Territorial"]:
        assert (PROCESSED / f"{tabela}.csv").exists()
