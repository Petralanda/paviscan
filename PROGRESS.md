# Progresso

Atualize ao fim de cada sessão. Curto e factual.

## Estado

| Marco | Status | Observação |
|---|---|---|
| M1 Ingestão e pista | concluído (tag m1) | verify m1 OK, verificador APROVADO |
| M2 Detecção e geometria | concluído (tag m2) | verify m2 OK, verificador APROVADO na 3ª volta |
| M3 Indicadores, exportações e imagem real | concluído (tag m3) | verify m3 OK, verificador APROVADO; 1ª imagem real processada |
| M4 Dashboard | a fazer | |
| M5 Fechamento | a fazer | |

## Feito
- Scaffold, harness, gerador sintético e testes golden.
- 11/11 M1: `ingestao.py` (SRC, GSD, UTM SIRGAS no Brasil via WarpedVRT, janelas com sobreposição), `pista.py` (polígono, janela, máscara), `pipeline.processar` em esqueleto gravando `pista_recorte.tif`, CLI `paviscan run`/`painel`. 10 testes unitários. Robustez do verificador: área do recorte 420 m² em seeds 11/42, gsd 0,01 a 0,05, orto em 4326.
- 11/11 M2: `deteccao/` (Protocol, `classico.py`, fábrica `criar`), `geometria.py` (vetorização, medidas, severidade, deduplicação), pipeline grava `defeitos.geojson`. Sintético: recall 100%, 0 FP, erro de área mediano 3 a 4% nas seeds 7/11/23/42, gsd 0,005 a 0,05; pista limpa 0 detecções. 168 cenas de buraco na fronteira de tile sem erro. 39 testes unitários.
- 11/11 M3: `pista.segmentos` (faixas ao longo do eixo maior, cobrem a pista), `indicadores.py`, `exportar.py` (GeoJSON, GPKG com 2 camadas, XLSX com 3 abas, resumo.json, previa.png RGBA lida com out_shape), ingestão reprojeta 3857/pés, estica uint16/float e usa alfa no VRT. 51 testes unitários, 9 golden. Verificador: pista inclinada, comprimento não múltiplo de 20 m e entrada 3857 fecham; imagem real com 225 MB de pico.

## Imagem real (M3)
- Ortofoto: `../images/6a7f671c77ca9598cc9fe780.tif` (fora do repo). Manaus, EPSG:31980, GSD 2,99 cm, 10647 x 15942 px, JPEG/YCbCr, sem nodata: fora da área imageada é **branco** (255), não máscara.
- Pista de teste: `dados/real/pista_avenida.geojson` (ignorado pelo git). Retângulo EPSG:31980 x 828641,469 a 828646,769, y 9667482,038 a 9667602,038 (avenida no leste da imagem, 5,3 x 120 m, 6 segmentos). Segmento 0 = sul.
- Resultado com a config atual: 39 detecções, 8,96 m², 1,41% da pista, 4 s.
- O que o detector errou (conferido em resolução cheia, `runs/real/deteccoes_avenida.png`):
  - Veículos: o caminhão sozinho gera 12 detecções (seg. 2); para-brisas de carros e a moto geram outras ~7, várias com confiança ≥ 0,8. É a maior fonte de FP.
  - Borda da pista: faixa escura de sarjeta/mato e borda desgastada geram fileiras de detecções pequenas (0,05 a 0,4 m²) nos seg. 4 e 5. Parte é dano real de borda, mas não é panela.
  - Sombra de poste (seg. 4, ids 9 a 11) junto a uma mancha escura que pode ser panela real.
  - Não detectado: a faixa longa de asfalto quebrado na borda oeste do seg. 2 (contraste baixo e muito alongada, cai no filtro de alongamento).
  - Trecho com poucos buracos de verdade: serve para medir FP, não recall. Para a demo convém achar trecho com panelas visíveis.
- Para o M5: polígono mais justo (recuar da sarjeta); filtrar veículo (objeto claro/saturado grande colado à detecção); avaliar `area_min_m2` maior em imagem real.

## Decisões
- 11/11: tiles com `sobreposicao_m` (metros); cada buraco fica com o tile cujo miolo contém o centroide e, no fim, polígonos sobrepostos ficam só com o maior (`geometria.deduplicar`). Unir a máscara do trecho inteiro foi descartado por memória em ortofoto grande.
- 11/11: ambiente em `.venv` com Python 3.12; `core.fileMode=false` no repo (Windows).
- 10/11: escopo reduzido a um retrato de uma imagem. Orçamento e série temporal saíram.
- 10/11: detector por anomalia escura local com limiar robusto (mediana + k x MAD), não Otsu nem watershed puro. YOLO do mestrado entra depois pela interface `Detector`.
- 10/11: saída visual é um dashboard Streamlit com filtros de área, severidade, confiança e segmento.

## Pendências e dúvidas para o usuário
- (M4) previa.png limita só a largura; limitar o maior lado (textura WebGL). defeitos.geojson vazio perde as colunas: `painel.dados.carregar` tem que repor.
- (menor) resto de segmento muito curto (ex.: 0,5 m) deixa pct_afetada instável; avaliar juntar ao anterior.
- (menor) area_pista_m2 não desconta área sem imagem (branco) se o polígono sair da área imageada.
- O repositório está no OneDrive: um arquivo foi regravado truncado durante um commit (2e19b7b fica quebrado no histórico; f7b1913 corrige). Sugestão: pausar a sincronização ou mover o repo para fora do OneDrive.
- (menor) `deduplicar` usa interseção > 0; avaliar tolerância relativa se aparecer caso real.
- Ortofoto real (GSD de 5 cm/px ou melhor) e polígono da pista.
- Confirmar as faixas de severidade em `config/params.yaml`.
