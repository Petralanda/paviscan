import numpy as np
import pytest
from scipy.ndimage import gaussian_filter

from paviscan.deteccao import Deteccao, criar
from paviscan.deteccao.classico import limiar_robusto
from paviscan.pipeline import carregar_config


@pytest.fixture(scope="module")
def det():
    params = carregar_config()
    return criar(params["detector"], params)


def _asfalto(h=300, w=400, seed=0):
    rng = np.random.default_rng(seed)
    return 95 + 4 * rng.standard_normal((h, w))


def _rgb(cinza):
    c = np.clip(cinza, 0, 255).astype(np.uint8)
    return np.stack([c, c, c], axis=-1)


def test_fabrica_e_contrato(det):
    assert det.nome == "classico" and det.versao
    with pytest.raises(ValueError):
        criar("nao_existe", {})


def test_limiar_robusto_nao_inventa_classe():
    v = np.random.default_rng(1).normal(0, 2, 10_000)
    assert limiar_robusto(v, 6.0, 18.0) == 18.0  # ruido puro: fica no piso
    assert limiar_robusto(v + 100, 6.0, 18.0) > 100


def test_buraco_quadrado_de_50px_a_2cm(det):
    img = _asfalto()
    img[100:150, 200:250] -= 50
    out = det.detectar(_rgb(img), 0.02, np.ones(img.shape, bool))
    assert len(out) == 1 and isinstance(out[0], Deteccao)
    area = out[0].mascara.sum() * 0.02**2
    assert abs(area - 1.0) < 0.1
    assert 0.5 < out[0].confianca <= 1.0


def test_asfalto_limpo_nada(det):
    img = _asfalto(seed=2)
    assert det.detectar(_rgb(img), 0.02, np.ones(img.shape, bool)) == []


def test_trinca_e_fora_da_pista_ignorados(det):
    img = _asfalto(seed=3)
    img[150:152, 20:380] -= 40  # trinca fina e longa
    img[:, :60] = 150  # terreno claro fora da pista
    valida = np.ones(img.shape, bool)
    valida[:, :60] = False
    assert det.detectar(_rgb(img), 0.02, valida) == []


def test_borda_suave_tem_menos_confianca(det):
    nitido = _asfalto(seed=4)
    nitido[100:150, 200:250] -= 50
    m = np.zeros(nitido.shape)
    m[100:150, 200:250] = 1
    suave = _asfalto(seed=4) - 50 * gaussian_filter(m, 6)
    valida = np.ones(nitido.shape, bool)
    c_nitido = det.detectar(_rgb(nitido), 0.02, valida)[0].confianca
    c_suave = [d.confianca for d in det.detectar(_rgb(suave), 0.02, valida)]
    assert not c_suave or max(c_suave) < c_nitido
