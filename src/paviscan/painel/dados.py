"""Dados do dashboard: leitura, filtros e indicadores. Funcoes puras, sem Streamlit."""

from __future__ import annotations

import base64
import io
import json
import math
from pathlib import Path

import cv2
import geopandas as gpd
import numpy as np
import pandas as pd

from paviscan import indicadores, pista

SEVERIDADES = ["baixa", "media", "alta"]
ROTULOS_SEVERIDADE = {"baixa": "Baixa", "media": "Média", "alta": "Alta"}
CORES_SEVERIDADE = {"baixa": "#E9B949", "media": "#E8772E", "alta": "#C8102E"}
TIPOS_DEFEITOS = {
    "id": "int64",
    "area_m2": "float64",
    "largura_m": "float64",
    "comprimento_m": "float64",
    "confianca": "float64",
    "severidade": "object",
    "segmento": "int64",
}


def listar_runs(pasta: Path) -> list[Path]:
    """Subpastas com resumo.json (um levantamento processado cada), mais recentes primeiro."""
    pasta = Path(pasta)
    if not pasta.is_dir():
        return []
    runs = [p for p in pasta.iterdir() if (p / "resumo.json").is_file()]
    return sorted(runs, key=lambda p: (p / "resumo.json").stat().st_mtime, reverse=True)


def _com_colunas(defeitos: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """GeoJSON sem feicoes nao guarda esquema: repoe as colunas do contrato."""
    out = defeitos.copy()
    for col, tipo in TIPOS_DEFEITOS.items():
        if col not in out.columns:
            out[col] = pd.Series(dtype=tipo)
        elif len(out):
            out[col] = out[col].astype(tipo)
    return out


def carregar(run: Path) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, dict]:
    """(defeitos, segmentos, resumo) de uma pasta de resultado."""
    run = Path(run)
    resumo = json.loads((run / "resumo.json").read_text(encoding="utf-8"))
    segmentos = gpd.read_file(run / "segmentos.geojson")
    defeitos = gpd.read_file(run / "defeitos.geojson")
    if defeitos.crs is None:
        defeitos = defeitos.set_crs(segmentos.crs)
    return _com_colunas(defeitos), segmentos, resumo


def filtrar(
    defeitos: gpd.GeoDataFrame,
    area_min: float | None = None,
    area_max: float | None = None,
    confianca_min: float | None = None,
    severidade: list[str] | None = None,
    segmentos: list[int] | None = None,
) -> gpd.GeoDataFrame:
    """Aplica os filtros do dashboard. None = nao filtra."""
    m = pd.Series(True, index=defeitos.index)
    if area_min is not None:
        m &= defeitos["area_m2"] >= area_min
    if area_max is not None:
        m &= defeitos["area_m2"] <= area_max
    if confianca_min is not None:
        m &= defeitos["confianca"] >= confianca_min
    if severidade is not None:
        m &= defeitos["severidade"].isin(list(severidade))
    if segmentos is not None:
        m &= defeitos["segmento"].isin([int(s) for s in segmentos])
    return defeitos[m]


def comprimento_m(segmentos: gpd.GeoDataFrame) -> float:
    """Comprimento da pista ao longo do eixo."""
    if "comprimento_m" in segmentos.columns:
        return float(segmentos["comprimento_m"].sum())
    _, _, s0, s1 = pista.eixo(segmentos.geometry.union_all())
    return s1 - s0


def resumir(defeitos: gpd.GeoDataFrame, segmentos: gpd.GeoDataFrame) -> dict:
    """Indicadores do que esta filtrado. A % usa a area de pista de todos os segmentos."""
    n = int(len(defeitos))
    area = float(defeitos["area_m2"].sum()) if n else 0.0
    area_pista = float(segmentos["area_pista_m2"].sum())
    comp = comprimento_m(segmentos)
    return {
        "n_buracos": n,
        "area_total_m2": area,
        "pct_afetada": 100 * area / area_pista if area_pista > 0 else 0.0,
        "buracos_por_100m": 100 * n / comp if comp > 0 else 0.0,
        "maior_buraco_m2": float(defeitos["area_m2"].max()) if n else 0.0,
    }


