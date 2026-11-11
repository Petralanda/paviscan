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
    """Com tiles de 512 px muitos buracos cruzam borda de tile: o resultado tem que ser o mesmo."""
    import geopandas as gpd
    import yaml

    from paviscan.pipeline import carregar_config

    params = carregar_config()
    params["tiles"] = {"tamanho_px": 512, "sobreposicao_px": 128}
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
