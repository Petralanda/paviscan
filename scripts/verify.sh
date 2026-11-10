#!/usr/bin/env bash
# Definicao de pronto. Uso: ./scripts/verify.sh [m1|m2|m3|m4|tudo]
set -uo pipefail
cd "$(dirname "$0")/.."
alvo="${1:-tudo}"
falhou=0

passo() { echo; echo "== $1"; shift; "$@" || falhou=1; }

passo "lint" ruff check src tests
passo "formato" ruff format --check src tests
[ -d tests/unit ] && passo "testes unitarios" pytest tests/unit -q

case "$alvo" in
  m1)   passo "smoke" python -c "import paviscan.pipeline, paviscan.cli" ;;
  m2)   passo "golden deteccao" pytest tests/golden/test_deteccao.py -q ;;
  m3)   passo "golden ate orcamento" pytest tests/golden/test_deteccao.py tests/golden/test_orcamento.py -q ;;
  m4|tudo) passo "golden completo" pytest tests/golden -q ;;
  *) echo "alvo desconhecido: $alvo"; exit 2 ;;
esac

# o gabarito nao pode ter sido alterado
if git rev-parse --git-dir >/dev/null 2>&1; then
  if ! git diff --quiet HEAD -- tests/golden src/paviscan/sintetico.py 2>/dev/null; then
    echo; echo "== ERRO: tests/golden ou sintetico.py foram modificados"; falhou=1
  fi
fi

echo
[ "$falhou" -eq 0 ] && echo "VERIFY: OK ($alvo)" || echo "VERIFY: FALHOU ($alvo)"
exit "$falhou"
