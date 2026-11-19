"""Agrega localmente a base anonimizada do CadÚnico 2023 e exporta só indicadores municipais.

Uso: python -m scripts.aggregate_cadunico_local "C:/dados_restritos/cadastro-unico-2023.csv"
"""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from src.config import PROCESSED

COLUNAS = ["cod_familiar", "vlr_renda_total", "vlr_renda_media", "d.val_desp_alimentacao_fam",
           "d.cod_destino_lixo_domic_fam", "d.marc_pbf", "dat_atualizacao",
           "p.cod_sabe_ler_escrever_memb", "p.dta_nasc_pessoa"]
REFERENCIA = pd.Timestamp("2023-09-16")


def aggregate(filepath: str) -> dict:
    data = pd.read_csv(filepath, sep=";", usecols=COLUNAS, low_memory=False)
    families = data.drop_duplicates("cod_familiar")
    age = (REFERENCIA - pd.to_datetime(data["p.dta_nasc_pessoa"], dayfirst=True, errors="coerce")).dt.days / 365.2425
    adults = age >= 15
    food = families["d.val_desp_alimentacao_fam"]
    ratio = (food / families["vlr_renda_total"].replace(0, float("nan"))).dropna()
    updates = pd.to_datetime(families.dat_atualizacao, dayfirst=True, errors="coerce")
    lixo = families["d.cod_destino_lixo_domic_fam"]
    result = {
        "referencia": "16/09/2023", "escopo": "Recife", "tipo": "indicadores_municipais_somente",
        "familias": int(len(families)), "pessoas": int(len(data)),
        "renda_per_capita_mediana_brl": float(families.vlr_renda_media.median()),
        "pct_familias_renda_pc_ate_218": float(100 * (families.vlr_renda_media <= 218).mean()),
        "pct_familias_renda_pc_ate_660": float(100 * (families.vlr_renda_media <= 660).mean()),
        "pct_familias_marcacao_pbf": float(100 * (families["d.marc_pbf"] == 1).mean()),
        "gasto_alimentacao_mediana_brl": float(food.median()),
        "pct_mediana_gasto_sobre_renda_declarada": float(100 * ratio.median()),
        "pct_gasto_sobre_renda_ge_50_entre_validos": float(100 * (ratio >= .5).mean()),
        "proporcoes_alimentacao_denominador_valido": int(ratio.count()),
        "pct_pessoas_15mais_nao_leem": float(100 * (adults & (data["p.cod_sabe_ler_escrever_memb"] == 2)).sum()
                                             / adults.sum()),
        "pct_pessoas_60mais": float(100 * (age >= 60).mean()),
        "pct_familias_cadastro_atualizado_ate_24m": float(100 * (updates >= pd.Timestamp("2021-09-16")).mean()),
        "pct_familias_coleta_direta": float(100 * (lixo == 1).mean()),
        "pct_familias_coleta_indireta": float(100 * (lixo == 2).mean()),
        "pct_familias_lixo_outros_destinos": float(100 * lixo.isin([3, 4, 5, 6]).mean()),
        "sha256_arquivo_nao_publicado": hashlib.sha256(Path(filepath).read_bytes()).hexdigest(),
        "advertencia": "Dados públicos anonimizados de referência 2023, processados localmente; apenas este agregado é "
                       "exportado. A renda declarada não inclui benefícios sociais. NÃO publicar microdados.",
    }
    PROCESSED.mkdir(parents=True, exist_ok=True)
    (PROCESSED / "cadunico_agregado_municipal_2023.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("arquivo", help="CSV do Cadastro Único 2023, mantido fora do repositório")
    resultado = aggregate(parser.parse_args().arquivo)
    print(f"Indicadores municipais exportados: {resultado['familias']} famílias, {resultado['pessoas']} pessoas.")
