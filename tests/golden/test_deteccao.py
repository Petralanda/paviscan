"""M2: buracos no lugar certo e com a medida certa."""

import geopandas as gpd
import numpy as np

from .conftest import casar


def test_src_projetado_e_colunas(saida_cena):
    det = gpd.read_file(saida_cena / "defeitos.geojson")
    assert det.crs is not None and det.crs.is_projected
    for col in ("id", "area_m2", "largura_m", "comprimento_m", "confianca"):
        assert col in det.columns, col
    assert det["id"].is_unique
    assert np.allclose(det["area_m2"], det.geometry.area, rtol=0.02)
    assert (det["largura_m"] <= det["comprimento_m"] + 1e-9).all()
    assert det["confianca"].between(0, 1).all()


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


def test_pista_sem_buraco_nao_gera_deteccao(tmp_path):
    """Limiar tem que ser robusto: asfalto limpo (com faixa, trinca e sombra) da zero ou quase."""
    from paviscan.pipeline import processar

    from paviscan import sintetico

    limpa = sintetico.gerar_cena(tmp_path / "limpa", n_buracos=0, seed=3)
    out = processar(limpa / "orto.tif", limpa / "pista.geojson", tmp_path / "run")
    det = gpd.read_file(out / "defeitos.geojson")
    assert len(det) <= 1, f"{len(det)} deteccoes em pista sem buraco"
