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


@pytest.mark.parametrize("gsd", [0.005, 0.02])
@pytest.mark.parametrize("eixo", ["coluna", "linha"])
@pytest.mark.parametrize("raio,desloc", [(0.9, 0.0), (1.6, 0.0), (1.6, -0.8), (1.6, 0.8)])
def test_buraco_na_fronteira_do_tile_sai_uma_vez(tmp_path, gsd, eixo, raio, desloc):
    """Buraco cruzando a fronteira entre miolos: uma deteccao so, com a area inteira."""
    import geopandas as gpd
    from rasterio.transform import from_origin
    from shapely.geometry import box

    from paviscan.pipeline import carregar_config, tiles_em_px

    tam, sob = tiles_em_px(carregar_config(), gsd)
    passo = tam - 2 * sob
    lado = passo + int(round(4.0 / gsd))  # um miolo inteiro e mais 4 m: cabe a fronteira
    rng = np.random.default_rng(0)
    img = 95 + 4 * rng.standard_normal((lado, lado))
    fronteira = passo + desloc * raio / gsd
    meio = passo / 2
    cx, cy = (fronteira, meio) if eixo == "coluna" else (meio, fronteira)
    yy, xx = np.mgrid[0:lado, 0:lado]
    img[(xx - cx) ** 2 + (yy - cy) ** 2 <= (raio / gsd) ** 2] -= 50
    rgb = np.clip(np.stack([img] * 3), 0, 255).astype(np.uint8)
    x0, y0, m = 830000.0, 9660000.0, lado * gsd
    perfil = dict(driver="GTiff", width=lado, height=lado, count=3, dtype="uint8")
    tf = from_origin(x0, y0, gsd, gsd)
    with rasterio.open(tmp_path / "o.tif", "w", crs="EPSG:31980", transform=tf, **perfil) as ds:
        ds.write(rgb)
    gpd.GeoDataFrame(geometry=[box(x0, y0 - m, x0 + m, y0)], crs="EPSG:31980").to_file(
        tmp_path / "p.geojson"
    )
    out = processar(tmp_path / "o.tif", tmp_path / "p.geojson", tmp_path / "r")
    det = gpd.read_file(out / "defeitos.geojson")
    assert len(det) == 1, list(det["area_m2"].round(2))
    assert abs(det["area_m2"].iloc[0] - np.pi * raio**2) / (np.pi * raio**2) < 0.05
