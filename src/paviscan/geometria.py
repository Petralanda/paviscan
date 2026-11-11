"""Mascara -> poligono em UTM, com area, largura, comprimento e severidade."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
from rasterio.features import shapes
from shapely.geometry import Polygon, shape

COLUNAS = ["id", "area_m2", "largura_m", "comprimento_m", "confianca", "severidade"]


def vetorizar(mascara: np.ndarray, transform, gsd_m: float) -> Polygon | None:
    """Maior poligono da mascara, simplificado com tolerancia de meio pixel."""
    m = mascara.astype(np.uint8)
    polis = [shape(g) for g, v in shapes(m, mask=m.astype(bool), transform=transform) if v == 1]
    if not polis:
        return None
    pol = max(polis, key=lambda g: g.area).simplify(gsd_m / 2, preserve_topology=True)
    return pol if pol.is_valid and not pol.is_empty else pol.buffer(0)


def medidas(pol: Polygon) -> tuple[float, float]:
    """(largura, comprimento): lados menor e maior do retangulo minimo rotacionado."""
    ret = pol.minimum_rotated_rectangle
    if not isinstance(ret, Polygon):
        return 0.0, float(ret.length)
    x, y = np.asarray(ret.exterior.coords)[:3].T
    lados = sorted(
        [float(np.hypot(x[1] - x[0], y[1] - y[0])), float(np.hypot(x[2] - x[1], y[2] - y[1]))]
    )
    return lados[0], lados[1]


def severidade(area_m2: float, params: dict) -> str:
    """Faixa por area, com os limites de params['severidade']."""
    s = params["severidade"]
    if area_m2 >= s["alta_a_partir_de"]:
        return "alta"
    if area_m2 >= s["media_a_partir_de"]:
        return "media"
    return "baixa"


def montar_defeitos(
    poligonos: list[Polygon], confiancas: list[float], crs, params: dict
) -> gpd.GeoDataFrame:
    """GeoDataFrame dos defeitos com as colunas do contrato (menos `segmento`)."""
    linhas = []
    for i, (pol, conf) in enumerate(zip(poligonos, confiancas, strict=True)):
        larg, comp = medidas(pol)
        area = float(pol.area)
        linhas.append(
            dict(
                id=i,
                area_m2=area,
                largura_m=larg,
                comprimento_m=comp,
                confianca=float(np.clip(conf, 0, 1)),
                severidade=severidade(area, params),
                geometry=pol,
            )
        )
    if not linhas:
        return gpd.GeoDataFrame({c: [] for c in COLUNAS}, geometry=[], crs=crs)
    return gpd.GeoDataFrame(linhas, geometry="geometry", crs=crs)
