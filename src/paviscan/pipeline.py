"""Orquestra o processamento de uma ortofoto: ingestao, pista e recorte."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import rasterio
import yaml
from rasterio.windows import Window
from rasterio.windows import transform as transform_janela

from paviscan import ingestao, pista

CONFIG_PADRAO = Path(__file__).resolve().parents[2] / "config" / "params.yaml"

Progresso = Callable[[float, str], None]


def carregar_config(config: Path | None = None) -> dict:
    """Le o params.yaml (o do repositorio quando `config` e None)."""
    caminho = Path(config) if config else CONFIG_PADRAO
    return yaml.safe_load(caminho.read_text(encoding="utf-8"))


def _relativa(janela: Window, base: Window) -> Window:
    return Window(
        janela.col_off - base.col_off, janela.row_off - base.row_off, janela.width, janela.height
    )


def gravar_recorte(ds, geom, jan_pista: Window, destino: Path, params: dict) -> None:
    """Grava a ortofoto recortada a pista, janela a janela, com mascara fora da pista."""
    tf = transform_janela(jan_pista, ds.transform)
    perfil = dict(
        driver="GTiff",
        count=3,
        dtype="uint8",
        width=int(jan_pista.width),
        height=int(jan_pista.height),
        crs=ds.crs,
        transform=tf,
        compress="deflate",
        tiled=True,
        blockxsize=256,
        blockysize=256,
    )
    t = params["tiles"]
    with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=True), rasterio.open(destino, "w", **perfil) as dst:
        for _, inn in ingestao.janelas(ds.width, ds.height, t["tamanho_px"], 0, jan_pista):
            rgb, valido = ingestao.ler_rgb(ds, inn)
            m = valido & pista.mascara(geom, transform_janela(inn, ds.transform), valido.shape)
            rgb[~m] = 0
            rel = _relativa(inn, jan_pista)
            dst.write(np.moveaxis(rgb, -1, 0), window=rel)
            dst.write_mask((m * 255).astype(np.uint8), window=rel)


def processar(
    orto: Path,
    pista_path: Path,
    saida: Path,
    config: Path | None = None,
    progresso: Progresso | None = None,
) -> Path:
    """Processa `orto` restrita a `pista_path` e grava os resultados em `saida`."""
    params = carregar_config(config)
    avisar = progresso or (lambda f, msg: None)
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    with ingestao.abrir(Path(orto)) as ds:
        geom = pista.carregar(Path(pista_path), ds.crs)
        jan = pista.janela(geom, ds.transform, ds.width, ds.height)
        avisar(0.1, "recortando a pista")
        gravar_recorte(ds, geom, jan, saida / "pista_recorte.tif", params)
    avisar(1.0, "pronto")
    return saida
