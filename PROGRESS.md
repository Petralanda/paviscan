# Progresso

Atualize ao fim de cada sessão. Curto e factual.

## Estado

| Marco | Status | Observação |
|---|---|---|
| M1 Ingestão e pista | a fazer | |
| M2 Detecção e geometria | a fazer | |
| M3 Indicadores, exportações e imagem real | a fazer | |
| M4 Dashboard | a fazer | |
| M5 Fechamento | a fazer | |

## Feito
- Scaffold, harness, gerador sintético e testes golden.

## Decisões
- 10/11: escopo reduzido a um retrato de uma imagem. Orçamento e série temporal saíram.
- 10/11: detector por anomalia escura local com limiar robusto (mediana + k x MAD), não Otsu nem watershed puro. YOLO do mestrado entra depois pela interface `Detector`.
- 10/11: saída visual é um dashboard Streamlit com filtros de área, severidade, confiança e segmento.

## Pendências e dúvidas para o usuário
- Ortofoto real (GSD de 5 cm/px ou melhor) e polígono da pista.
- Confirmar as faixas de severidade em `config/params.yaml`.
