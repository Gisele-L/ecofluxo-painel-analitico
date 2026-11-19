from src.config import DW_PATH
from src.dw import construir

if __name__ == "__main__":
    contagem = construir()
    print(f"Data Warehouse criado em {DW_PATH.name}: {len(contagem)} tabelas")
    for tabela, linhas in contagem.items():
        if linhas:
            print(f"  {tabela}: {linhas} linhas")
