"""M4: antes e depois do mesmo trecho."""

import json

import geopandas as gpd


def test_comparacao(par, tmp_path):
    from paviscan.pipeline import comparar, processar

    antes, depois = par
    ra = processar(antes / "orto.tif", antes / "pista.geojson", tmp_path / "a")
    rd = processar(depois / "orto.tif", depois / "pista.geojson", tmp_path / "d")
    out = comparar(ra, rd, tmp_path / "comp")

    esp = json.loads((depois / "esperado.json").read_text())
    c = json.loads((out / "comparacao.json").read_text())
    assert abs(c["novos"] - esp["novos"]) <= 1
    assert abs(c["reparados"] - esp["reparados"]) <= 1
    assert c["cresceram"] >= esp["cresceram"] - 2
    assert c["delta_area_m2"] > 0

    g = gpd.read_file(out / "comparacao.geojson")
    assert set(g["status"]) <= {"novo", "cresceu", "estavel", "reparado"}
