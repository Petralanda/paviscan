"""Linha de comando: paviscan run | paviscan painel."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(add_completion=False, help="Buracos em pavimento a partir de ortofotos.")


@app.command()
def run(
    orto: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="Ortofoto GeoTIFF")],
    pista: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="Poligono da pista")],
    saida: Annotated[Path, typer.Option(help="Pasta de saida")],
    config: Annotated[
        Path | None, typer.Option(exists=True, dir_okay=False, help="params.yaml")
    ] = None,
) -> None:
    """Processa uma ortofoto e grava os resultados em SAIDA."""
    from paviscan.pipeline import processar

    def avisar(frac: float, msg: str) -> None:
        typer.echo(f"[{frac:4.0%}] {msg}")

    out = processar(orto, pista, saida, config, progresso=avisar)
    typer.echo(f"Resultados em {out}")


@app.command()
def painel(
    runs: Annotated[Path, typer.Option(help="Pasta com os levantamentos")] = Path("runs"),
) -> None:
    """Abre o dashboard no navegador."""
    app_py = Path(__file__).parent / "painel" / "app.py"
    env = {**os.environ, "PAVISCAN_RUNS": str(runs.resolve())}
    raise typer.Exit(
        subprocess.call([sys.executable, "-m", "streamlit", "run", str(app_py)], env=env)
    )


if __name__ == "__main__":
    app()
