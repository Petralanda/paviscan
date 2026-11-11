"""Acervo de ortofotos: a pasta de imagens que o painel e o CLI oferecem para processar.

Hoje as imagens sao copiadas para a pasta a mao. `guardar` ja grava uma imagem recebida
(por exemplo, de um upload futuro no painel) no acervo, validando antes de publicar.

Cada imagem pode ter o poligono da pista ao lado, com o mesmo nome:
    images/trecho.tif  +  images/trecho.pista.geojson
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import geopandas as gpd
import rasterio
from rasterio.warp import transform_bounds

from paviscan import ingestao

EXTENSOES = (".tif", ".tiff", ".geotiff", ".gtiff")
SUFIXOS_PISTA = (".pista.geojson", ".pista.gpkg")
RAIZ = Path(__file__).resolve().parents[2]


@dataclass
class Imagem:
    nome: str  # nome do arquivo sem extensao
    caminho: Path
    pista: Path | None  # poligono da pista ao lado da imagem, se houver


def pasta(params: dict | None = None) -> Path:
    """Pasta do acervo: PAVISCAN_IMAGENS, ou `acervo.pasta_imagens` do params.yaml
    (relativa a raiz do repositorio)."""
    if os.environ.get("PAVISCAN_IMAGENS"):
        return Path(os.environ["PAVISCAN_IMAGENS"])
    rel = (params or {}).get("acervo", {}).get("pasta_imagens", "../images")
    p = Path(rel)
    return p if p.is_absolute() else (RAIZ / p).resolve()


def eh_imagem(caminho: Path) -> bool:
    return caminho.is_file() and caminho.suffix.lower() in EXTENSOES


def pista_de(imagem: Path) -> Path | None:
    """Poligono da pista guardado ao lado da imagem."""
    for suf in SUFIXOS_PISTA:
        p = imagem.with_name(imagem.stem + suf)
        if p.is_file():
            return p
    return None


def listar(pasta_imagens: Path) -> list[Imagem]:
    """Imagens do acervo, em ordem alfabetica."""
    pasta_imagens = Path(pasta_imagens)
    if not pasta_imagens.is_dir():
        return []
    arqs = sorted((p for p in pasta_imagens.iterdir() if eh_imagem(p)), key=lambda p: p.name)
    return [Imagem(p.stem, p, pista_de(p)) for p in arqs]


def achar(nome_ou_caminho: str | Path, pasta_imagens: Path) -> Path:
    """Caminho existente, ou o nome (com ou sem extensao) de uma imagem do acervo."""
    p = Path(nome_ou_caminho)
    if p.is_file():
        return p
    for img in listar(pasta_imagens):
        if str(nome_ou_caminho) in (img.nome, img.caminho.name):
            return img.caminho
    raise FileNotFoundError(
        f"{nome_ou_caminho}: nao e arquivo nem imagem do acervo {pasta_imagens}"
    )


def descrever(caminho: Path) -> dict:
    """Metadados para mostrar antes de processar (le so o cabecalho, nao os pixels)."""
    with rasterio.open(caminho) as src:
        crs = src.crs
        lim = transform_bounds(crs, "EPSG:4326", *src.bounds) if crs else None
        return {
            "src": crs.to_string() if crs else None,
            "largura_px": src.width,
            "altura_px": src.height,
            "bandas": src.count,
            "tipo": src.dtypes[0],
            "gsd_m": ingestao.gsd_m(src) if crs and crs.is_projected else None,
            "reprojetar": bool(crs) and ingestao.precisa_reprojetar(crs),
            "limites_4326": lim,
            "tamanho_mb": caminho.stat().st_size / 1e6,
        }


def _validar(caminho: Path) -> None:
    try:
        with rasterio.open(caminho) as src:
            if src.crs is None:
                raise ValueError("a imagem nao tem SRC (georreferencia)")
            if src.count < 1:
                raise ValueError("a imagem nao tem bandas")
    except rasterio.errors.RasterioIOError as e:
        raise ValueError(f"nao e um raster legivel: {e}") from e


def guardar(
    origem: BinaryIO | Path, nome: str, pasta_imagens: Path, sobrescrever: bool = False
) -> Path:
    """Grava uma imagem no acervo e devolve o caminho final.

    Copia em blocos (ortofoto passa de 200 MB) para um arquivo temporario, confere que e um
    raster georreferenciado e so entao publica com o nome final. Se a validacao falha, nada
    fica no acervo.
    """
    destino_nome = Path(nome).name
    if Path(destino_nome).suffix.lower() not in EXTENSOES:
        destino_nome += ".tif"
    pasta_imagens = Path(pasta_imagens)
    pasta_imagens.mkdir(parents=True, exist_ok=True)
    destino = pasta_imagens / destino_nome
    if destino.exists() and not sobrescrever:
        raise FileExistsError(f"ja existe {destino.name} no acervo")
    temp = destino.with_name(f".{destino.name}.parcial")
    try:
        if isinstance(origem, (str, Path)):
            shutil.copyfile(origem, temp)
        else:
            with open(temp, "wb") as f:
                shutil.copyfileobj(origem, f, length=8 * 1024 * 1024)
        _validar(temp)
        os.replace(temp, destino)
    finally:
        temp.unlink(missing_ok=True)
    return destino


def guardar_pista(origem: BinaryIO | Path, imagem: Path) -> Path:
    """Grava o poligono da pista ao lado da imagem, como `<nome>.pista.geojson`.

    Aceita qualquer formato que o geopandas le (GeoJSON, GPKG, shapefile zipado).
    """
    gdf = gpd.read_file(origem)
    if gdf.empty or gdf.crs is None:
        raise ValueError("o poligono da pista esta vazio ou sem SRC")
    destino = Path(imagem).with_name(Path(imagem).stem + ".pista.geojson")
    gdf.to_file(destino, driver="GeoJSON")
    return destino
