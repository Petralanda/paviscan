# Progresso

Atualize ao fim de cada sessão. Curto e factual.

## Estado

| Marco | Status | Observação |
|---|---|---|
| M1 Ingestão e pista | concluído (tag m1) | verify m1 OK, verificador APROVADO |
| M2 Detecção e geometria | a fazer | |
| M3 Indicadores, exportações e imagem real | a fazer | |
| M4 Dashboard | a fazer | |
| M5 Fechamento | a fazer | |

## Feito
- Scaffold, harness, gerador sintético e testes golden.
- 11/11 M1: `ingestao.py` (SRC, GSD, UTM SIRGAS no Brasil via WarpedVRT, janelas com sobreposição), `pista.py` (polígono, janela, máscara), `pipeline.processar` em esqueleto gravando `pista_recorte.tif`, CLI `paviscan run`/`painel`. 10 testes unitários. Robustez do verificador: área do recorte 420 m² em seeds 11/42, gsd 0,01 a 0,05, orto em 4326.

## Decisões
- 11/11: ambiente em `.venv` com Python 3.12; `core.fileMode=false` no repo (Windows).
- 10/11: escopo reduzido a um retrato de uma imagem. Orçamento e série temporal saíram.
- 10/11: detector por anomalia escura local com limiar robusto (mediana + k x MAD), não Otsu nem watershed puro. YOLO do mestrado entra depois pela interface `Detector`.
- 10/11: saída visual é um dashboard Streamlit com filtros de área, severidade, confiança e segmento.

## Pendências e dúvidas para o usuário
- (M3) Reprojetar também SRC projetado impróprio para medir (EPSG:3857, unidades em pés). Hoje só reprojeta SRC geográfico.
- (M3) Esticamento de contraste para float 0-1 e uint16 de 12 bits; nodata no WarpedVRT.
- Ortofoto real (GSD de 5 cm/px ou melhor) e polígono da pista.
- Confirmar as faixas de severidade em `config/params.yaml`.
