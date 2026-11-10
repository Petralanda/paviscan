"""M4: serie temporal e dashboard."""

import json
import os
from pathlib import Path

import pytest

import paviscan
from paviscan import sintetico

COLUNAS = (
    "data",
    "id",
    "id_persistente",
    "status",
    "area_m2",
    "area_corte_m2",
    "confianca",
    "segmento",
    "custo_A",
    "custo_B",
)


@pytest.fixture(scope="module")
def serie(tmp_path_factory):
    from paviscan.pipeline import processar_serie

    base = tmp_path_factory.mktemp("serie")
    cenas = sintetico.gerar_serie(base / "cenas", n_datas=4, seed=5)
    saida = processar_serie(cenas, base / "runs")
    return base / "cenas", saida


def test_serie_gravada(serie):
    cenas, saida = serie
    assert (saida / "serie.geojson").exists()
    esperado = json.loads((cenas / "esperado.json").read_text())
    for data in esperado:
        assert (saida / data / "defeitos.geojson").exists(), data


def test_carregar_e_colunas(serie):
    from paviscan.painel.dados import carregar

    df = carregar(serie[1])
    for c in COLUNAS:
        assert c in df.columns, c
    assert df["data"].nunique() == 4
    assert set(df["status"]) <= {"inicial", "novo", "cresceu", "estavel", "reparado"}
    primeira = df[df["data"] == df["data"].min()]
    assert (primeira["status"] == "inicial").all()


def test_id_persistente_acompanha_o_buraco(serie):
    from paviscan.painel.dados import carregar

    df = carregar(serie[1])
    ativos = df[df["status"] != "reparado"]
    datas_por_buraco = ativos.groupby("id_persistente")["data"].nunique()
    assert datas_por_buraco.max() >= 3, "nenhum buraco foi acompanhado ao longo do tempo"
    assert not ativos.duplicated(["data", "id_persistente"]).any()


def test_filtros(serie):
    from paviscan.painel.dados import carregar, filtrar

    df = carregar(serie[1])
    datas = sorted(df["data"].unique())
    f = filtrar(df, data_ini=datas[1], data_fim=datas[2])
    assert set(f["data"].unique()) == {datas[1], datas[2]}
    f = filtrar(df, status=["novo"])
    assert len(f) > 0 and (f["status"] == "novo").all()
    f = filtrar(df, area_min=0.5)
    assert (f["area_m2"] >= 0.5).all()
    assert len(filtrar(df)) == len(df)


def test_area_cresce_no_tempo(serie):
    from paviscan.painel.dados import carregar

    df = carregar(serie[1])
    df = df[df["status"] != "reparado"]
    por_data = df.groupby("data")["area_m2"].sum().sort_index()
    assert por_data.iloc[-1] > por_data.iloc[0]


def test_app_abre_sem_erro(serie):
    from streamlit.testing.v1 import AppTest

    os.environ["PAVISCAN_RUNS"] = str(serie[1])
    app = Path(paviscan.__file__).parent / "painel" / "app.py"
    at = AppTest.from_file(str(app), default_timeout=120).run()
    assert not at.exception, at.exception
    assert len(at.sidebar) > 0, "dashboard sem filtros na barra lateral"
