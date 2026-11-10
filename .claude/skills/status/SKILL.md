---
name: status
description: Mostra em que ponto o PaviScan está: marcos concluídos, testes golden passando e próximas tarefas.
disable-model-invocation: true
---

1. Leia `PROGRESS.md` e rode `git log --oneline -10` e `git tag`.
2. Rode `pytest tests/golden -q --no-header 2>&1 | tail -15` para ver quais testes de aceite passam hoje.
3. Responda em uma tabela curta: marco, status, testes golden do marco (passando/total). Depois, as 3 próximas tarefas e as pendências que dependem do usuário.
