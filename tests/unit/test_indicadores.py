import geopandas as gpd
import pytest
from shapely.geometry import box

from paviscan import indicadores, pista

CRS = "EPSG:31980"


@pytest.fixture
def segs():
    return pista.segmentos(box(0, 0, 60, 7), 20, CRS)


def _defeitos(polis):
    areas = [p.area for p in polis]
    return gpd.GeoDataFrame({"id": range(len(polis)), "area_m2": areas}, geometry=polis, crs=CRS)


def test_segmento_pelo_centroide(segs):
    d = _defeitos([box(1, 1, 2, 2), box(19.5, 1, 21.5, 2), box(55, 3, 56, 4)])
    out = indicadores.atribuir_segmento(d, segs)
    assert out["segmento"].tolist() == [0, 1, 2]  # o do meio tem centroide em x = 20,5


def test_agregar_e_resumo_batem(segs):
    d = indicadores.atribuir_segmento(_defeitos([box(1, 1, 2, 2), box(3, 3, 4, 3.5)]), segs)
    s = indicadores.agregar(d, segs)
    assert s["n_buracos"].tolist() == [2, 0, 0]
    assert s["area_buracos_m2"].tolist() == pytest.approx([1.5, 0, 0])
    assert s["pct_afetada"].iloc[0] == pytest.approx(100 * 1.5 / 140)
    r = indicadores.resumo(d, s, 0.02, "classico", "0.1.0", [[-3.0, -60.1], [-2.9, -60.0]])
    assert r["n_defeitos"] == 2 and r["area_pista_m2"] == pytest.approx(420)
    assert r["pct_afetada"] == pytest.approx(100 * 1.5 / 420)
    assert r["comprimento_m"] == pytest.approx(60)


def test_sem_buraco(segs):
    vazio = gpd.GeoDataFrame({"id": [], "area_m2": []}, geometry=[], crs=CRS)
    d = indicadores.atribuir_segmento(vazio, segs)
    s = indicadores.agregar(d, segs)
    assert s["n_buracos"].sum() == 0 and (s["pct_afetada"] == 0).all()
    r = indicadores.resumo(d, s, 0.02, "classico", "0.1.0", [[0, 0], [1, 1]])
    assert r["n_defeitos"] == 0 and r["area_total_m2"] == 0 and r["pct_afetada"] == 0
