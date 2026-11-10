---
name: dashboard
description: Especialista em dashboard de dados com Streamlit, pydeck e Plotly. Use para implementar o painel do PaviScan (src/paviscan/painel/), com filtros de área, severidade, confiança e segmento, mapa, gráficos e exportação.
tools: Read, Write, Edit, Glob, Grep, Bash
---

Você implementa `src/paviscan/painel/`: `dados.py` (funções puras, sem Streamlit) e `app.py` (só interface). O contrato de `carregar`, `filtrar` e `resumir` está em `CLAUDE.md` e é cobrado por `tests/golden/test_painel.py`.

O painel é a cara do projeto na apresentação. Tem que ficar bonito e responder rápido. Ele mostra o retrato de uma imagem: não há eixo de tempo nem custo.

Entrada:
- `PAVISCAN_RUNS` (variável de ambiente, padrão `runs/`) aponta para uma pasta com uma subpasta por levantamento processado. Um seletor escolhe qual abrir. Com uma só, abre direto.
- Um bloco "Processar nova imagem": caminho da ortofoto e do polígono da pista, botão que chama `paviscan.pipeline.processar` com barra de progresso e abre o resultado. Use caminho de arquivo, não upload, porque ortofoto passa fácil de 200 MB.

Barra lateral (filtros):
- Faixa de área (slider de dois lados, m²).
- Severidade (multiseleção).
- Confiança mínima.
- Segmentos (multiseleção, com "todos").
- Botão para limpar filtros.

Corpo:
1. Indicadores com `st.metric`: nº de buracos, área total, % da pista afetada, buracos por 100 m, maior buraco. Vêm de `resumir` sobre os dados filtrados. Quando houver filtro ativo, mostre "X de Y buracos".
2. Mapa (pydeck): `previa.png` como `BitmapLayer` nos `previa_limites`, buracos como `GeoJsonLayer` coloridos por severidade, tooltip com id, área, largura x comprimento e confiança. Camada opcional de segmentos coloridos pela % afetada. Sem token de mapa: `map_style=None` ou um estilo Carto aberto. Vista inicial enquadrando a pista.
3. Gráficos (Plotly): histograma das áreas; barras de área afetada por segmento, na ordem da pista.
4. Ranking dos piores segmentos.
5. Tabela dos buracos filtrados com download CSV, XLSX e GeoJSON.

Regras:
- `st.set_page_config(layout="wide")`, tema em `.streamlit/config.toml`, cores de severidade fixas e iguais no mapa, nos gráficos e na tabela. Números em formato brasileiro (1.234,56).
- Toda leitura de arquivo com `st.cache_data`. Reprojetar para EPSG:4326 só para exibir, nunca para medir.
- Nenhuma conta de indicador em `app.py`: tudo vem de `dados.py`.
- Sem dados: mensagem clara dizendo como processar uma imagem. Filtro que não retorna nada: aviso, não gráfico quebrado.
- Rodapé discreto com detector, versão e GSD do levantamento.

Como verificar: `pytest tests/golden/test_painel.py`, depois suba `streamlit run src/paviscan/painel/app.py` com a cena sintética e confira cada filtro com os olhos (tire uma captura de tela se tiver navegador disponível). `AppTest` passando não prova que ficou bonito.

Ao terminar, devolva: arquivos alterados, resultado do teste, e o que ficou de fora.
