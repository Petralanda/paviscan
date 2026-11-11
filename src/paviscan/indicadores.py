"""Indicadores por segmento e resumo do levantamento."""

from __future__ import annotations

import geopandas as gpd
import numpy as np


def atribuir_segmento(defeitos: gpd.GeoDataFrame, segmentos: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Coluna `segmento`: segmento que contem o centroide do buraco (o mais proximo, se nenhum)."""
    out = defeitos.copy()
    if out.empty:
        out["segmento"] = np.array([], dtype=int)
        return out
    cent = gpd.GeoDataFrame(geometry=out.geometry.centroid, crs=out.crs)
    junta = gpd.sjoin_nearest(cent, segmentos[["segmento", "geometry"]], how="left")
    junta = junta[~junta.index.duplicated(keep="first")]
    out["segmento"] = junta["segmento"].astype(int).to_numpy()
    return out


def agregar(defeitos: gpd.GeoDataFrame, segmentos: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Por segmento: area_pista_m2, n_buracos, area_buracos_m2, pct_afetada (0 a 100)."""
    seg = segmentos.copy()
    seg["area_pista_m2"] = seg.geometry.area
    grupos = defeitos.groupby("segmento")["area_m2"]
    seg["n_buracos"] = seg["segmento"].map(grupos.size()).fillna(0).astype(int)
    seg["area_buracos_m2"] = seg["segmento"].map(grupos.sum()).fillna(0.0).astype(float)
    seg["pct_afetada"] = 100 * seg["area_buracos_m2"] / seg["area_pista_m2"]
    return seg


def resumo(
    defeitos: gpd.GeoDataFrame,
    segmentos: gpd.GeoDataFrame,
    gsd_m: float,
    detector: str,
    versao: str,
    previa_limites: list[list[float]],
) -> dict:
    """Numeros do levantamento inteiro, para o resumo.json."""
    area_pista = float(segmentos["area_pista_m2"].sum())
    area_total = float(defeitos["area_m2"].sum()) if len(defeitos) else 0.0
    return {
        "gsd_m": float(gsd_m),
        "n_defeitos": int(len(defeitos)),
        "area_total_m2": area_total,
        "area_pista_m2": area_pista,
        "pct_afetada": 100 * area_total / area_pista if area_pista > 0 else 0.0,
        "comprimento_m": float(segmentos["comprimento_m"].sum()),
        "n_segmentos": int(len(segmentos)),
        "src": segmentos.crs.to_string() if segmentos.crs else None,
        "detector": detector,
        "versao": versao,
        "previa_limites": previa_limites,
    }