def por_segmento(defeitos: gpd.GeoDataFrame, segmentos: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Segmentos com os indicadores recalculados so com os defeitos filtrados."""
    base = segmentos.drop(
        columns=["area_pista_m2", "n_buracos", "area_buracos_m2", "pct_afetada"], errors="ignore"
    )
    return indicadores.agregar(defeitos, base).sort_values("segmento")


def ranking(seg: gpd.GeoDataFrame, n: int = 5) -> pd.DataFrame:
    """Piores segmentos pela % afetada (so os que tem buraco)."""
    cols = ["segmento", "inicio_m", "fim_m", "n_buracos", "area_buracos_m2", "pct_afetada"]
    cols = [c for c in cols if c in seg.columns]
    r = seg[seg["n_buracos"] > 0].sort_values(["pct_afetada", "n_buracos"], ascending=False)
    return pd.DataFrame(r[cols].head(n)).reset_index(drop=True)


def tabela(defeitos: gpd.GeoDataFrame) -> pd.DataFrame:
    """Defeitos sem geometria, ordenados por area, para a tabela e o CSV."""
    cols = list(TIPOS_DEFEITOS)
    df = pd.DataFrame(defeitos[cols]).sort_values("area_m2", ascending=False)
    if len(defeitos):
        c = defeitos.loc[df.index].geometry.centroid
        df["x_centroide"], df["y_centroide"] = c.x.to_numpy(), c.y.to_numpy()
    return df.reset_index(drop=True)


def csv_bytes(defeitos: gpd.GeoDataFrame) -> bytes:
    """CSV em padrao brasileiro (separador ;, decimal ,), com BOM para o Excel."""
    return tabela(defeitos).to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")


def xlsx_bytes(defeitos: gpd.GeoDataFrame, segmentos: gpd.GeoDataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        tabela(defeitos).to_excel(xl, sheet_name="Buracos", index=False)
        pd.DataFrame(segmentos.drop(columns="geometry")).to_excel(
            xl, sheet_name="Segmentos", index=False
        )
    return buf.getvalue()


def geojson_bytes(defeitos: gpd.GeoDataFrame) -> bytes:
    """GeoJSON no SRC de medida (UTM), com o crs declarado."""
    return defeitos.to_json(drop_id=True).encode("utf-8")


def para_mapa(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Copia em EPSG:4326 so para exibir. Nunca medir nela."""
    return gdf.to_crs("EPSG:4326")


def poligonos_mapa(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Uma linha por anel externo, em lon/lat, para o PolygonLayer do pydeck (coluna `contorno`).

    Multipoligono vira uma linha por parte, repetindo os atributos.
    """
    g = para_mapa(gdf).explode(index_parts=False)
    df = pd.DataFrame(g.drop(columns="geometry"))
    df["contorno"] = [[list(xy) for xy in p.exterior.coords] for p in g.geometry]
    return df.reset_index(drop=True)


def cor_rgba(hexa: str, alfa: int = 200) -> list[int]:
    h = hexa.lstrip("#")
    return [int(h[i : i + 2], 16) for i in (0, 2, 4)] + [alfa]


def cor_pct(pct: float, pct_max: float) -> list[int]:
    """Verde -> vermelho conforme a % afetada do segmento (relativa ao pior)."""
    t = 0.0 if pct_max <= 0 else min(1.0, pct / pct_max)
    return [int(60 + 160 * t), int(170 - 120 * t), 90, 90]


def previa_data_uri(run: Path, lado_max: int = 2048) -> str | None:
    """previa.png reduzida para o navegador, como data URI."""
    p = Path(run) / "previa.png"
    if not p.is_file():
        return None
    img = cv2.imdecode(np.frombuffer(p.read_bytes(), np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    f = max(img.shape[:2]) / lado_max
    if f > 1:
        img = cv2.resize(
            img, (int(img.shape[1] / f), int(img.shape[0] / f)), interpolation=cv2.INTER_AREA
        )
    ok, png = cv2.imencode(".png", img)
    return "data:image/png;base64," + base64.b64encode(png.tobytes()).decode() if ok else None


def vista_inicial(limites: list[list[float]], largura_px: int = 900, altura_px: int = 560) -> dict:
    """Centro e zoom que enquadram os limites [[lat_s, lon_o], [lat_n, lon_l]] na tela."""
    (lat_s, lon_o), (lat_n, lon_l) = limites
    lat, lon = (lat_s + lat_n) / 2, (lon_o + lon_l) / 2
    cos = math.cos(math.radians(lat))
    alt_m = max((lat_n - lat_s) * 111_320, 1.0)
    larg_m = max((lon_l - lon_o) * 111_320 * cos, 1.0)
    m_por_px = max(larg_m / largura_px, alt_m / altura_px) * 1.1  # 10% de folga
    zoom = math.log2(78_271.5 * cos / m_por_px)  # deck.gl: mundo de 512 px no zoom 0
    return {"latitude": lat, "longitude": lon, "zoom": max(1.0, min(22.0, zoom))}


def fmt(x: float, casas: int = 2) -> str:
    """Numero em formato brasileiro: 1.234,56."""
    s = f"{x:,.{casas}f}"
    return s.replace(",", "\0").replace(".", ",").replace("\0", ".")
