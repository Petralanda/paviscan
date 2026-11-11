# Progresso

Atualize ao fim de cada sessão. Curto e factual.

## Estado

| Marco | Status | Observação |
|---|---|---|
| M1 Ingestão e pista | concluído (tag m1) | verify m1 OK, verificador APROVADO |
| M2 Detecção e geometria | concluído (tag m2) | verify m2 OK, verificador APROVADO na 3ª volta |
| M3 Indicadores, exportações e imagem real | concluído (tag m3) | verify m3 OK, verificador APROVADO; 1ª imagem real processada |
| M4 Dashboard | concluído (tag m4) | verify m4 OK, verificador APROVADO; conferido no Chrome |
| M5 Fechamento | a fazer | |

## Feito
- Scaffold, harness, gerador sintético e testes golden.
- 11/11 M1: `ingestao.py` (SRC, GSD, UTM SIRGAS no Brasil via WarpedVRT, janelas com sobreposição), `pista.py` (polígono, janela, máscara), `pipeline.processar` em esqueleto gravando `pista_recorte.tif`, CLI `paviscan run`/`painel`. 10 testes unitários. Robustez do verificador: área do recorte 420 m² em seeds 11/42, gsd 0,01 a 0,05, orto em 4326.
- 11/11 M2: `deteccao/` (Protocol, `classico.py`, fábrica `criar`), `geometria.py` (vetorização, medidas, severidade, deduplicação), pipeline grava `defeitos.geojson`. Sintético: recall 100%, 0 FP, erro de área mediano 3 a 4% nas seeds 7/11/23/42, gsd 0,005 a 0,05; pista limpa 0 detecções. 168 cenas de buraco na fronteira de tile sem erro. 39 testes unitários.
- 11/11 M3: `pista.segmentos` (faixas ao longo do eixo maior, cobrem a pista), `indicadores.py`, `exportar.py` (GeoJSON, GPKG com 2 camadas, XLSX com 3 abas, resumo.json, previa.png RGBA lida com out_shape), ingestão reprojeta 3857/pés, estica uint16/float e usa alfa no VRT. 51 testes unitários, 9 golden. Verificador: pista inclinada, comprimento não múltiplo de 20 m e entrada 3857 fecham; imagem real com 225 MB de pico.
- 11/11 M4: `painel/dados.py` (funções puras: carregar, filtrar, resumir, por_segmento, ranking, exportações, cores, formato BR) e `painel/app.py` (filtros na barra lateral, 5 indicadores com "X de Y", mapa pydeck com prévia + buracos por severidade + segmentos opcionais, histograma, barras por segmento, ranking, tabela, downloads CSV/XLSX/GeoJSON). Conferido no Chrome real com Playwright: filtros mudam mapa/indicadores/tabela, downloads baixam, troca de levantamento, sem erro no console.
- 11/11 Acervo (pedido do usuário): `acervo.py` lê as GeoTIFF de `../images` (config `acervo.pasta_imagens` ou `PAVISCAN_IMAGENS`), com o polígono da pista ao lado (`<nome>.pista.geojson`). Painel escolhe a imagem numa lista e processa; CLI `paviscan imagens` e `paviscan run --orto <nome>`. `acervo.guardar()` já grava uma imagem recebida (arquivo ou stream, em blocos, valida raster com SRC antes de publicar) para o upload futuro.

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
- 11/11: pydeck dentro do Streamlit avalia string como expressão: a data URI da prévia vai entre aspas simples; acessores por nome de coluna (`PolygonLayer` + coluna `contorno`), nunca `@@=`. Zoom do deck.gl usa mundo de 512 px.
- 11/11: imagens entram pelo acervo (pasta), não por upload: ortofoto passa de 200 MB. Upload no painel fica para depois, chamando `acervo.guardar` (atenção a `server.maxUploadSize`, padrão 200 MB).
- 11/11: tiles com `sobreposicao_m` (metros); cada buraco fica com o tile cujo miolo contém o centroide e, no fim, polígonos sobrepostos ficam só com o maior (`geometria.deduplicar`). Unir a máscara do trecho inteiro foi descartado por memória em ortofoto grande.
- 11/11: ambiente em `.venv` com Python 3.12; `core.fileMode=false` no repo (Windows).
- 10/11: escopo reduzido a um retrato de uma imagem. Orçamento e série temporal saíram.
- 10/11: detector por anomalia escura local com limiar robusto (mediana + k x MAD), não Otsu nem watershed puro. YOLO do mestrado entra depois pela interface `Detector`.
- 10/11: saída visual é um dashboard Streamlit com filtros de área, severidade, confiança e segmento.

## Pendências e dúvidas para o usuário
- (M5) Painel: sanitizar o nome do levantamento e avisar antes de sobrescrever; deixar claro que a % e os buracos/100 m são da pista inteira quando há filtro de segmento.
- Arquivos do repo foram regravados por fora duas vezes (geometria.py truncado às 09:52, cli.py voltou a uma versão antiga às 10:32), provavelmente buffer antigo do VS Code com salvamento automático ou o OneDrive. Ambos restaurados. Convém fechar abas antigas do editor e pausar a sincronização do OneDrive nesta pasta.
- Upload de imagem pelo painel (futuro): `acervo.guardar` pronto; falta o `st.file_uploader` e decidir o limite de tamanho.
- (menor) resto de segmento muito curto (ex.: 0,5 m) deixa pct_afetada instável; avaliar juntar ao anterior.
- (menor) area_pista_m2 não desconta área sem imagem (branco) se o polígono sair da área imageada.
- O repositório está no OneDrive: um arquivo foi regravado truncado durante um commit (2e19b7b fica quebrado no histórico; f7b1913 corrige). Sugestão: pausar a sincronização ou mover o repo para fora do OneDrive.
- (menor) `deduplicar` usa interseção > 0; avaliar tolerância relativa se aparecer caso real.
- Ortofoto real (GSD de 5 cm/px ou melhor) e polígono da pista.
- Confirmar as faixas de severidade em `config/params.yaml`.
