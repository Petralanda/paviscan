# PaviScan: plano de execução

Objetivo: uma imagem aérea de um trecho asfaltado entra, os buracos saem localizados e medidos, e tudo aparece num dashboard com filtros. É um retrato do momento: uma imagem, um resultado. Sem orçamento e sem comparação entre datas. Tudo em Python.

Prazo: 11 a 17 NOV, apresentação dia 18.

## 1. Decisões já tomadas

| Tema | Decisão | Motivo |
|---|---|---|
| Detector agora | Anomalia escura local com limiar robusto e filtros de forma, atrás de uma interface `Detector` | É o que funciona sem dados anotados. Detalhe na seção 3 |
| Detector depois | YOLO de segmentação do mestrado, plugado pela mesma interface | É o recomendado para uso real, mas depende de pesos treinados em ortofoto |
| Unidade de análise | Buraco como polígono em UTM | Área, largura e comprimento saem da geometria |
| Severidade | Três faixas por área (baixa, média, alta), limites em config | Dá um filtro útil no dashboard. Não é classificação de norma |
| Dashboard | Streamlit + pydeck (mapa) + Plotly (gráficos) | Python puro, filtros prontos |
| Armazenamento | Uma pasta por execução, GeoJSON + JSON | Sem banco |
| Fora do escopo | Orçamento, série temporal, profundidade, trincas | Decisão de 10/11 para caber no prazo |

## 2. Insumo: o que funciona e o que não funciona

A regra: o buraco precisa ter pelo menos 6 pixels de lado. Buraco de 30 cm pede GSD de 5 cm/px ou melhor.

| Fonte | GSD típico | Serve? |
|---|---|---|
| Ortofoto de drone (do mestrando ou própria) | 1 a 3 cm | Sim. É o insumo certo |
| OpenAerialMap (drone, CC-BY 4.0, baixa GeoTIFF) | 1 a 30 cm, filtrar por ≤ 5 cm | Sim, para desenvolver e para a demo |
| Google Earth / Google Maps | 15 a 50 cm no Brasil | Não. Um buraco vira 1 a 3 pixels, e os termos de uso não permitem extrair dados da imagem |
| Mapillary / KartaView | Foto de rua em perspectiva | Não neste prazo. Medir área exige retificar a perspectiva |
| Gerador sintético (`paviscan.sintetico`, já no repo) | Qualquer | Sim. É o gabarito dos testes e o plano B da demo |

Como só precisamos de uma imagem por trecho, o OpenAerialMap resolve bem: basta achar uma ortofoto de drone com asfalto ruim.

## 3. Detector: por que não só watershed

Watershed separa regiões que se tocam. Ele não decide o que é buraco. O que decide é comparar cada pixel com o asfalto em volta. A receita:

1. Cinza com redução leve de ruído, só dentro da pista.
2. Fundo local: estimativa do asfalto "limpo" numa janela maior que o maior buraco esperado (~2 m). Anomalia = fundo menos imagem. Isso cancela sombra larga e variação de iluminação, que derrubam um limiar global.
3. Limiar robusto: mediana + k x MAD da anomalia. Otsu não serve aqui porque sempre divide a imagem em duas classes, mesmo quando não há buraco nenhum.
4. Limpeza morfológica e componentes conexos. Watershed entra só para separar buracos colados.
5. Filtros de forma em metros: área, solidez e alongamento. Cortam faixa pintada, trinca, sombra de poste e borda de sombra.
6. Confiança por contraste e nitidez da borda.

Limites conhecidos: mancha de óleo, remendo escuro, tampa de bueiro e poça vão aparecer como buraco. Isso é esperado de um método sem aprendizado e deve ser dito na apresentação. O filtro de confiança do dashboard ajuda a esconder os casos fracos.

Se sobrar tempo: refinar a borda de cada candidato com o SAM (modelo de segmentação pré-treinado). Só vale se houver GPU.

## 4. Pipeline

```
ortofoto.tif + pista.geojson
  [1] ingestao     lê em janelas, confere SRC e GSD, reprojeta para UTM se preciso
  [2] pista        recorta para o polígono da pista
  [3] deteccao     Detector.detectar(tile) -> máscaras
  [4] geometria    máscara -> polígono em UTM: área, largura, comprimento, severidade
  [5] indicadores  por segmento de 20 m: nº de buracos, área, % afetada
  [6] saidas       defeitos.geojson, segmentos.geojson, resumo.json, previa.png, XLSX
  [7] painel       dashboard lendo a pasta de saída
```

