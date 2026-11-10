# PaviScan: plano de execução

Objetivo: imagem aérea de um trecho asfaltado entra, buracos saem medidos em m², com opções de reparo e orçamento. Com várias datas do mesmo trecho, sai a evolução no tempo. Tudo aparece num dashboard com filtros. Tudo em Python.

Prazo: 11 a 17 NOV, apresentação dia 18.

## 1. Decisões já tomadas

| Tema | Decisão | Motivo |
|---|---|---|
| Detector | Visão clássica (anomalia escura + watershed) atrás de uma interface `Detector` | Testa o sistema inteiro agora. O YOLO do mestrado entra depois trocando uma linha de config |
| Unidade de análise | Buraco (panela) como polígono em UTM | Área em m² sai direto da geometria |
| Profundidade | Valor assumido por configuração (padrão 5 cm). Se houver MDS, usa o desnível | Imagem 2D não tem profundidade. Não é crucial |
| Série temporal | N levantamentos do mesmo trecho, cada buraco com um ID que o acompanha entre datas. Sem dados reais, usa a série sintética | O filtro de tempo do dashboard depende disso |
| Dashboard | Streamlit + pydeck (mapa) + Plotly (gráficos) | Python puro, filtros prontos, fica bonito rápido |
| Armazenamento | Uma pasta por data, GeoJSON + CSV, e um `serie.geojson` consolidado | Sem banco |

## 2. Insumo: o que funciona e o que não funciona

A regra: o buraco precisa ter pelo menos 6 pixels de lado. Buraco de 30 cm pede GSD de 5 cm/px ou melhor.

| Fonte | GSD típico | Serve? |
|---|---|---|
| Ortofoto de drone (do mestrando ou própria) | 1 a 3 cm | Sim. É o insumo certo |
| OpenAerialMap (drone, CC-BY 4.0, baixa GeoTIFF) | 1 a 30 cm, filtrar por ≤ 5 cm | Sim, para desenvolver. Par antes/depois do mesmo trecho é raro |
| Google Earth / Google Maps | 15 a 50 cm no Brasil | Não. Um buraco vira 1 a 3 pixels. Além disso os termos de uso não permitem extrair dados da imagem. Só serve de fundo no mapa |
| Mapillary / KartaView (o "street view aberto") | Foto de rua em perspectiva | Não neste prazo. Tem histórico, mas medir área exige retificar a perspectiva |
| Gerador sintético (`paviscan.sintetico`, já no repo) | Qualquer | Sim. É o gabarito dos testes e o plano B do antes/depois |

Ordem de tentativa: ortofoto real do mestrando, depois OpenAerialMap, depois sintético. O sistema roda igual nos três.

## 3. Pipeline

```
ortofoto.tif + pista.geojson
  [1] ingestao    lê em janelas, confere SRC e GSD, reprojeta para UTM se preciso
  [2] pista       recorta para o polígono da pista
  [3] deteccao    Detector.detectar(tile) -> máscaras   (classico | yolo no futuro)
  [4] geometria   máscara -> polígono em UTM, área m², retângulo de corte do remendo
  [5] orcamento   área x solução x preço -> opções A/B/C por buraco e total
  [6] serie       casa buracos entre datas: id persistente e status (novo, cresceu, estavel, reparado)
  [7] painel      dashboard Streamlit lendo serie.geojson + orcamento.xlsx para exportar
```

Detector clássico (passo 3), em ordem:
1. Cinza + CLAHE dentro da máscara da pista.
2. Fundo do asfalto por mediana grande (janela de ~1,5 m). Anomalia = fundo menos imagem.
3. Limiar de Otsu na anomalia, abertura e fechamento morfológicos.
4. Transformada de distância + watershed para separar buracos colados.
5. Filtros: área entre 0,05 e 10 m², solidez ≥ 0,6, alongamento ≤ 4 (corta sombra de poste, trinca e faixa).

Orçamento (passo 5), três opções por buraco:
- A. Tapa-buraco superficial: área do retângulo de corte x espessura do revestimento.
- B. Remendo profundo: A + recomposição de base. Indicado quando o terreno (subleito) é ruim.
- C. Fresagem e recapeamento do segmento inteiro, quando a área afetada do segmento passa de um limite (padrão 15%).

