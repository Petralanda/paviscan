---
name: verificar
description: Roda a verificação completa do PaviScan (lint, testes, golden) e pede o veredito do agente verificador. Use antes de commit ou quando o usuário perguntar se está funcionando.
argument-hint: "[m1|m2|m3|m4|tudo]"
---

1. Rode `./scripts/verify.sh $ARGUMENTS` (sem argumento, usa `tudo`).
2. Chame o subagente `verificador` passando o alvo e a saída do script.
3. Mostre ao usuário o veredito, os números de robustez e a lista de problemas, sem suavizar. Não corrija nada nesta skill: só relate e pergunte se deve corrigir.
