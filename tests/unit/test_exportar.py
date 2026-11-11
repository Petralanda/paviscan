import json

import cv2
import geopandas as gpd
import numpy as np
import pandas as pd
import pytest

from paviscan import sintetico
from paviscan.pipeline import processar


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    cena = sintetico.gerar_cena(tmp_path_factory.mktemp("cena"), n_buracos=4, seed=9)
    return processar(cena / "orto.tif", cena / "pista.geojson", tmp_path_factory.mktemp("run"))


def test_gpkg_com_duas_camadas(run):
    d = gpd.read_file(run / "defeitos.gpkg", layer="defeitos")
    s = gpd.read_file(run / "defeitos.gpkg", layer="segmentos")
    assert len(d) == len(gpd.read_file(run / "defeitos.geojson"))
    assert len(s) == 3 and d.crs.to_epsg() == 31980


def test_xlsx_com_tres_abas(run):
    abas = pd.read_excel(run / "resumo.xlsx", sheet_name=None)
    assert set(abas) == {"Resumo", "Buracos", "Segmentos"}
    assert len(abas["Segmentos"]) == 3
    assert {"area_m2", "severidade", "segmento", "x_centroide"} <= set(abas["Buracos"].columns)


def test_previa_reduzida_e_limites(run):
    img = cv2.imdecode(np.frombuffer((run / "previa.png").read_bytes(), np.uint8), -1)
    assert img.shape[2] == 4 and max(img.shape[:2]) <= 4000
    assert img.shape[1] < 3500  # 70 m de largura a 2 cm seriam 3500 px: tem que ter reduzido
    r = json.loads((run / "resumo.json").read_text(encoding="utf-8"))
    (lat_s, lon_o), (lat_n, lon_l) = r["previa_limites"]
    assert -4 < lat_s < lat_n < 0 and -63 < lon_o < lon_l < -57  # Manaus
