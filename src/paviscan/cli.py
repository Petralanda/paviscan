"""Linha de comando: paviscan run | paviscan imagens | paviscan painel."""

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
    orto: Annotated[
        str, typer.Option(help="Ortofoto GeoTIFF: caminho ou nome de uma imagem do acervo")
    ],
    saida: Annotated[Path, typer.Option(help="Pasta de saida")],
    pista: Annotated[
        Path | None,
        typer.Option(
            exists=True,
            dir_okay=False,
            help="Poligono da pista. Sem ele, usa <imagem>.pista.geojson do acervo",
        ),
    ] = None,
    config: Annotated[
        Path | None, typer.Option(exists=True, dir_okay=False, help="params.yaml")
    ] = None,
) -> None:
    """Processa uma ortofoto e grava os resultados em SAIDA."""
    from paviscan import acervo
    from paviscan.pipeline import carregar_config, processar

    pasta = acervo.pasta(carregar_config(config))
    try:
        caminho = acervo.achar(orto, pasta)
    except FileNotFoundError as e:
        raise typer.BadParameter(str(e), param_hint="--orto") from e
    pista = pista or acervo.pista_de(caminho)
    if pista is None:
        raise typer.BadParameter(
            f"sem --pista e sem {caminho.stem}.pista.geojson ao lado da imagem",
            param_hint="--pista",
        )

    def avisar(frac: float, msg: str) -> None:
        typer.echo(f"[{frac:4.0%}] {msg}")

    out = processar(caminho, pista, saida, config, progresso=avisar)
    typer.echo(f"Resultados em {out}")


@app.command()
def imagens(
    config: Annotated[
        Path | None, typer.Option(exists=True, dir_okay=False, help="params.yaml")
    ] = None,
) -> None:
    """Lista as ortofotos do acervo e se cada uma ja tem o poligono da pista."""
    from paviscan import acervo
    from paviscan.pipeline import carregar_config

    pasta = acervo.pasta(carregar_config(config))
    imgs = acervo.listar(pasta)
    typer.echo(f"Acervo: {pasta}")
    if not imgs:
        typer.echo("  (vazio) copie GeoTIFFs para esta pasta")
    for img in imgs:
        d = acervo.descrever(img.caminho)
        gsd = f"{100 * d['gsd_m']:.1f} cm" if d["gsd_m"] else "graus"
        pista = img.pista.name if img.pista else "SEM PISTA"
        typer.echo(f"  {img.caminho.name}  {d['largura_px']}x{d['altura_px']}  {gsd}  {pista}")


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
