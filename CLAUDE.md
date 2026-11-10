# PaviScan

Pipeline em Python: ortofoto de pista asfaltada -> buracos como polígonos em UTM -> área -> opções de reparo e orçamento -> série temporal entre datas -> dashboard Streamlit com filtros e XLSX. Plano completo em `PLAN.md`. Estado atual em `PROGRESS.md` (leia no início de toda sessão, atualize no fim).

## Comandos

```bash
pip install -e ".[dev]"
./scripts/verify.sh            # lint + testes + golden. É a definição de pronto
pytest tests/golden -q         # só os testes de aceite
python -m paviscan.sintetico dados/sint --seed 7    # gera cena de teste com gabarito
paviscan run --orto X.tif --pista pista.geojson --saida runs/nome
paviscan comparar runs/antes runs/depois --saida runs/comp
paviscan serie dados/trecho/ --saida runs/trecho      # uma subpasta AAAA-MM-DD por levantamento
paviscan painel --runs runs/trecho                   # abre o dashboard
```

## Estrutura

```
src/paviscan/
  sintetico.py    PRONTO. Gera ortofoto + pista + gabarito. Não mudar a assinatura
  ingestao.py     M1  abrir raster em janelas, SRC, GSD, reprojeção para UTM
  pista.py        M1  máscara da pista a partir do polígono
  deteccao/       M2  base.py (Protocol), classico.py (watershed), yolo.py (futuro)
  geometria.py    M2  máscara -> polígonos UTM, área, retângulo de corte
  orcamento.py    M3  soluções, preços, opções A/B/C
  comparacao.py   M3  casar buracos de duas datas e montar a serie (id persistente)
  painel/         M4  dados.py (funcoes puras) e app.py (Streamlit)
  pipeline.py     M1+ orquestra tudo
  cli.py          M1+ typer
config/           params.yaml, solucoes.csv, precos.csv
tests/golden/     testes de aceite. BLOQUEADOS para edição
tests/unit/       testes que você escreve
```

## Contratos (os testes golden dependem deles)

```python
# paviscan/pipeline.py
def processar(orto: Path, pista: Path, saida: Path, config: Path | None = None) -> Path
# grava em saida/: defeitos.geojson (SRC UTM; colunas id, area_m2, area_corte_m2, confianca)
#                  orcamento.csv   (colunas id, opcao, servico, unidade, quantidade, preco_unit, custo)
#                  resumo.json     (gsd_m, n_defeitos, area_total_m2, custo_por_opcao{A,B,C}, detector, versao)

def comparar(antes: Path, depois: Path, saida: Path, tolerancia_m: float = 0.5) -> Path
# antes e depois são pastas de saída de processar().
# grava saida/comparacao.geojson com coluna status em {"novo","cresceu","estavel","reparado"}
#        saida/comparacao.json   {novos, cresceram, estaveis, reparados, delta_area_m2}

def processar_serie(cenas: list[Path], saida: Path, config: Path | None = None) -> Path
# cada cena e uma pasta com orto.tif, pista.geojson e meta.json contendo "data" (AAAA-MM-DD).
# grava saida/<data>/ (igual a processar, mais previa.png da ortofoto reduzida) e
#       saida/serie.geojson: uma linha por buraco por data, colunas
#       data, id, id_persistente, status, area_m2, area_corte_m2, confianca, segmento, custo_A, custo_B
# status em {"inicial","novo","cresceu","estavel","reparado"}; tudo "inicial" na primeira data.
# id_persistente acompanha o mesmo buraco entre datas. Linha "reparado" repete a geometria da data anterior.

# paviscan/painel/dados.py  (sem importar streamlit)
def carregar(runs: Path) -> gpd.GeoDataFrame        # le serie.geojson; coluna data como datetime
def filtrar(df, data_ini=None, data_fim=None, status=None, area_min=None, area_max=None,
            segmentos=None, confianca_min=None) -> gpd.GeoDataFrame   # None = nao filtra; datas inclusivas

# paviscan/deteccao/base.py
class Detector(Protocol):
    nome: str
    versao: str
    def detectar(self, img: np.ndarray, gsd_m: float, valida: np.ndarray) -> list[Deteccao]: ...
    # img: RGB uint8 HxWx3. valida: bool HxW (True = pista). Sem estado entre chamadas.

@dataclass
class Deteccao:
    mascara: np.ndarray   # bool HxW, um buraco por detecção
    confianca: float      # 0 a 1
    classe: str = "panela"
```

O detector é escolhido por `config/params.yaml: detector: classico`. Nada fora de `deteccao/` pode saber qual detector está rodando.

## Regras

- Toda medida é feita em SRC projetado em metros. Se a entrada vier em graus, reprojetar para a zona UTM do centroide antes de qualquer cálculo.
- Nunca carregar o raster inteiro: ler por janelas (`rasterio.windows`), com sobreposição para o buraco não ser cortado na borda.
- Limiares e preços moram em `config/`, nunca no código.
- Não editar `tests/golden/` nem `src/paviscan/sintetico.py` para fazer teste passar. Se o teste parecer errado, pare e explique ao usuário.
- Não inventar preço. `precos.csv` tem a coluna `fonte`; placeholder fica marcado como PLACEHOLDER e aparece assim na planilha.
- Código e nomes em português sem acento, docstrings curtas, type hints, sem classes onde função resolve.
- Um commit por tarefa, mensagem em português no imperativo. Não dar push sem o usuário pedir.

## Como trabalhar

1. Leia `PROGRESS.md` e a seção do marco em `PLAN.md`.
2. Planeje em tarefas pequenas. Tarefas independentes vão para especialistas em paralelo; dependentes, em sequência.
3. Ao delegar, passe ao subagente: arquivos a criar, o contrato acima que se aplica, e o teste que precisa passar. Ele não vê esta conversa.
4. Terminou de codar: `./scripts/verify.sh`. Depois chame o `verificador` (ele não viu o código ser escrito). Só é "pronto" com o veredito APROVADO.
5. Atualize `PROGRESS.md`, faça commit.

Especialistas em `.claude/agents/`: `geo-raster`, `cv-detector`, `orcamentista`, `serie-temporal`, `dashboard`, `verificador`.
