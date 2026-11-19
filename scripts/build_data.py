from src.pipeline import build

if __name__ == "__main__":
    resumo = build()
    print(f"Fato_Indicador_Territorial: {resumo['bairros_total']} bairros x 10 indicadores")
    print(f"Moradores a até 500 m: {resumo['cobertura_populacional_500m_pct']:.1f}%")
    print(f"Bairros sem ponto de recicláveis: {resumo['bairros_sem_ponto']}")
