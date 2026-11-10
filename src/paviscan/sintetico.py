"""Gera cenas sinteticas de pista com buracos de gabarito conhecido.

Serve de oraculo para os testes golden e de plano B para o antes/depois.
Nao altere a assinatura de `gerar_cena` nem de `gerar_par`.

Uso: python -m paviscan.sintetico dados/sint --seed 7
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from scipy.ndimage import gaussian_filter
from shapely import affinity
from shapely.geometry import Polygon, box, mapping

SRC = "EPSG:31980"  # SIRGAS 2000 / UTM 20S (Manaus)
ORIGEM = (830_000.0, 9_660_000.0)  # canto superior esquerdo (E, N)


def _buraco(cx: float, cy: float, raio: float, rng: np.random.Generator) -> Polygon:
    """Poligono irregular, aproximadamente eliptico, em metros."""
    ang = np.linspace(0, 2 * np.pi, 24, endpoint=False)
    r = raio * (1 + 0.15 * rng.standard_normal(ang.size))
    r = np.clip(r, 0.6 * raio, 1.4 * raio)
    pol = Polygon(np.c_[cx + r * np.cos(ang), cy + r * np.sin(ang)]).buffer(0)
    pol = affinity.scale(pol, 1.0, rng.uniform(0.6, 1.0))
    return affinity.rotate(pol, rng.uniform(0, 180))


def _sortear_buracos(n: int, pista: Polygon, rng: np.random.Generator) -> list[Polygon]:
    x0, y0, x1, y1 = pista.bounds
    out: list[Polygon] = []
    tent = 0
    while len(out) < n and tent < 5000:
        tent += 1
        raio = rng.uniform(0.25, 0.7)
        p = _buraco(rng.uniform(x0 + 1, x1 - 1), rng.uniform(y0 + 1.2, y1 - 1.2), raio, rng)
        if not pista.buffer(-0.3).contains(p):
            continue
        if any(p.distance(q) < 1.5 for q in out):
            continue
        out.append(p)
    return out


def _renderizar(
    buracos: list[Polygon],
    pista: Polygon,
    largura_m: float,
    altura_m: float,
    gsd: float,
    rng: np.random.Generator,
) -> tuple[np.ndarray, rasterio.Affine]:
    w, h = int(round(largura_m / gsd)), int(round(altura_m / gsd))
    tf = from_origin(ORIGEM[0], ORIGEM[1], gsd, gsd)

    # terreno fora da pista (mais claro) e asfalto com textura
    img = 150 + 12 * gaussian_filter(rng.standard_normal((h, w)), 6)
    m_pista = rasterize([(mapping(pista), 1)], out_shape=(h, w), transform=tf).astype(bool)
    asfalto = (
        95 + 6 * gaussian_filter(rng.standard_normal((h, w)), 3) + 4 * rng.standard_normal((h, w))
    )
    asfalto += 8 * gaussian_filter(rng.standard_normal((h, w)), 40 / (gsd * 100))  # manchas largas
    img[m_pista] = asfalto[m_pista]

    # distratores: faixa central tracejada (clara) e uma trinca/sombra fina (escura)
    x0, y0, x1, y1 = pista.bounds
    yc = (y0 + y1) / 2
    faixas = [box(x, yc - 0.06, x + 2.0, yc + 0.06) for x in np.arange(x0 + 1, x1 - 2, 4.0)]
    m_faixa = rasterize([(mapping(f), 1) for f in faixas], out_shape=(h, w), transform=tf).astype(
        bool
    )
    img[m_faixa & m_pista] = 215
    trinca = box(x0 + 3, y0 + 0.8, x0 + 9, y0 + 0.84)
    m_tr = rasterize([(mapping(trinca), 1)], out_shape=(h, w), transform=tf).astype(bool)
    img[m_tr] -= 35

    # buracos: escuros, borda suave
    if buracos:
        m_b = rasterize([(mapping(b), 1) for b in buracos], out_shape=(h, w), transform=tf)
        suave = gaussian_filter(m_b.astype(float), max(1.0, 0.02 / gsd))
        img -= 50 * suave

    cinza = np.clip(img, 0, 255).astype(np.uint8)
    rgb = np.stack([cinza, cinza, np.clip(cinza.astype(int) + 3, 0, 255).astype(np.uint8)])
    return rgb, tf


def _gravar(
    pasta: Path, rgb: np.ndarray, tf, pista: Polygon, buracos: list[Polygon], gsd: float
) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    perfil = dict(
        driver="GTiff",
        count=3,
        dtype="uint8",
        height=rgb.shape[1],
        width=rgb.shape[2],
        crs=SRC,
        transform=tf,
        compress="deflate",
        tiled=True,
        blockxsize=256,
        blockysize=256,
    )
    with rasterio.open(pasta / "orto.tif", "w", **perfil) as dst:
        dst.write(rgb)

    def fc(feats):
        return {
            "type": "FeatureCollection",
            "crs": {
                "type": "name",
                "properties": {"name": f"urn:ogc:def:crs:{SRC.replace(':', '::')}"},
            },
            "features": feats,
        }

    (pasta / "pista.geojson").write_text(
        json.dumps(
            fc([{"type": "Feature", "properties": {"nome": "pista"}, "geometry": mapping(pista)}])
        )
    )
    (pasta / "gabarito.geojson").write_text(
        json.dumps(
            fc(
                [
                    {
                        "type": "Feature",
                        "properties": {"id": i, "area_m2": round(b.area, 4)},
                        "geometry": mapping(b),
                    }
                    for i, b in enumerate(buracos)
                ]
            )
        )
    )
    (pasta / "meta.json").write_text(
        json.dumps({"gsd_m": gsd, "src": SRC, "n_buracos": len(buracos)})
    )
    return pasta


def gerar_cena(
    pasta: Path,
    n_buracos: int = 8,
    gsd: float = 0.02,
    comprimento_m: float = 60.0,
    largura_pista_m: float = 7.0,
    seed: int = 7,
) -> Path:
    """Grava orto.tif, pista.geojson, gabarito.geojson e meta.json em `pasta`."""
    rng = np.random.default_rng(seed)
    altura_m = largura_pista_m + 4.0
    pista = box(
        ORIGEM[0], ORIGEM[1] - 2.0 - largura_pista_m, ORIGEM[0] + comprimento_m, ORIGEM[1] - 2.0
    )
    buracos = _sortear_buracos(n_buracos, pista, rng)
    rgb, tf = _renderizar(buracos, pista, comprimento_m, altura_m, gsd, rng)
    return _gravar(Path(pasta), rgb, tf, pista, buracos, gsd)


def gerar_par(
    pasta: Path,
    n_buracos: int = 8,
    n_novos: int = 2,
    n_reparados: int = 1,
    fator_crescimento: float = 1.6,
    gsd: float = 0.02,
    seed: int = 7,
) -> tuple[Path, Path]:
    """Gera `pasta/antes` e `pasta/depois` do mesmo trecho.

    No depois: os `n_reparados` primeiros buracos somem, os demais crescem em area
    por `fator_crescimento`, e surgem `n_novos`. `depois/esperado.json` guarda as contagens.
    """
    rng = np.random.default_rng(seed)
    comprimento_m, largura_pista_m = 60.0, 7.0
    altura_m = largura_pista_m + 4.0
    pista = box(
        ORIGEM[0], ORIGEM[1] - 2.0 - largura_pista_m, ORIGEM[0] + comprimento_m, ORIGEM[1] - 2.0
    )
    todos = _sortear_buracos(n_buracos + n_novos, pista, rng)
    antes, novos = todos[:n_buracos], todos[n_buracos:]
    k = fator_crescimento**0.5
    crescidos = [affinity.scale(b, k, k) for b in antes[n_reparados:]]
    depois = crescidos + novos

    pasta = Path(pasta)
    rgb_a, tf = _renderizar(
        antes, pista, comprimento_m, altura_m, gsd, np.random.default_rng(seed + 1)
    )
    a = _gravar(pasta / "antes", rgb_a, tf, pista, antes, gsd)
    rgb_d, tf = _renderizar(
        depois, pista, comprimento_m, altura_m, gsd, np.random.default_rng(seed + 2)
    )
    d = _gravar(pasta / "depois", rgb_d, tf, pista, depois, gsd)
    (d / "esperado.json").write_text(
        json.dumps({"novos": len(novos), "cresceram": len(crescidos), "reparados": n_reparados})
    )
    return a, d


if __name__ == "__main__":
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dados/sint")
    semente = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 7
    gerar_cena(destino / "cena", seed=semente)
    gerar_par(destino / "par", seed=semente)
    print(f"Cenas gravadas em {destino}")
