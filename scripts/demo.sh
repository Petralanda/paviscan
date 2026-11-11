#!/usr/bin/env bash
# Prepara a demo: cena sintetica + todas as imagens do acervo que tem pista, depois abre o painel.
# Uso: ./scripts/demo.sh [--sem-painel]
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe   # Windows
elif [ -x .venv/bin/python ]; then PY=.venv/bin/python
else PY=python; fi

RUNS=runs/demo
mkdir -p "$RUNS"

echo "== cena sintetica (gabarito conhecido)"
"$PY" -c "from paviscan import sintetico; sintetico.gerar_cena('dados/sint/cena', seed=7)"
"$PY" -m paviscan.cli run --orto dados/sint/cena/orto.tif --pista dados/sint/cena/pista.geojson \
  --saida "$RUNS/sintetico"

echo "== imagens do acervo com poligono da pista"
"$PY" - "$RUNS" <<'EOF'
import sys
from pathlib import Path

from paviscan import acervo
from paviscan.pipeline import carregar_config, processar

runs = Path(sys.argv[1])
pasta = acervo.pasta(carregar_config())
imgs = acervo.listar(pasta)
print(f"acervo: {pasta} ({len(imgs)} imagens)")
for img in imgs:
    if img.pista is None:
        print(f"  pulando {img.caminho.name}: falta {img.nome}.pista.geojson")
        continue
    print(f"  processando {img.caminho.name}")
    processar(img.caminho, img.pista, runs / img.nome)
EOF

if [ "${1:-}" != "--sem-painel" ]; then
  echo "== abrindo o painel (Ctrl+C para sair)"
  exec "$PY" -m paviscan.cli painel --runs "$RUNS"
fi
