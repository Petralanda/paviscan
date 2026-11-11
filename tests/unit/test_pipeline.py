import numpy as np
import pytest
import rasterio
from typer.testing import CliRunner

from paviscan import sintetico
from paviscan.cli import app
from paviscan.pipeline import processar


@pytest.fixture(scope="module")
def cena(tmp_path_factory):
    return sintetico.gerar_cena(tmp_path_factory.mktemp("cena"), n_buracos=3, seed=5)


def test_recorte_da_pista(cena, tmp_path):
    out = processar(cena / "orto.tif", cena / "pista.geojson", tmp_path / "run")
    with rasterio.open(out / "pista_recorte.tif") as r:
        assert r.crs.to_epsg() == 31980
        assert abs(r.res[0] - 0.02) < 1e-9
        m = r.dataset_mask() > 0
        area = m.sum() * r.res[0] * r.res[1]
        assert abs(area - 60 * 7) < 1.0  # pista de 60 x 7 m
        assert np.all(r.read(1)[~m] == 0)


def test_cli_run(cena, tmp_path):
    res = CliRunner().invoke(
        app,
        [
            "run",
            "--orto",
            str(cena / "orto.tif"),
            "--pista",
            str(cena / "pista.geojson"),
            "--saida",
            str(tmp_path / "r"),
        ],
    )
    assert res.exit_code == 0, res.output
    assert (tmp_path / "r" / "pista_recorte.tif").exists()


def test_tiles_pequenos_nao_duplicam_nem_cortam_buraco(cena, tmp_path):
    """Com tiles pequenos muitos buracos cruzam borda de tile: o resultado tem que ser o mesmo."""
    import geopandas as gpd
    import yaml

    from paviscan.pipeline import carregar_config

    params = carregar_config()
    params["tiles"] = {"tamanho_px": 512, "sobreposicao_m": 2.5}
    cfg = tmp_path / "p.yaml"
    cfg.write_text(yaml.safe_dump(params))
    a = gpd.read_file(
        processar(cena / "orto.tif", cena / "pista.geojson", tmp_path / "a") / "defeitos.geojson"
    )
    b = gpd.read_file(
        processar(cena / "orto.tif", cena / "pista.geojson", tmp_path / "b", cfg)
        / "defeitos.geojson"
    )
    assert len(a) == len(b) == 3
    assert sorted(a["area_m2"].round(2)) == sorted(b["area_m2"].round(2))


def test_gsd_fino_buraco_na_fronteira_do_tile(tmp_path):
    """A 0,5 cm, um buraco de 0,9 m de raio bem na fronteira do miolo sai inteiro e uma vez so."""
    import geopandas as gpd
    from rasterio.transform import from_origin
    from shapely.geometry import box

    from paviscan.pipeline import carregar_config, tiles_em_px

    gsd = 0.005
    tam, sob = tiles_em_px(carregar_config(), gsd)
    assert sob * gsd >= 2.5 and tam - 2 * sob >= tam / 2
    h, w = int(5 / gsd), int(12 / gsd)
    x0, y0 = 830000.0, 9660000.0
    img = 95 + 4 * np.random.default_rng(0).standard_normal((h, w))
    cx, cy = tam - 2 * sob, h // 2  # fronteira entre o miolo do 1o e do 2o tile
    yy, xx = np.mgrid[0:h, 0:w]
    img[(xx - cx) ** 2 + (yy - cy) ** 2 <= (0.9 / gsd) ** 2] -= 50
    rgb = np.clip(np.stack([img] * 3), 0, 255).astype(np.uint8)
    d = tmp_path / "c"
    d.mkdir()
    perfil = dict(driver="GTiff", width=w, height=h, count=3, dtype="uint8", crs="EPSG:31980")
    with rasterio.open(d / "o.tif", "w", transform=from_origin(x0, y0, gsd, gsd), **perfil) as ds:
        ds.write(rgb)
    gpd.GeoDataFrame(geometry=[box(x0, y0 - 5, x0 + 12, y0)], crs="EPSG:31980").to_file(
        d / "p.geojson"
    )
    det = gpd.read_file(
        processar(d / "o.tif", d / "p.geojson", tmp_path / "r") / "defeitos.geojson"
    )
    assert len(det) == 1
    assert abs(det["area_m2"].iloc[0] - np.pi * 0.81) < 0.1
