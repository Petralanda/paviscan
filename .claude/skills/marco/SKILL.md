---
name: marco
description: Executa um marco do PLAN.md de ponta a ponta (M1 a M5), delegando aos especialistas e fechando com verificação independente e commit.
argument-hint: "[M1|M2|M3|M4|M5]"
disable-model-invocation: true
---

Execute o marco **$ARGUMENTS** do PaviScan.

1. **Contexto.** Leia `PROGRESS.md`, a linha do marco em `PLAN.md` e os contratos em `CLAUDE.md`. Se o marco anterior não estiver concluído, pare e avise.

2. **Plano.** Quebre o marco em 3 a 6 tarefas, cada uma com arquivo a criar e teste que prova que funcionou. Mostre o plano em poucas linhas e siga sem esperar aprovação, a menos que algo contradiga o `PLAN.md`.

3. **Execução.** Você é o orquestrador: integra e decide, os especialistas implementam.

   | Marco | Especialistas | Observação |
   |---|---|---|
   | M1 | geo-raster | Você escreve `pipeline.py` e `cli.py` em esqueleto |
   | M2 | cv-detector e geo-raster em paralelo | Detector e geometria só se encontram no contrato `Deteccao`. Você integra |
   | M3 | orcamentista | |
   | M4 | viz-relatorio | Comparação primeiro, mapa depois |
   | M5 | nenhum fixo | Rodar em imagem real, README, ajustar config. Peça a imagem ao usuário se não houver em `dados/` |

   Ao delegar, o pedido precisa conter: objetivo, arquivos, o trecho do contrato que se aplica, o teste alvo e o que devolver. O especialista não vê esta conversa.

4. **Verificação.** Rode `./scripts/verify.sh` com o alvo do marco em minúsculas. Se falhar, corrija e repita. Passou: chame o `verificador` informando o marco.

5. **Correção.** Se REPROVADO, mande cada problema ao especialista responsável e volte ao passo 4. No máximo 3 voltas. Depois disso pare e explique ao usuário o que está travando.

6. **Fechamento.** Só com APROVADO: atualize `PROGRESS.md` (status, decisões, pendências), faça commit e `git tag` do marco em minúsculas. Termine com um resumo de 5 linhas: o que entrou, números do teste, pendências.

Nunca: editar `tests/golden/` ou `sintetico.py`, dar push, inventar preço, marcar como feito sem o veredito.
