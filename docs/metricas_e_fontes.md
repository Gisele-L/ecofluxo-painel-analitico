# Métricas e fontes

## Bases

| Fonte | Uso no projeto |
|---|---|
| Prefeitura do Recife: pontos de coleta seletiva | 244 registros; 225 dentro de Recife; 144 aceitam recicláveis secos (`Dim_Local`) |
| Prefeitura do Recife: bairros, RPAs e ZEIS | 94 bairros, 6 RPAs e 92 áreas de ZEIS |
| IBGE, Censo 2022 (data de referência 31/07/2022) | Moradores, domicílios e rendimento do responsável por bairro e por setor |
| MDS, CadINSAN (jan/2024) | Risco de insegurança alimentar grave, valor municipal |
| Cadastro Único 2023, base anonimizada | Só agregados municipais; microdados fora do repositório |

As licenças, os endereços e as datas de cada base ficam na `Dim_Fonte_Dado`.

## Tabela fato

A `Fato_Indicador_Territorial` guarda um valor por bairro, indicador e data de referência: 94 bairros × 10 indicadores
= 940 linhas.

| Código | Origem | Agregação |
|---|---|---|
| MORADORES, DOMICILIOS | Censo 2022 (V06002, V06001) | soma |
| RENDA_MEDIA_RESP | Censo 2022 (V06004) | média ponderada por domicílios |
| RENDA_MEDIANA_RESP | Censo 2022 (V06006) | não aditiva |
| AREA_KM2, AREA_ZEIS_KM2 | malha de bairros e ZEIS | soma |
| PONTOS_TOTAIS, PONTOS_RECICLAVEIS | pontos de coleta localizados no bairro | soma |
| MORADORES_COBERTOS_500M, MORADORES_COBERTOS_1000M | estimativa do projeto | soma |

## Medidas calculadas no painel

- **Moradores próximos de um ponto:** moradores do bairro × fração da área do bairro a até 500 m (ou 1 km), em linha reta,
  de algum ponto de recicláveis. Supõe moradores distribuídos de forma uniforme no bairro. O percentual de um recorte é
  Σ moradores próximos ÷ Σ moradores, e não a média dos percentuais.
- **Pontos por 10 mil moradores:** Σ pontos de recicláveis ÷ Σ moradores × 10.000.
- **Quintis de renda:** bairros ordenados pelo rendimento médio do responsável, com cerca de 20% dos moradores em cada
  grupo (21, 20, 14, 17 e 22 bairros). Rendimento do responsável não é renda familiar.
- **IPV (Índice de Prioridade para Validação):** média de três componentes de 0 a 1, multiplicada por 100: parte do
  bairro sem ponto a até 500 m; rendimento médio invertido em escala logarítmica; parte da área em ZEIS. Calculado para
  os 72 bairros com 5 mil moradores ou mais. Apoia a escolha de onde validar o piloto; não mede fome.
- **Cobertura da área de ZEIS (24,2%):** calculada sobre a área total das 92 ZEIS, que inclui 0,63 km² fora dos
  polígonos de bairro. Por isso vem do cálculo geométrico municipal (`outputs/indicadores.json`), e não da soma por bairro.

## Simulação

Grade de células de 50 m; candidatos a novo ponto a cada 150 m; algoritmo guloso que escolhe, a cada passo, o ponto que
mais aumenta os moradores a até 500 m. É um cenário: não considera vias, ladeiras, imóveis disponíveis, segurança nem
credenciamento. A cobertura dos 10 bairros prioritários (6,6%) é medida nessa mesma grade; pela interseção exata dos
polígonos, o valor é 6,70%.

## Limites

- Ponto na base pública não significa ponto ativo nem credenciado.
- CadINSAN e CadÚnico existem só no nível municipal; não há valores por bairro.
- Não há dados de EcoTickets, entregas, resgates ou finanças: esses fatos ficam vazios até o piloto.
