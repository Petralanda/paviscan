"""M4: dados e filtros do dashboard."""

import os
from pathlib import Path

import paviscan


def test_carregar(saida_cena):
    from paviscan.painel.dados import carregar

    det, seg, resumo = carregar(saida_cena)
    assert len(det) == resumo["n_defeitos"]
    assert "pct_afetada" in seg.columns


def test_filtros(saida_cena):
    from paviscan.painel.dados import carregar, filtrar

    det, _, _ = carregar(saida_cena)
    assert len(filtrar(det)) == len(det)

    corte = float(det["area_m2"].median())
    f = filtrar(det, area_min=corte)
    assert 0 < len(f) < len(det) and (f["area_m2"] >= corte).all()
    f = filtrar(det, area_max=corte)
    assert (f["area_m2"] <= corte).all()

    sev = det["severidade"].iloc[0]
    f = filtrar(det, severidade=[sev])
    assert len(f) > 0 and (f["severidade"] == sev).all()

    s = int(det["segmento"].iloc[0])
    f = filtrar(det, segmentos=[s])
    assert len(f) > 0 and (f["segmento"] == s).all()

    assert (filtrar(det, confianca_min=0.5)["confianca"] >= 0.5).all()
    assert len(filtrar(det, area_min=1e9)) == 0


def test_resumir(saida_cena):
    from paviscan.painel.dados import carregar, filtrar, resumir

    det, seg, _ = carregar(saida_cena)
    r = resumir(det, seg)
    assert r["n_buracos"] == len(det)
    assert abs(r["area_total_m2"] - det["area_m2"].sum()) < 0.01
    assert abs(r["pct_afetada"] - 100 * det["area_m2"].sum() / seg["area_pista_m2"].sum()) < 0.05
    assert abs(r["buracos_por_100m"] - len(det) / 60 * 100) < 0.5
    assert abs(r["maior_buraco_m2"] - det["area_m2"].max()) < 0.01

    vazio = resumir(filtrar(det, area_min=1e9), seg)
    assert vazio["n_buracos"] == 0 and vazio["area_total_m2"] == 0


def test_app_abre_sem_erro(saida_cena):
    from streamlit.testing.v1 import AppTest

    os.environ["PAVISCAN_RUNS"] = str(saida_cena.parent)
    app = Path(paviscan.__file__).parent / "painel" / "app.py"
    at = AppTest.from_file(str(app), default_timeout=120).run()
    assert not at.exception, at.exception
    assert len(at.sidebar) > 0, "dashboard sem filtros na barra lateral"
    assert len(at.metric) >= 3, "dashboard sem indicadores"