## 5. Dashboard

Roda com `paviscan painel`. É a tela da apresentação.

| Parte | Conteúdo |
|---|---|
| Entrada | Escolher um levantamento já processado ou apontar uma imagem nova e processar na hora |
| Filtros (barra lateral) | Faixa de área, severidade, confiança mínima, segmentos |
| Indicadores | Nº de buracos, área total, % da pista afetada, buracos por 100 m, maior buraco |
| Mapa | Ortofoto + buracos coloridos por severidade, com tooltip. Camada opcional de segmentos coloridos pela % afetada |
| Gráficos | Distribuição das áreas; área afetada ao longo da pista, por segmento |
| Ranking | Piores segmentos |
| Tabela | Buracos filtrados, com download CSV, XLSX e GeoJSON |

## 6. Marcos

| Marco | Dia | Entrega | Pronto quando |
|---|---|---|---|
| M1 | 11 Qua | Ingestão, pista, CLI `paviscan run` em esqueleto | Lê a cena sintética e grava o recorte da pista |
| M2 | 12 Qui | Detector + geometria | `tests/golden/test_deteccao.py` passa |
| M3 | 13 Sex | Indicadores por segmento, exportações e primeiro teste em imagem real | `tests/golden/test_indicadores.py` passa e uma imagem real foi processada |
| M4 | 16 Seg | Dashboard com filtros | `tests/golden/test_painel.py` passa e o painel foi conferido no navegador |
| M5 | 17 Ter | Ajuste em imagem real, README, ensaio | Demo roda do zero em < 10 min |

Ponto de corte: se o M2 não passar até o fim do dia 12, o fim de semana vai para a detecção e o M3 encolhe para só as exportações.

Com o orçamento e a série temporal fora, o cronograma tem folga. O melhor uso dela é rodar em imagem real cedo (dia 13), porque é lá que o detector vai falhar de jeitos que o sintético não mostra.

## 7. Como rodar com o Claude Code

```bash
cd paviscan
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
claude
```

Dentro do Claude Code:
- `/marco M1` executa o marco: planeja, delega aos especialistas, roda a verificação, faz commit.
- `/verificar` roda lint + testes + golden e devolve o veredito do agente verificador.
- `/status` mostra o que falta.

| Peça | Arquivo | Função |
|---|---|---|
| Memória do projeto | `CLAUDE.md` | Contexto, contratos entre módulos, regras |
| Estado entre sessões | `PROGRESS.md` | O que foi feito, decisões, pendências |
| Especialistas | `.claude/agents/*.md` | geo-raster, cv-detector, dashboard, verificador |
| Fluxos | `.claude/skills/*/SKILL.md` | /marco, /verificar, /status |
| Trilhos | `.claude/settings.json` | Permissões, formatação automática, golden protegido contra edição |
| Gabarito | `tests/golden/` + `sintetico.py` | Testes de aceite escritos antes do código. O agente não pode alterá-los |

Quem escreve o código não é quem decide se está pronto: o verificador é só leitura, e os testes de aceite já existem e estão bloqueados.

## 8. Git

```bash
cd paviscan
# o zip já vem com git iniciado e commits; do zero seria: git init -b main && git add -A && git commit -m "Scaffold inicial"
gh repo create paviscan --private --source=. --push   # ou criar no site e: git remote add origin <url> && git push -u origin main
```

Um commit por tarefa concluída, um tag por marco (`git tag m1`).

## 9. Riscos

| Risco | O que fazer |
|---|---|
| Falso positivo em imagem real (óleo, remendo, bueiro, poça) | Esperado. Ajustar limiares em config, usar o filtro de confiança, e dizer o limite na apresentação |
| Sem imagem real até dia 13 | OpenAerialMap. Em último caso, a demo usa a cena sintética |
| Não ter o polígono da pista | Desenhar no QGIS em 5 minutos. Detecção automática da pista fica fora |
| Dashboard bonito toma tempo sem fim | Fechar primeiro filtros e mapa funcionando. Acabamento só depois do golden passar |
