"""M2: buracos no lugar certo e com a area certa."""

import json

import geopandas as gpd
import numpy as np

from .conftest import casar


def test_saidas_existem(saida_cena):
    for nome in ("defeitos.geojson", "resumo.json"):
        assert (saida_cena / nome).exists(), nome


def test_src_projetado_e_colunas(saida_cena):
    det = gpd.read_file(saida_cena / "defeitos.geojson")
    assert det.crs is not None and det.crs.is_projected
    for col in ("id", "area_m2", "area_corte_m2", "confianca"):
        assert col in det.columns, col
    assert np.allclose(det["area_m2"], det.geometry.area, rtol=0.02)
    assert (det["area_corte_m2"] >= det["area_m2"]).all()


def test_recall_e_falsos_positivos(cena, saida_cena):
    det = gpd.read_file(saida_cena / "defeitos.geojson")
    gab = gpd.read_file(cena / "gabarito.geojson")
    pares = casar(det, gab)
    assert len(pares) / len(gab) >= 0.75, f"recall {len(pares)}/{len(gab)}"
    assert len(det) - len(pares) <= 2, f"{len(det) - len(pares)} falsos positivos"


def test_erro_de_area(cena, saida_cena):
    det = gpd.read_file(saida_cena / "defeitos.geojson")
    gab = gpd.read_file(cena / "gabarito.geojson")
    erros = [
        abs(det.geometry[i].area - gab.geometry[j].area) / gab.geometry[j].area
        for i, j in casar(det, gab)
    ]
    assert erros and float(np.median(erros)) <= 0.25, f"erro mediano {np.median(erros):.2f}"


def test_resumo(cena, saida_cena):
    r = json.loads((saida_cena / "resumo.json").read_text())
    assert abs(r["gsd_m"] - 0.02) < 1e-6
    det = gpd.read_file(saida_cena / "defeitos.geojson")
    assert r["n_defeitos"] == len(det)
    assert abs(r["area_total_m2"] - det["area_m2"].sum()) < 0.01
