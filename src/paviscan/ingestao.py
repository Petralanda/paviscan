"""Abertura da ortofoto: SRC, GSD, reprojecao para UTM e leitura em janelas."""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling, transform_bounds
from rasterio.windows import Window

# Brasil (com folga): usa SIRGAS 2000 em vez de WGS 84
_BRASIL = (-75.0, -35.0, -28.0, 6.0)


def zona_utm(lon: float, lat: float) -> CRS:
    """SRC UTM da zona que contem (lon, lat). SIRGAS 2000 dentro do Brasil."""
    zona = int(math.floor((lon + 180) / 6)) + 1
    sul = lat < 0
    lo, la, hi, ha = _BRASIL
    if lo <= lon <= hi and la <= lat <= ha:
        if sul and 18 <= zona <= 25:
            return CRS.from_epsg(31960 + zona)
        if not sul and 17 <= zona <= 22:
            return CRS.from_epsg(31954 + zona)
    return CRS.from_epsg((32700 if sul else 32600) + zona)


@contextmanager
def abrir(orto: Path) -> Iterator[rasterio.io.DatasetReaderBase]:
    """Abre a ortofoto em SRC projetado. Se estiver em graus, devolve um WarpedVRT em UTM."""
    with rasterio.open(orto) as src:
        if src.crs is None:
            raise ValueError(f"{orto}: ortofoto sem SRC")
        if CRS.from_user_input(src.crs).is_projected:
            yield src
            return
        o, s, l_, n = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
        destino = zona_utm((o + l_) / 2, (s + n) / 2)
        with WarpedVRT(src, crs=destino, resampling=Resampling.bilinear) as vrt:
            yield vrt


def gsd_m(ds) -> float:
    """Tamanho do pixel em metros (media dos dois eixos)."""
    rx, ry = ds.res
    return float((abs(rx) + abs(ry)) / 2)


def janelas(
    largura: int,
    altura: int,
    tamanho: int,
    sobreposicao: int,
    limite: Window | None = None,
) -> Iterator[tuple[Window, Window]]:
    """Gera (externa, interna): internas cobrem `limite` sem sobreposicao, externas somam borda."""
    lim = limite or Window(0, 0, largura, altura)
    c0, l0 = max(0, int(lim.col_off)), max(0, int(lim.row_off))
    c1 = min(largura, int(math.ceil(lim.col_off + lim.width)))
    l1 = min(altura, int(math.ceil(lim.row_off + lim.height)))
    passo = max(1, tamanho - 2 * sobreposicao)
    for lin in range(l0, l1, passo):
        for col in range(c0, c1, passo):
            interna = Window(col, lin, min(passo, c1 - col), min(passo, l1 - lin))
            ec0, el0 = max(0, col - sobreposicao), max(0, lin - sobreposicao)
            ec1 = min(largura, col + interna.width + sobreposicao)
            el1 = min(altura, lin + interna.height + sobreposicao)
            yield Window(ec0, el0, ec1 - ec0, el1 - el0), interna


def _para_uint8(a: np.ndarray) -> np.ndarray:
    if a.dtype == np.uint8:
        return a
    if a.dtype == np.uint16:
        return (a >> 8).astype(np.uint8)
    return np.clip(a, 0, 255).astype(np.uint8)


def ler_rgb(ds, janela: Window) -> tuple[np.ndarray, np.ndarray]:
    """Le uma janela como RGB uint8 HxWx3 e a mascara de dado valido (bool HxW)."""
    n = ds.count
    bandas = [1, 1, 1] if n < 3 else [1, 2, 3]
    arr = ds.read(bandas, window=janela, boundless=False)
    rgb = _para_uint8(np.moveaxis(arr, 0, -1))
    valido = ds.dataset_mask(window=janela) > 0
    return np.ascontiguousarray(rgb), valido
