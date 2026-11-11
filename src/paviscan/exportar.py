"""Saidas do levantamento: GeoJSON, GPKG, XLSX, resumo.json e previa.png."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds
from rasterio.windows import bounds as limites_janela

from paviscan import ingestao

LADO_PREVIA_PX = 4000  # maior lado da previa: cabe na textura WebGL do mapa


def gravar_vetores(defeitos: gpd.GeoDataFrame, segmentos: gpd.GeoDataFrame, saida: Path) -> None:
    """defeitos.geojson, segmentos.geojson e defeitos.gpkg (camadas defeitos e segmentos)."""
    defeitos.to_file(saida / "defeitos.geojson", driver="GeoJSON")
    segmentos.to_file(saida / "segmentos.geojson", driver="GeoJSON")
    gpkg = saida / "defeitos.gpkg"
    gpkg.unlink(missing_ok=True)
    defeitos.to_file(gpkg, layer="defeitos", driver="GPKG")
    segmentos.to_file(gpkg, layer="segmentos", driver="GPKG")


def gravar_resumo(resumo: dict, saida: Path) -> None:
    (saida / "resumo.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False), "utf-8")


def gravar_xlsx(
    resumo: dict, defeitos: gpd.GeoDataFrame, segmentos: gpd.GeoDataFrame, saida: Path
) -> None:
    """resumo.xlsx com as abas Resumo, Buracos e Segmentos."""
    linhas = [(k, json.dumps(v) if isinstance(v, list) else v) for k, v in resumo.items()]
    with pd.ExcelWriter(saida / "resumo.xlsx", engine="openpyxl") as xl:
        pd.DataFrame(linhas, columns=["indicador", "valor"]).to_excel(
            xl, sheet_name="Resumo", index=False
        )
        buracos = pd.DataFrame(defeitos.drop(columns="geometry"))
        if len(defeitos):
            c = defeitos.geometry.centroid
            buracos["x_centroide"], buracos["y_centroide"] = c.x.to_numpy(), c.y.to_numpy()
        buracos.to_excel(xl, sheet_name="Buracos", index=False)
        pd.DataFrame(segmentos.drop(columns="geometry")).to_excel(
            xl, sheet_name="Segmentos", index=False
        )


def gravar_previa(
    ds, geom, saida: Path, margem_m: float, escala: tuple[float, float] | None = None
) -> list[list[float]]:
    """previa.png do entorno da pista, com o maior lado reduzido a no maximo LADO_PREVIA_PX.

    Le a janela ja reduzida (`out_shape`), sem carregar o raster inteiro. Devolve os limites
    em EPSG:4326 no formato [[lat_s, lon_o], [lat_n, lon_l]].
    """
    x0, y0, x1, y1 = geom.buffer(margem_m).bounds
    jan = from_bounds(x0, y0, x1, y1, transform=ds.transform)
    jan = jan.intersection(Window(0, 0, ds.width, ds.height)).round_offsets().round_lengths()
    fator = max(1.0, max(jan.width, jan.height) / LADO_PREVIA_PX)
    forma = (max(1, int(jan.height / fator)), max(1, int(jan.width / fator)))
    bandas = [1, 1, 1] if ds.count < 3 else [1, 2, 3]
    arr = ds.read(bandas, window=jan, out_shape=(3, *forma), resampling=Resampling.average)
    rgb = ingestao.para_uint8(np.moveaxis(arr, 0, -1), escala)
    alfa = ds.dataset_mask(window=jan, out_shape=forma, resampling=Resampling.nearest)
    bgra = np.dstack([rgb[..., ::-1], alfa.astype(np.uint8)])
    ok, png = cv2.imencode(".png", bgra)
    if not ok:
        raise RuntimeError("falha ao codificar previa.png")
    (saida / "previa.png").write_bytes(png.tobytes())
    o, s, l_, n = transform_bounds(ds.crs, "EPSG:4326", *limites_janela(jan, ds.transform))
    return [[s, o], [n, l_]]
