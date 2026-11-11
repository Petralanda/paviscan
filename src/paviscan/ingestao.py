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


def precisa_reprojetar(crs) -> bool:
    """True se o SRC nao serve para medir: geografico, unidade diferente de metro ou Mercator
    (Web Mercator incluido), cuja escala varia com a latitude. UTM (transversa) serve."""
    c = CRS.from_user_input(crs)
    if not c.is_projected:
        return True
    unidade = (c.axis_info[0].unit_name or "").lower() if c.axis_info else ""
    if unidade not in ("metre", "meter", "metro"):
        return True
    metodo = (c.coordinate_operation.method_name if c.coordinate_operation else "").lower()
    return "mercator" in metodo and "transverse" not in metodo


@contextmanager
def abrir(orto: Path) -> Iterator[rasterio.io.DatasetReaderBase]:
    """Abre a ortofoto em SRC projetado em metros. Se nao estiver, devolve um WarpedVRT em UTM
    com canal alfa, para a area sem dado nao virar pista."""
    with rasterio.open(orto) as src:
        if src.crs is None:
            raise ValueError(f"{orto}: ortofoto sem SRC")
        if not precisa_reprojetar(src.crs):
            yield src
            return
        o, s, l_, n = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
        destino = zona_utm((o + l_) / 2, (s + n) / 2)
        with WarpedVRT(src, crs=destino, resampling=Resampling.bilinear, add_alpha=True) as vrt:
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
    if tamanho <= 2 * sobreposicao:
        raise ValueError(f"tile de {tamanho} px nao comporta sobreposicao de {sobreposicao} px")
    passo = tamanho - 2 * sobreposicao
    for lin in range(l0, l1, passo):
        for col in range(c0, c1, passo):
            interna = Window(col, lin, min(passo, c1 - col), min(passo, l1 - lin))
            ec0, el0 = max(0, col - sobreposicao), max(0, lin - sobreposicao)
            ec1 = min(largura, col + interna.width + sobreposicao)
            el1 = min(altura, lin + interna.height + sobreposicao)
            yield Window(ec0, el0, ec1 - ec0, el1 - el0), interna


def escala(ds, lado_px: int = 1024) -> tuple[float, float] | None:
    """(lo, hi) para levar a ortofoto a 0-255: percentis 0,5 e 99,5 de uma leitura reduzida.

    None quando ja e uint8. Calculada uma vez para o levantamento todo, nao por janela.
    """
    if ds.dtypes[0] == "uint8":
        return None
    f = max(1.0, max(ds.width, ds.height) / lado_px)
    forma = (min(ds.count, 3), max(1, int(ds.height / f)), max(1, int(ds.width / f)))
    a = ds.read(list(range(1, forma[0] + 1)), out_shape=forma, masked=True)
    v = a.compressed() if np.ma.isMaskedArray(a) else a.ravel()
    v = v[np.isfinite(v)]
    if v.size == 0:
        return None
    lo, hi = np.percentile(v, [0.5, 99.5])
    return float(lo), float(max(hi, lo + 1e-6))


def para_uint8(a: np.ndarray, esc: tuple[float, float] | None = None) -> np.ndarray:
    """Converte para uint8. Com `esc`, estica (lo, hi) linearmente para 0-255."""
    if esc is None:
        if a.dtype == np.uint8:
            return a
        return np.clip(a, 0, 255).astype(np.uint8)
    lo, hi = esc
    b = (a.astype(np.float32) - lo) * (255.0 / (hi - lo))
    return np.clip(np.nan_to_num(b), 0, 255).astype(np.uint8)


def ler_rgb(
    ds, janela: Window, esc: tuple[float, float] | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Le uma janela como RGB uint8 HxWx3 e a mascara de dado valido (bool HxW)."""
    n = ds.count
    bandas = [1, 1, 1] if n < 3 else [1, 2, 3]
    arr = ds.read(bandas, window=janela, boundless=False)
    rgb = para_uint8(np.moveaxis(arr, 0, -1), esc)
    valido = ds.dataset_mask(window=janela) > 0
    return np.ascontiguousarray(rgb), valido
