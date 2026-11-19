from src.scenario import export

if __name__ == "__main__":
    for recorte, s in export().items():
        print(recorte, s["moradores"], {k: round(v, 1) for k, v in s["cobertura_por_qtd_pontos"].items()})
