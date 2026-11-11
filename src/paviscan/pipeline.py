"""Orquestra o processamento de uma ortofoto: ingestao, pista, deteccao e geometria."""

from __future__ import annotations

import math
import warnings
from collections.abc import Callable
from pathlib import Path

import numpy as np
import rasterio
import yaml
from rasterio.windows import Window
from rasterio.windows import transform as transform_janela

from paviscan import deteccao, geometria, ingestao, pista

CONFIG_PADRAO = Path(__file__).resolve().parents[2] / "config" / "params.yaml"

Progresso = Callable[[float, str], None]


def carregar_config(config: Path | None = None) -> dict:
    """Le o params.yaml (o do repositorio quando `config` e None)."""
    caminho = Path(config) if config else CONFIG_PADRAO
    return yaml.safe_load(caminho.read_text(encoding="utf-8"))


def _relativa(janela: Window, base: Window) -> Window:
    return Window(
        janela.col_off - base.col_off, janela.row_off - base.row_off, janela.width, janela.height
    )


def gravar_recorte(ds, geom, jan_pista: Window, destino: Path, params: dict) -> None:
    """Grava a ortofoto recortada a pista, janela a janela, com mascara fora da pista."""
    tf = transform_janela(jan_pista, ds.transform)
    perfil = dict(
        driver="GTiff",
        count=3,
        dtype="uint8",
        width=int(jan_pista.width),
        height=int(jan_pista.height),
        crs=ds.crs,
        transform=tf,
        compress="deflate",
        tiled=True,
        blockxsize=256,
        blockysize=256,
    )
    t = params["tiles"]
    with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=True), rasterio.open(destino, "w", **perfil) as dst:
        for _, inn in ingestao.janelas(ds.width, ds.height, t["tamanho_px"], 0, jan_pista):
            rgb, valido = ingestao.ler_rgb(ds, inn)
            m = valido & pista.mascara(geom, transform_janela(inn, ds.transform), valido.shape)
            rgb[~m] = 0
            rel = _relativa(inn, jan_pista)
            dst.write(np.moveaxis(rgb, -1, 0), window=rel)
            dst.write_mask((m * 255).astype(np.uint8), window=rel)


def tiles_em_px(params: dict, gsd: float) -> tuple[int, int]:
    """(tamanho, sobreposicao) em pixels. A sobreposicao vem em metros; o tile cresce se preciso
    para o miolo continuar com pelo menos metade do tile."""
    t = params["tiles"]
    sob = int(math.ceil(t["sobreposicao_m"] / gsd))
    return max(int(t["tamanho_px"]), 4 * sob), sob


def _toca_borda_interna(m: np.ndarray, ext: Window, largura: int, altura: int) -> bool:
    """True se a mascara encosta numa borda do tile que nao e borda do raster (buraco cortado)."""
    r0, c0 = int(ext.row_off), int(ext.col_off)
    r1, c1 = r0 + m.shape[0], c0 + m.shape[1]
    return bool(
        (r0 > 0 and m[0].any())
        or (r1 < altura and m[-1].any())
        or (c0 > 0 and m[:, 0].any())
        or (c1 < largura and m[:, -1].any())
    )


def detectar_trecho(ds, geom, jan_pista: Window, params: dict, avisar: Progresso):
    """Roda o detector tile a tile. Cada buraco fica com o tile cujo miolo contem o centroide.

    A sobreposicao (em metros, `tiles.sobreposicao_m`) tem que passar do raio do maior buraco:
    assim o tile dono ve o buraco inteiro. Se mesmo assim ele encostar na borda, ha aviso.
    """
    det = deteccao.criar(params["detector"], params)
    gsd = ingestao.gsd_m(ds)
    tam, sob = tiles_em_px(params, gsd)
    tiles = list(ingestao.janelas(ds.width, ds.height, tam, sob, jan_pista))
    poligonos, confiancas, cortados = [], [], 0
    for k, (ext, inn) in enumerate(tiles):
        avisar(0.2 + 0.6 * k / len(tiles), f"detectando ({k + 1}/{len(tiles)})")
        tf = transform_janela(ext, ds.transform)
        rgb, valido = ingestao.ler_rgb(ds, ext)
        valida = valido & pista.mascara(geom, tf, valido.shape)
        if not valida.any():
            continue
        for d in det.detectar(rgb, gsd, valida):
            lin, col = np.nonzero(d.mascara)
            cl = float(lin.mean()) + ext.row_off
            cc = float(col.mean()) + ext.col_off
            dentro_l = inn.row_off <= cl < inn.row_off + inn.height
            dentro_c = inn.col_off <= cc < inn.col_off + inn.width
            if not (dentro_l and dentro_c):
                continue
            cortados += _toca_borda_interna(d.mascara, ext, ds.width, ds.height)
            pol = geometria.vetorizar(d.mascara, tf, gsd)
            if pol is not None and pol.area > 0:
                poligonos.append(pol)
                confiancas.append(d.confianca)
    if cortados:
        warnings.warn(
            f"{cortados} buraco(s) encostam na borda do tile: aumente tiles.sobreposicao_m",
            stacklevel=2,
        )
    return geometria.montar_defeitos(poligonos, confiancas, ds.crs, params), det


def processar(
    orto: Path,
    pista_path: Path,
    saida: Path,
    config: Path | None = None,
    progresso: Progresso | None = None,
) -> Path:
    """Processa `orto` restrita a `pista_path` e grava os resultados em `saida`."""
    params = carregar_config(config)
    avisar = progresso or (lambda f, msg: None)
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    with ingestao.abrir(Path(orto)) as ds:
        geom = pista.carregar(Path(pista_path), ds.crs)
        jan = pista.janela(geom, ds.transform, ds.width, ds.height)
        avisar(0.1, "recortando a pista")
        gravar_recorte(ds, geom, jan, saida / "pista_recorte.tif", params)
        defeitos, _ = detectar_trecho(ds, geom, jan, params, avisar)
    avisar(0.9, "gravando resultados")
    defeitos.to_file(saida / "defeitos.geojson", driver="GeoJSON")
    avisar(1.0, "pronto")
    return saida
