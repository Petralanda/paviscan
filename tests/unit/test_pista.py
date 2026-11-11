import geopandas as gpd
from rasterio.transform import from_origin
from shapely.geometry import box

from paviscan import pista


def test_carregar_reprojeta_para_o_src_da_orto(tmp_path):
    p = tmp_path / "p.geojson"
    gpd.GeoDataFrame(geometry=[box(830000, 9659000, 830060, 9659007)], crs="EPSG:31980").to_crs(
        "EPSG:4326"
    ).to_file(p)
    geom = pista.carregar(p, "EPSG:31980")
    assert abs(geom.area - 420.0) < 0.5


def test_mascara_quadrado_de_50px_a_2cm_da_1m2():
    tf = from_origin(0.0, 10.0, 0.02, 0.02)
    m = pista.mascara(box(1.0, 8.0, 2.0, 9.0), tf, (500, 500))
    assert m.sum() == 50 * 50
    assert m.sum() * 0.02**2 == 1.0


def test_janela_contem_a_pista_e_corta_no_raster():
    tf = from_origin(0.0, 10.0, 0.02, 0.02)
    w = pista.janela(box(1.0, 8.0, 2.0, 9.0), tf, 500, 500)
    assert w.col_off <= 50 and w.col_off + w.width >= 100
    assert w.row_off <= 50 and w.row_off + w.height >= 100
    w = pista.janela(box(-5.0, 0.0, 50.0, 20.0), tf, 500, 500)
    assert (w.col_off, w.row_off, w.width, w.height) == (0, 0, 500, 500)