Variam por tipo de pavimento (CBUQ, PMF, TSD) e por condição do terreno (bom, regular, ruim), tudo em `config/`. Os preços que estão lá são placeholders: trocar pelo SICRO/SINAPI do mês antes de mostrar qualquer número.

## 4. Dashboard

Roda com `paviscan painel` (Streamlit). É a tela da apresentação.

| Parte | Conteúdo |
|---|---|
| Filtros (barra lateral) | Período (slider de datas), status do buraco, faixa de área, confiança mínima, segmentos |
| Opções de orçamento | Tipo de pavimento, condição do terreno, opção de reparo A/B/C, BDI. Mudou, o custo recalcula na hora |
| Indicadores | Buracos ativos, área total, custo total, cada um com a variação contra o levantamento anterior |
| Mapa | Ortofoto da data escolhida + buracos coloridos por status, com tooltip |
| Evolução | Área e custo por data; novos x reparados por data |
| Ranking | Segmentos que mais pioraram no período |
| Tabela | Buracos filtrados, com download CSV e XLSX |

## 5. Marcos

| Marco | Dia | Entrega | Pronto quando |
|---|---|---|---|
| M1 | 11 Qua | Ingestão, pista, CLI `paviscan run` esqueleto | Lê a cena sintética e grava recorte da pista |
| M2 | 12 Qui | Detector clássico + geometria | `tests/golden/test_deteccao.py` passa |
| M3 | 13 Sex | Orçamento com opções A/B/C e XLSX + comparação e série temporal | `test_orcamento.py` e `test_comparacao.py` passam |
| M4 | 16 Seg | Dashboard com filtros | `tests/golden/test_painel.py` passa e o painel foi conferido no navegador |
| M5 | 17 Ter | Rodar em imagem real, README, ensaio | Demo roda do zero em < 10 min |

Ponto de corte: se M2 não passar até o fim do dia 12, a série temporal sai e o dashboard mostra uma data só.

O dashboard entrou depois do cronograma original e o M3 ficou pesado. A reserva do fim de semana (14 e 15) passa a ser provável, não só garantia.

## 6. Como rodar com o Claude Code

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

O que tem no harness (pasta `.claude/`):

| Peça | Arquivo | Função |
|---|---|---|
| Memória do projeto | `CLAUDE.md` | Contexto, contratos entre módulos, regras |
| Estado entre sessões | `PROGRESS.md` | O que foi feito, decisões, pendências |
| Especialistas | `.claude/agents/*.md` | geo-raster, cv-detector, orcamentista, serie-temporal, dashboard, verificador |
| Fluxos | `.claude/skills/*/SKILL.md` | /marco, /verificar, /status |
| Trilhos | `.claude/settings.json` | Permissões, formatação automática, golden protegido contra edição |
| Gabarito | `tests/golden/` + `sintetico.py` | Testes de aceite escritos antes do código. O agente não pode alterá-los |

A ideia central: quem escreve o código não é quem decide se está pronto. O verificador é só leitura, e os testes de aceite já existem e estão bloqueados.

## 7. Git

```bash
cd paviscan
# o zip ja vem com git iniciado e o primeiro commit; se partir do zero: git init -b main && git add -A && git commit -m "Scaffold inicial"
gh repo create paviscan --private --source=. --push   # ou criar no site e: git remote add origin <url> && git push -u origin main
```

Um commit por tarefa concluída, um tag por marco (`git tag m1`).

## 8. Riscos

| Risco | O que fazer |
|---|---|
| Detector clássico confunde sombra, mancha de óleo e remendo escuro com buraco | Esperado. A demo mostra o fluxo. Deixar limiares em config e relatar precisão no sintético |
| Sem imagem real até dia 13 | Seguir com OpenAerialMap + sintético |
| Duas datas desalinhadas | Casar por distância com tolerância (padrão 0,5 m) e relatar o deslocamento |
| Dashboard bonito toma tempo sem fim | Fechar primeiro os filtros e o mapa funcionando. Acabamento visual só depois do golden passar |
| Preço errado no orçamento | Planilha sai com a fonte e a data de cada preço. Placeholder aparece marcado |
