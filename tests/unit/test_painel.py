import os
from pathlib import Path

import geopandas as gpd
import pytest

import paviscan
from paviscan import sintetico
from paviscan.painel import dados as D
from paviscan.pipeline import processar

APP = str(Path(paviscan.__file__).parent / "painel" / "app.py")


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    base = tmp_path_factory.mktemp("runs")
    cena = sintetico.gerar_cena(tmp_path_factory.mktemp("c"), n_buracos=10, seed=21)
    processar(cena / "orto.tif", cena / "pista.geojson", base / "cheio")
    limpa = sintetico.gerar_cena(tmp_path_factory.mktemp("l"), n_buracos=0, seed=3)
    processar(limpa / "orto.tif", limpa / "pista.geojson", base / "vazio")
    return base


def test_listar_runs(runs, tmp_path):
    assert {p.name for p in D.listar_runs(runs)} == {"cheio", "vazio"}
    assert D.listar_runs(tmp_path / "nao_existe") == []


def test_carregar_vazio_repoe_colunas(runs):
    det, seg, resumo = D.carregar(runs / "vazio")
    assert det.empty and resumo["n_defeitos"] == 0
    assert set(D.TIPOS_DEFEITOS) <= set(det.columns)
    assert len(D.filtrar(det, area_min=0.1, severidade=["alta"], segmentos=[0])) == 0
    r = D.resumir(det, seg)
    assert r["n_buracos"] == 0 and r["maior_buraco_m2"] == 0 and r["buracos_por_100m"] == 0
    assert D.ranking(D.por_segmento(det, seg)).empty
    assert D.tabela(det).empty and D.csv_bytes(det)


def test_por_segmento_e_ranking(runs):
    det, seg, _ = D.carregar(runs / "cheio")
    so_um = D.filtrar(det, segmentos=[int(det["segmento"].iloc[0])])
    s = D.por_segmento(so_um, seg)
    assert s["n_buracos"].sum() == len(so_um)
    assert s["area_pista_m2"].sum() == pytest.approx(seg["area_pista_m2"].sum())
    rk = D.ranking(D.por_segmento(det, seg))
    assert rk["pct_afetada"].is_monotonic_decreasing and (rk["n_buracos"] > 0).all()


def test_exportacoes(runs):
    det, seg, _ = D.carregar(runs / "cheio")
    csv = D.csv_bytes(det).decode("utf-8-sig")
    assert csv.splitlines()[0].startswith("id;area_m2") and len(csv.splitlines()) == len(det) + 1
    assert D.xlsx_bytes(det, seg)[:2] == b"PK"
    import io

    volta = gpd.read_file(io.BytesIO(D.geojson_bytes(det)))
    assert len(volta) == len(det)


def test_fmt_e_vista():
    assert D.fmt(1234.567) == "1.234,57" and D.fmt(0.5, 1) == "0,5"
    v = D.vista_inicial([[-3.0044, -60.0439], [-3.0032, -60.0437]])
    assert 18 < v["zoom"] < 21 and v["latitude"] == pytest.approx(-3.0038)
    assert D.cor_pct(0, 0) == D.cor_pct(0, 5) and D.cor_pct(5, 5) != D.cor_pct(0, 5)


def test_previa_data_uri(runs):
    uri = D.previa_data_uri(runs / "cheio", lado_max=500)
    assert uri.startswith("data:image/png;base64,")


def _metrica(at, rotulo):
    return next(m.value for m in at.metric if m.label == rotulo)


def test_cada_filtro_muda_o_que_aparece(runs):
    from streamlit.testing.v1 import AppTest

    os.environ["PAVISCAN_RUNS"] = str(runs)
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception, at.exception
    at.sidebar.selectbox[0].set_value("cheio").run()
    total = _metrica(at, "Buracos")
    n = int(total)
    assert n >= 8

    at.sidebar.slider[1].set_value(0.95).run()  # confianca minima
    assert "de" in _metrica(at, "Buracos")
    at.sidebar.button[0].click().run()  # limpar
    assert _metrica(at, "Buracos") == total

    at.sidebar.multiselect[0].set_value(["alta"]).run()  # severidade
    so_alta = _metrica(at, "Buracos")
    assert so_alta != total and so_alta.endswith(f"de {n}")
    at.sidebar.button[0].click().run()

    det, _, _ = D.carregar(runs / "cheio")
    s = int(det["segmento"].value_counts().idxmin())
    at.sidebar.multiselect[1].set_value([s]).run()  # segmentos
    esperado = int((det["segmento"] == s).sum())
    assert _metrica(at, "Buracos") == f"{esperado} de {n}"
    at.sidebar.button[0].click().run()

    lo, hi = at.sidebar.slider[0].value  # area
    at.sidebar.slider[0].set_value((lo, (lo + hi) / 2)).run()
    assert _metrica(at, "Buracos").endswith(f"de {n}") and _metrica(at, "Buracos") != total
    assert not at.exception


def test_levantamento_sem_buraco_nao_quebra(runs):
    from streamlit.testing.v1 import AppTest

    os.environ["PAVISCAN_RUNS"] = str(runs)
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.sidebar.selectbox[0].set_value("vazio").run()
    assert not at.exception, at.exception
    assert _metrica(at, "Buracos") == "0"
    assert any("Nenhum buraco" in s.value for s in at.success)


def test_poligonos_mapa_em_lonlat(runs):
    det, seg, _ = D.carregar(runs / "cheio")
    df = D.poligonos_mapa(det)
    assert len(df) == len(det) and "contorno" in df.columns
    lon, lat = df["contorno"].iloc[0][0]
    assert -63 < lon < -57 and -4 < lat < 0
    assert len(D.poligonos_mapa(seg)) >= len(seg)


def test_nome_levantamento_seguro():
    assert D.nome_levantamento("Avenida Ápio Mendes 11/11") == "Avenida_Apio_Mendes_11_11"
    assert D.nome_levantamento("../../etc") == "etc"
    assert D.nome_levantamento("  ") == ""


def test_filtro_de_segmento_usa_so_os_segmentos_escolhidos(runs):
    from streamlit.testing.v1 import AppTest

    os.environ["PAVISCAN_RUNS"] = str(runs)
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.sidebar.selectbox[0].set_value("cheio").run()
    det, seg, _ = D.carregar(runs / "cheio")
    s = int(det["segmento"].iloc[0])
    at.sidebar.multiselect[1].set_value([s]).run()
    so = D.filtrar(det, segmentos=[s])
    esperado = D.resumir(so, seg[seg["segmento"] == s])
    assert _metrica(at, "% da pista afetada") == f"{D.fmt(esperado['pct_afetada'])} %"
    assert _metrica(at, "Buracos por 100 m") == D.fmt(esperado["buracos_por_100m"], 1)
