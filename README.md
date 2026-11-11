# PaviScan

Buracos em pavimento a partir de ortofoto de drone. Uma imagem entra, os buracos saem como polígonos em UTM, com área, largura, comprimento, severidade e o segmento de 20 m em que caem, e tudo aparece num dashboard com filtros. É um retrato da data do voo: não há orçamento nem comparação entre datas.

## Usar sem terminal (Windows)

1. Na primeira vez, dê dois cliques em `Instalar.bat` (5 a 10 minutos).
2. Dê dois cliques em `PaviScan.bat`. O navegador abre em http://localhost:8501. Para encerrar, feche a janela preta.
3. No painel, abra **Imagens: enviar e processar**:
   - **Enviar imagem**: escolha a `.tif` (até 4 GB) e, se tiver, o polígono da pista (GeoJSON ou GPKG). Clique em **Guardar no acervo**. A imagem fica na pasta `images`.
   - **Processar**: escolha a imagem e clique em **Processar**. Se ela ainda não tiver o polígono da pista, a própria aba pede o arquivo.
4. Os resultados ficam em `runs/levantamentos` e aparecem no seletor da barra lateral.

## Instalar (linha de comando)

Python 3.10 ou mais novo (testado com 3.12).

```bash
python -m venv .venv
source .venv/bin/activate          # Windows (Git Bash): source .venv/Scripts/activate
pip install -e ".[dev]"
```

A instalação leva de 5 a 8 minutos numa máquina limpa (rasterio, geopandas, streamlit). Para a apresentação, deixe o ambiente instalado antes.

## Demo em um comando

```bash
./scripts/demo.sh
```

O script gera a cena sintética (com gabarito conhecido), processa todas as imagens do acervo que têm polígono da pista e abre o painel em http://localhost:8501. No ensaio a partir de um clone limpo, o tempo total foi de 8 min 52 s, sendo 8 min de instalação e 48 s da demo em si.

## Acervo de imagens

As ortofotos ficam numa pasta, o acervo. Por padrão é `../images`, ao lado do repositório; dá para mudar em `config/params.yaml` (`acervo.pasta_imagens`) ou com a variável `PAVISCAN_IMAGENS`.

- Formatos: GeoTIFF (`.tif`, `.tiff`, `.geotiff`) com SRC. SRC em graus, Web Mercator ou pés é reprojetado para UTM (SIRGAS 2000 no Brasil) antes de medir.
- Cada imagem precisa do polígono da pista ao lado, com o mesmo nome: `trecho.tif` + `trecho.pista.geojson`. Desenhe no QGIS em poucos minutos e recue uns 30 cm do meio-fio (a sarjeta gera falso positivo).
- Resolução: o buraco precisa de pelo menos 6 pixels de lado. Para buraco de 30 cm, use GSD de 5 cm/px ou melhor. Google Earth não serve.
- Para guardar imagem nova por código: `paviscan.acervo.guardar(arquivo, nome, pasta)` grava em blocos e só publica depois de validar que é um raster georreferenciado. É a peça para o upload pelo painel, que fica para depois.

## Linha de comando

```bash
paviscan imagens                                     # lista o acervo e diz quem já tem pista
paviscan run --orto trecho --saida runs/trecho       # nome do acervo; usa trecho.pista.geojson
paviscan run --orto X.tif --pista p.geojson --saida runs/x
paviscan painel --runs runs/                         # abre o dashboard
```

Cada execução grava numa pasta:

| Arquivo | Conteúdo |
|---|---|
| `defeitos.geojson`, `defeitos.gpkg` | Buracos em UTM: id, area_m2, largura_m, comprimento_m, confianca, severidade, segmento |
| `segmentos.geojson` | Pista cortada em trechos de 20 m: área de pista, nº de buracos, área de buracos, % afetada |
| `resumo.json`, `resumo.xlsx` | Números do levantamento; o XLSX tem as abas Resumo, Buracos e Segmentos |
| `previa.png` | Ortofoto reduzida do entorno da pista, para o mapa do painel |
| `pista_recorte.tif` | Ortofoto recortada à pista |

## Painel

Na barra lateral: levantamento, faixa de área, severidade, confiança mínima e segmentos. No corpo, de cima para baixo:

- os indicadores (nº de buracos, área total, % da pista afetada, buracos por 100 m, maior buraco);
- o mapa com a ortofoto e os buracos por cor de severidade (com os segmentos opcionais);
- o histograma das áreas e a área afetada por segmento;
- o ranking dos piores segmentos;
- a tabela com download em CSV, XLSX e GeoJSON.

"Processar nova imagem" escolhe uma imagem do acervo e processa na hora.

## Como o detector funciona

Ele compara cada pixel com o asfalto em volta, e não com um limiar global:

1. Fundo local: mediana numa janela de 2 m.
2. Anomalia = fundo − imagem.
3. Limiar robusto = mediana + 6 × MAD, com um piso. Não é Otsu, que inventa buraco em pista limpa.
4. Filtros de forma em metros: área, solidez e alongamento.
5. Descarte de regiões escuras coladas a um objeto claro, grande e compacto, com cara de lataria (para-brisa e sombra de carro). Sinalização comprida, como faixa de pedestre e linha de retenção, não conta.
6. Confiança pelo contraste e pela nitidez da borda.

Todos os limiares estão em `config/params.yaml`, em metros.

Resultados:

- Cena sintética (seeds 7, 11, 23 e 42; GSD de 1 a 5 cm): recall de 100%, nenhum falso positivo, erro de área mediano de 2% a 5%. Em pista sem buraco, nenhuma detecção.
- Imagem real (Manaus, 3 cm, 120 m de avenida): 33 detecções, contra 39 sem o filtro de veículo. Quase todas são falsos positivos: caminhão, borda desgastada ou sarjeta e sombra de poste. O trecho tem poucas panelas, então mede falso positivo e não recall.

Limites conhecidos, que valem para qualquer método sem aprendizado:

- mancha de óleo, remendo escuro, bueiro, poça e veículo escuro aparecem como buraco;
- buraco colado a um objeto claro grande e compacto (placa de concreto de vários m², veículo estacionado) é descartado junto com os para-brisas;
- profundidade não é medida.

O filtro de confiança do painel esconde os casos fracos. O próximo passo é o YOLO de segmentação, plugado na mesma interface `Detector`.

## Desenvolvimento

```bash
./scripts/verify.sh            # lint + formato + testes unitários + testes de aceite (golden)
pytest tests/golden -q         # só os testes de aceite, que não devem ser editados
```

Contratos entre módulos em `CLAUDE.md`, plano em `PLAN.md`, estado em `PROGRESS.md`, roteiro da apresentação em `ROTEIRO.md`.
