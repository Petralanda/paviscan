import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.windows import Window

from paviscan.ingestao import abrir, gsd_m, janelas, ler_rgb, zona_utm


def test_zona_utm_manaus_e_europa():
    assert zona_utm(-60.02, -3.1).to_epsg() == 31980  # SIRGAS 2000 / UTM 20S
    assert zona_utm(-46.6, -23.5).to_epsg() == 31983  # Sao Paulo, 23S
    assert zona_utm(2.35, 48.85).to_epsg() == 32631  # Paris, WGS 84 / 31N


def test_janelas_internas_cobrem_sem_sobreposicao():
    cont = np.zeros((500, 700), int)
    for ext, inn in janelas(700, 500, tamanho=256, sobreposicao=32):
        c, r = int(inn.col_off), int(inn.row_off)
        cont[r : r + int(inn.height), c : c + int(inn.width)] += 1
        assert ext.col_off <= inn.col_off and ext.row_off <= inn.row_off
        assert ext.width <= 256 and ext.height <= 256
    assert (cont == 1).all()


def test_janelas_respeitam_limite():
    lim = Window(100, 50, 200, 80)
    ws = list(janelas(700, 500, 256, 32, limite=lim))
    area = sum(int(i.width) * int(i.height) for _, i in ws)
    assert area == 200 * 80


def _gravar(caminho, crs, tf, dados, **extra):
    perfil = dict(
        driver="GTiff",
        count=dados.shape[0],
        dtype=dados.dtype,
        height=dados.shape[1],
        width=dados.shape[2],
        crs=crs,
        transform=tf,
        **extra,
    )
    with rasterio.open(caminho, "w", **perfil) as dst:
        dst.write(dados)


def test_projetado_gsd_e_nodata(tmp_path):
    dados = np.full((3, 40, 60), 100, np.uint8)
    dados[:, :10, :] = 0
    p = tmp_path / "a.tif"
    _gravar(p, "EPSG:31980", from_origin(830000, 9660000, 0.02, 0.02), dados, nodata=0)
    with abrir(p) as ds:
        assert abs(gsd_m(ds) - 0.02) < 1e-12
        rgb, valido = ler_rgb(ds, Window(0, 0, 60, 40))
    assert rgb.shape == (40, 60, 3) and rgb.dtype == np.uint8
    assert not valido[:10].any() and valido[10:].all()


def test_geografico_vira_utm(tmp_path):
    dados = np.full((3, 50, 50), 120, np.uint8)
    p = tmp_path / "g.tif"
    _gravar(p, "EPSG:4326", from_origin(-60.02, -3.0, 2e-7, 2e-7), dados)
    with abrir(p) as ds:
        assert ds.crs.to_epsg() == 31980
        assert 0.01 < gsd_m(ds) < 0.05  # ~2,2 cm


def test_precisa_reprojetar():
    from paviscan.ingestao import precisa_reprojetar

    assert not precisa_reprojetar("EPSG:31980")  # UTM: mede
    assert precisa_reprojetar("EPSG:4326")  # graus
    assert precisa_reprojetar("EPSG:3857")  # Web Mercator: escala varia com a latitude
    assert precisa_reprojetar("EPSG:2263")  # pes (NY State Plane)


def test_web_mercator_vira_utm_e_area_certa(tmp_path):
    from rasterio.warp import transform

    xs, ys = transform("EPSG:31983", "EPSG:3857", [330000], [7400000])  # Sao Paulo
    dados = np.full((3, 200, 200), 120, np.uint8)
    p = tmp_path / "m.tif"
    _gravar(p, "EPSG:3857", from_origin(xs[0], ys[0], 0.02, 0.02), dados)
    with abrir(p) as ds:
        assert ds.crs.to_epsg() == 31983
        lado = 200 * 0.02 * 0.917  # 1 m em 3857 vale cos(23,5 graus) m no terreno
        assert abs(gsd_m(ds) * max(ds.width, ds.height) - lado) < 0.3
        valido = ds.dataset_mask() > 0  # VRT com alfa: canto rotacionado sem dado e invalido
        assert 0.8 * lado**2 < valido.sum() * gsd_m(ds) ** 2 < 1.1 * lado**2


def test_uint16_esticado(tmp_path):
    from paviscan.ingestao import escala

    rng = np.random.default_rng(0)
    dados = rng.integers(1000, 4000, (3, 64, 64)).astype(np.uint16)  # 12 bits
    p = tmp_path / "u.tif"
    _gravar(p, "EPSG:31980", from_origin(830000, 9660000, 0.02, 0.02), dados)
    with abrir(p) as ds:
        esc = escala(ds)
        rgb, _ = ler_rgb(ds, Window(0, 0, 64, 64), esc)
    assert esc is not None and rgb.dtype == np.uint8
    assert rgb.min() < 10 and rgb.max() > 245
