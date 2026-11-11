import io
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

import paviscan
from paviscan import acervo, sintetico
from paviscan.cli import app


@pytest.fixture(scope="module")
def cena(tmp_path_factory):
    return sintetico.gerar_cena(tmp_path_factory.mktemp("cena"), n_buracos=3, seed=4)


@pytest.fixture
def pasta(cena, tmp_path):
    """Acervo com uma imagem com pista ao lado e uma sem."""
    p = tmp_path / "images"
    p.mkdir()
    shutil.copy(cena / "orto.tif", p / "trecho_a.tif")
    shutil.copy(cena / "pista.geojson", p / "trecho_a.pista.geojson")
    shutil.copy(cena / "orto.tif", p / "TRECHO_B.GeoTIFF")
    (p / "notas.txt").write_text("nao e imagem")
    return p


def test_listar_e_pista_ao_lado(pasta):
    imgs = acervo.listar(pasta)
    assert [i.caminho.name for i in imgs] == ["TRECHO_B.GeoTIFF", "trecho_a.tif"]
    assert imgs[1].pista.name == "trecho_a.pista.geojson" and imgs[0].pista is None
    assert acervo.listar(pasta / "nao_existe") == []


def test_achar_por_nome_ou_caminho(pasta):
    assert acervo.achar("trecho_a", pasta).name == "trecho_a.tif"
    assert acervo.achar("TRECHO_B.GeoTIFF", pasta).name == "TRECHO_B.GeoTIFF"
    assert acervo.achar(pasta / "trecho_a.tif", Path("x")).name == "trecho_a.tif"
    with pytest.raises(FileNotFoundError):
        acervo.achar("outro", pasta)


def test_descrever_le_so_metadados(pasta):
    d = acervo.descrever(pasta / "trecho_a.tif")
    assert d["src"] == "EPSG:31980" and abs(d["gsd_m"] - 0.02) < 1e-9
    assert not d["reprojetar"] and d["largura_px"] == 3000


def test_pasta_por_config_e_por_ambiente(tmp_path, monkeypatch):
    monkeypatch.delenv("PAVISCAN_IMAGENS", raising=False)
    assert acervo.pasta({"acervo": {"pasta_imagens": "../images"}}) == (
        Path(paviscan.__file__).resolve().parents[2].parent / "images"
    )
    monkeypatch.setenv("PAVISCAN_IMAGENS", str(tmp_path))
    assert acervo.pasta({}) == tmp_path


def test_guardar_de_arquivo_e_de_stream(cena, tmp_path):
    destino = tmp_path / "acervo"
    a = acervo.guardar(cena / "orto.tif", "voo_01", destino)
    assert a.name == "voo_01.tif" and acervo.listar(destino)[0].caminho == a
    with open(cena / "orto.tif", "rb") as f:  # como um upload: objeto de arquivo
        b = acervo.guardar(io.BytesIO(f.read()), "voo_02.tiff", destino)
    assert b.name == "voo_02.tiff"
    with pytest.raises(FileExistsError):
        acervo.guardar(cena / "orto.tif", "voo_01", destino)
    assert not list(destino.glob(".*parcial"))


def test_guardar_recusa_o_que_nao_e_raster_e_nao_deixa_resto(tmp_path):
    destino = tmp_path / "acervo"
    with pytest.raises(ValueError):
        acervo.guardar(io.BytesIO(b"isto nao e um tiff"), "lixo", destino)
    assert list(destino.iterdir()) == []


def test_guardar_pista_ao_lado_da_imagem(cena, tmp_path):
    img = acervo.guardar(cena / "orto.tif", "voo", tmp_path)
    p = acervo.guardar_pista(cena / "pista.geojson", img)
    assert p.name == "voo.pista.geojson" and acervo.pista_de(img) == p


def test_cli_imagens_e_run_pelo_nome(pasta, tmp_path, monkeypatch):
    monkeypatch.setenv("PAVISCAN_IMAGENS", str(pasta))
    r = CliRunner().invoke(app, ["imagens"])
    assert r.exit_code == 0 and "trecho_a.pista.geojson" in r.output and "SEM PISTA" in r.output
    r = CliRunner().invoke(app, ["run", "--orto", "trecho_a", "--saida", str(tmp_path / "r")])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "r" / "resumo.json").exists()
    r = CliRunner().invoke(app, ["run", "--orto", "TRECHO_B", "--saida", str(tmp_path / "s")])
    assert r.exit_code != 0 and "pista" in r.output


def test_painel_processa_imagem_do_acervo(pasta, tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("PAVISCAN_IMAGENS", str(pasta))
    monkeypatch.setenv("PAVISCAN_RUNS", str(tmp_path / "runs"))
    arq = str(Path(paviscan.__file__).parent / "painel" / "app.py")
    at = AppTest.from_file(arq, default_timeout=180).run()
    assert not at.exception, at.exception
    assert at.selectbox(key="nova_orto").options == [
        "TRECHO_B.GeoTIFF  (sem polígono da pista)",
        "trecho_a.tif",
    ]
    at.selectbox(key="nova_orto").set_value("trecho_a.tif").run()
    at.button[0].click().run()
    assert not at.exception, at.exception
    assert (tmp_path / "runs" / "trecho_a" / "resumo.json").exists()
    assert len(at.metric) >= 3
