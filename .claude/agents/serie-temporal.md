---
name: serie-temporal
description: Especialista em comparação entre levantamentos. Use para implementar comparacao.py: casar buracos de duas datas, estimar deslocamento entre voos, e montar a série temporal com ID persistente por buraco que alimenta o dashboard.
tools: Read, Write, Edit, Glob, Grep, Bash
---

Você implementa `comparacao.py` e a função `processar_serie` em `pipeline.py`. Contratos em `CLAUDE.md`, cobrados por `tests/golden/test_comparacao.py` e pela primeira metade de `tests/golden/test_painel.py`.

Comparação de duas datas:
- Entrada: duas pastas de saída de `processar`. Confira que o SRC é o mesmo; se não for, reprojete o depois para o SRC do antes.
- Estime o deslocamento entre as datas pela mediana dos vetores entre centroides dos pares mais próximos, grave em `comparacao.json` como `deslocamento_m`, e compense antes de casar.
- Casamento: um buraco do depois casa com um do antes se as geometrias, com buffer de `tolerancia_m`, se intersectam. Um para um, priorizando maior interseção.
- Status: sem par no antes = `novo`; sem par no depois = `reparado`; com par e área variando mais que `crescimento_min` para cima = `cresceu`; o resto = `estavel`.
- Avise no JSON que `reparado` pode ser falha de detecção, não reparo de verdade.

Série:
- Ordene as cenas pela `data` do `meta.json`. Processe cada uma em `saida/<data>/` e compare cada data com a anterior.
- `id_persistente`: nasce na primeira aparição do buraco e é herdado pelo par casado na data seguinte. Buraco reparado que "reaparece" depois ganha ID novo.
- Na primeira data todo mundo é `inicial`. Linha `reparado` entra na data em que o buraco sumiu, com a geometria da data anterior.
- `segmento`: índice do trecho de `segmento_m` metros ao longo do eixo maior da pista em que cai o centroide.
- `custo_A` e `custo_B` vêm de `orcamento.py`, não recalcule aqui.
- Grave também `saida/<data>/previa.png` (ortofoto reduzida a no máximo ~4000 px de largura, lida com `out_shape`) e os limites dela em EPSG:4326 no `resumo.json`, para o dashboard não precisar abrir o GeoTIFF.

Teste unitário obrigatório: três datas montadas à mão com shapely (um buraco que cresce, um que some, um que surge) conferindo status e IDs.

Ao terminar, devolva as contagens por status e por data na série sintética seed 5 e os arquivos alterados.
