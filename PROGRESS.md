# Progresso

Atualize ao fim de cada sessão. Curto e factual.

## Estado

| Marco | Status | Observação |
|---|---|---|
| M1 Ingestão e pista | concluído (tag m1) | verify m1 OK, verificador APROVADO |
| M2 Detecção e geometria | concluído (tag m2) | verify m2 OK, verificador APROVADO na 3ª volta |
| M3 Indicadores, exportações e imagem real | a fazer | |
| M4 Dashboard | a fazer | |
| M5 Fechamento | a fazer | |

## Feito
- Scaffold, harness, gerador sintético e testes golden.
- 11/11 M1: `ingestao.py` (SRC, GSD, UTM SIRGAS no Brasil via WarpedVRT, janelas com sobreposição), `pista.py` (polígono, janela, máscara), `pipeline.processar` em esqueleto gravando `pista_recorte.tif`, CLI `paviscan run`/`painel`. 10 testes unitários. Robustez do verificador: área do recorte 420 m² em seeds 11/42, gsd 0,01 a 0,05, orto em 4326.
- 11/11 M2: `deteccao/` (Protocol, `classico.py`, fábrica `criar`), `geometria.py` (vetorização, medidas, severidade, deduplicação), pipeline grava `defeitos.geojson`. Sintético: recall 100%, 0 FP, erro de área mediano 3 a 4% nas seeds 7/11/23/42, gsd 0,005 a 0,05; pista limpa 0 detecções. 168 cenas de buraco na fronteira de tile sem erro. 39 testes unitários.

## Decisões
- 11/11: tiles com `sobreposicao_m` (metros); cada buraco fica com o tile cujo miolo contém o centroide e, no fim, polígonos sobrepostos ficam só com o maior (`geometria.deduplicar`). Unir a máscara do trecho inteiro foi descartado por memória em ortofoto grande.
- 11/11: ambiente em `.venv` com Python 3.12; `core.fileMode=false` no repo (Windows).
- 10/11: escopo reduzido a um retrato de uma imagem. Orçamento e série temporal saíram.
- 10/11: detector por anomalia escura local com limiar robusto (mediana + k x MAD), não Otsu nem watershed puro. YOLO do mestrado entra depois pela interface `Detector`.
- 10/11: saída visual é um dashboard Streamlit com filtros de área, severidade, confiança e segmento.

## Pendências e dúvidas para o usuário
- O repositório está no OneDrive: um arquivo foi regravado truncado durante um commit (2e19b7b fica quebrado no histórico; f7b1913 corrige). Sugestão: pausar a sincronização ou mover o repo para fora do OneDrive.
- (menor) `deduplicar` usa interseção > 0; avaliar tolerância relativa se aparecer caso real.
- (M3) Reprojetar também SRC projetado impróprio para medir (EPSG:3857, unidades em pés). Hoje só reprojeta SRC geográfico.
- (M3) Esticamento de contraste para float 0-1 e uint16 de 12 bits; nodata no WarpedVRT.
- Ortofoto real (GSD de 5 cm/px ou melhor) e polígono da pista.
- Confirmar as faixas de severidade em `config/params.yaml`.
