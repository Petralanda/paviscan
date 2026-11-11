import numpy as np
import pytest
from rasterio.transform import from_origin
from shapely.geometry import box

from paviscan import geometria
from paviscan.pipeline import carregar_config


def test_quadrado_50px_a_2cm_da_1m2():
    m = np.zeros((200, 200), bool)
    m[50:100, 60:110] = True
    pol = geometria.vetorizar(m, from_origin(830000, 9660000, 0.02, 0.02), 0.02)
    assert abs(pol.area - 1.0) < 1e-9
    assert pol.bounds == pytest.approx((830001.2, 9659998.0, 830002.2, 9659999.0))


def test_mascara_vazia():
    assert geometria.vetorizar(np.zeros((10, 10), bool), from_origin(0, 0, 1, 1), 1) is None


def test_medidas_retangulo_girado():
    from shapely import affinity

    pol = affinity.rotate(box(0, 0, 2.0, 0.5), 33)
    larg, comp = geometria.medidas(pol)
    assert larg == pytest.approx(0.5) and comp == pytest.approx(2.0)


def test_severidade_pelos_limites():
    p = carregar_config()
    assert geometria.severidade(0.1, p) == "baixa"
    assert geometria.severidade(0.25, p) == "media"
    assert geometria.severidade(1.0, p) == "alta"


def test_montar_defeitos_colunas_e_vazio():
    p = carregar_config()
    gdf = geometria.montar_defeitos([box(0, 0, 1, 0.5)], [0.7], "EPSG:31980", p)
    assert list(gdf.columns[:-1]) == geometria.COLUNAS
    assert gdf.loc[0, "area_m2"] == pytest.approx(0.5)
    assert gdf.loc[0, "severidade"] == "media"
    vazio = geometria.montar_defeitos([], [], "EPSG:31980", p)
    assert vazio.empty and vazio.crs.to_epsg() == 31980
