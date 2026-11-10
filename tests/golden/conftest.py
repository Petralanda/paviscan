"""Testes de aceite. NAO EDITAR para fazer passar: mude o codigo, nao o gabarito."""

import geopandas as gpd
import pytest

from paviscan import sintetico


@pytest.fixture(scope="session")
def cena(tmp_path_factory):
    return sintetico.gerar_cena(tmp_path_factory.mktemp("cena"), n_buracos=8, seed=7)


@pytest.fixture(scope="session")
def par(tmp_path_factory):
    return sintetico.gerar_par(tmp_path_factory.mktemp("par"), seed=11)


@pytest.fixture(scope="session")
def saida_cena(cena, tmp_path_factory):
    from paviscan.pipeline import processar

    return processar(cena / "orto.tif", cena / "pista.geojson", tmp_path_factory.mktemp("run"))


def casar(det: gpd.GeoDataFrame, gab: gpd.GeoDataFrame, iou_min: float = 0.3):
    """Casa deteccoes e gabarito por IoU. Devolve lista de (i_det, i_gab)."""
    pares, usados = [], set()
    for j, g in enumerate(gab.geometry):
        melhor, melhor_iou = None, iou_min
        for i, d in enumerate(det.geometry):
            if i in usados or not d.intersects(g):
                continue
            iou = d.intersection(g).area / d.union(g).area
            if iou >= melhor_iou:
                melhor, melhor_iou = i, iou
        if melhor is not None:
            usados.add(melhor)
            pares.append((melhor, j))
    return pares
