"""Poligono da pista: leitura, mascara por janela e janela de leitura."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
from rasterio.features import rasterize
from rasterio.windows import Window, from_bounds
from shapely.geometry import Polygon, mapping
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


def eixo(geom: BaseGeometry) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Eixo maior do retangulo minimo rotacionado: (origem, direcao unitaria, s_min, s_max).

    A direcao aponta para leste (ou para norte, se o eixo for vertical), para a numeracao
    dos segmentos ser deterministica.
    """
    ret = geom.minimum_rotated_rectangle
    xy = np.asarray(ret.exterior.coords)[:4]
    lados = [xy[1] - xy[0], xy[2] - xy[1]]
    u = max(lados, key=lambda v: float(np.hypot(*v)))
    u = u / np.hypot(*u)
    if u[0] < -1e-9 or (abs(u[0]) <= 1e-9 and u[1] < 0):
        u = -u
    s = xy @ u
    return xy[0], u, float(s.min()), float(s.max())


def segmentos(geom: BaseGeometry, comprimento_m: float, crs=None) -> gpd.GeoDataFrame:
    """Corta a pista em faixas de `comprimento_m` ao longo do eixo maior, numeradas de 0.

    Cobre a pista inteira sem sobra nem sobreposicao; o ultimo pedaco absorve o resto.
    """
    _, u, s0, s1 = eixo(geom)
    v = np.array([-u[1], u[0]])
    c = geom.centroid
    t = float(np.array([c.x, c.y]) @ v)  # posicao da pista na direcao transversal
    comp = s1 - s0
    n = max(1, int(np.ceil(comp / comprimento_m - 1e-6)))
    larg = 10 * (comp + 1) + 1e3
    linhas = []
    for i in range(n):
        a = s0 + i * comprimento_m - (larg if i == 0 else 0)
        b = s1 + larg if i == n - 1 else s0 + (i + 1) * comprimento_m
        lo, hi = (t - larg) * v, (t + larg) * v
        faixa = Polygon([a * u + lo, b * u + lo, b * u + hi, a * u + hi])
        pedaco = geom.intersection(faixa)
        ini = i * comprimento_m
        fim = comp if i == n - 1 else (i + 1) * comprimento_m
        linhas.append(
            dict(segmento=i, inicio_m=ini, fim_m=fim, comprimento_m=fim - ini, geometry=pedaco)
        )
    return gpd.GeoDataFrame(linhas, geometry="geometry", crs=crs)
