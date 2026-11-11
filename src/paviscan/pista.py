"""Poligono da pista: leitura, mascara por janela e janela de leitura."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
from rasterio.features import rasterize
from rasterio.windows import Window, from_bounds
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union


def carregar(pista: Path, crs) -> BaseGeometry:
    """Le o poligono da pista e devolve a uniao, ja no SRC `crs` da ortofoto."""
    gdf = gpd.read_file(pista)
    if gdf.empty:
        raise ValueError(f"{pista}: nenhum poligono")
    if gdf.crs is None:
        raise ValueError(f"{pista}: poligono sem SRC")
    geom = unary_union(gdf.to_crs(crs).geometry.make_valid())
    geom = geom.buffer(0)
    if geom.is_empty or geom.area <= 0:
        raise ValueError(f"{pista}: poligono sem area")
    return geom


def janela(geom: BaseGeometry, transform, largura: int, altura: int) -> Window:
    """Janela em pixels que contem a pista, recortada aos limites do raster."""
    w = from_bounds(*geom.bounds, transform=transform).round_offsets().round_lengths()
    c0, l0 = max(0, int(w.col_off)), max(0, int(w.row_off))
    c1 = min(largura, int(w.col_off + w.width) + 1)
    l1 = min(altura, int(w.row_off + w.height) + 1)
    if c1 <= c0 or l1 <= l0:
        raise ValueError("a pista nao cruza a ortofoto")
    return Window(c0, l0, c1 - c0, l1 - l0)


def mascara(geom: BaseGeometry, transform, forma: tuple[int, int]) -> np.ndarray:
    """Mascara bool (True = pista) para uma janela com `transform` e `forma` (altura, largura)."""
    return rasterize([(mapping(geom), 1)], out_shape=forma, transform=transform, fill=0).astype(
        bool
    )
