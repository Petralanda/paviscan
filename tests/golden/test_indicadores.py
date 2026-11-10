"""M3: severidade, segmentos e resumo fecham entre si."""

import json

import geopandas as gpd


def test_arquivos(saida_cena):
    for nome in ("defeitos.geojson", "segmentos.geojson", "resumo.json", "previa.png"):
        assert (saida_cena / nome).exists(), nome


def test_severidade_e_segmento(saida_cena):
    det = gpd.read_file(saida_cena / "defeitos.geojson")
    seg = gpd.read_file(saida_cena / "segmentos.geojson")
    assert set(det["severidade"]) <= {"baixa", "media", "alta"}
    assert set(det["segmento"]) <= set(seg["segmento"])
    ordem = {"baixa": 0, "media": 1, "alta": 2}
    d = det.sort_values("area_m2")
    assert d["severidade"].map(ordem).is_monotonic_increasing


def test_segmentos_cobrem_a_pista(cena, saida_cena):
    seg = gpd.read_file(saida_cena / "segmentos.geojson")
    pista = gpd.read_file(cena / "pista.geojson")
    assert seg.crs.is_projected
    assert len(seg) == 3  # 60 m de pista em segmentos de 20 m
    assert abs(seg["area_pista_m2"].sum() - pista.geometry.area.sum()) < 1.0
    assert abs(seg.geometry.area.sum() - pista.geometry.area.sum()) < 1.0


def test_agregacao_bate(saida_cena):
    det = gpd.read_file(saida_cena / "defeitos.geojson")
    seg = gpd.read_file(saida_cena / "segmentos.geojson").set_index("segmento")
    assert seg["n_buracos"].sum() == len(det)
    por_seg = det.groupby("segmento")["area_m2"].sum()
    for s, linha in seg.iterrows():
        esperado = float(por_seg.get(s, 0.0))
        assert abs(linha["area_buracos_m2"] - esperado) < 0.01
        assert abs(linha["pct_afetada"] - 100 * esperado / linha["area_pista_m2"]) < 0.05


def test_resumo(saida_cena):
    r = json.loads((saida_cena / "resumo.json").read_text())
    det = gpd.read_file(saida_cena / "defeitos.geojson")
    assert abs(r["gsd_m"] - 0.02) < 1e-6
    assert r["n_defeitos"] == len(det)
    assert abs(r["area_total_m2"] - det["area_m2"].sum()) < 0.01
    assert abs(r["pct_afetada"] - 100 * r["area_total_m2"] / r["area_pista_m2"]) < 0.05
    (lat_s, lon_o), (lat_n, lon_l) = r["previa_limites"]
    assert -90 <= lat_s < lat_n <= 90 and -180 <= lon_o < lon_l <= 180
    assert r["detector"] and r["versao"]
