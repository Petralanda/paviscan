"""Dashboard do PaviScan. So interface: toda conta vem de `paviscan.painel.dados`."""

from __future__ import annotations

import os
from pathlib import Path

import plotly.express as px
import pydeck as pdk
import streamlit as st

from paviscan import acervo
from paviscan.painel import dados as D
from paviscan.pipeline import carregar_config, processar

st.set_page_config(page_title="PaviScan", page_icon="🛣️", layout="wide")

PASTA_RUNS = Path(os.environ.get("PAVISCAN_RUNS", "runs"))
ORDEM_SEV = {"severidade": D.SEVERIDADES}
CORES_PLOTLY = D.CORES_SEVERIDADE
ALTURA_MAPA = 560


@st.cache_data(show_spinner=False)
def _carregar(run: str, versao: float):
    return D.carregar(Path(run))


@st.cache_data(show_spinner=False)
def _previa(run: str, versao: float):
    return D.previa_data_uri(Path(run))


def _versao(run: Path) -> float:
    return (run / "resumo.json").stat().st_mtime


@st.cache_data(show_spinner=False)
def _descrever(caminho: str, versao: float) -> dict:
    return acervo.descrever(Path(caminho))


def _processar_nova() -> None:
    """Escolhe uma ortofoto do acervo (pasta de imagens) e processa na hora."""
    pasta = acervo.pasta(carregar_config())
    with st.expander("Processar nova imagem", expanded=not D.listar_runs(PASTA_RUNS)):
        imgs = acervo.listar(pasta)
        if not imgs:
            st.info(f"Nenhuma GeoTIFF no acervo. Copie as ortofotos para `{pasta}`.")
            return
        st.caption(f"Acervo de imagens: `{pasta}`")
        por_nome = {i.caminho.name: i for i in imgs}
        escolha = st.selectbox(
            "Ortofoto",
            list(por_nome),
            key="nova_orto",
            format_func=lambda n: n if por_nome[n].pista else f"{n}  (sem polígono da pista)",
        )
        img = por_nome[escolha]
        d = _descrever(str(img.caminho), img.caminho.stat().st_mtime)
        gsd = f"{D.fmt(100 * d['gsd_m'], 1)} cm/px" if d["gsd_m"] else "SRC em graus"
        st.caption(
            f"{d['largura_px']} x {d['altura_px']} px · {gsd} · {d['src']} · "
            f"{D.fmt(d['tamanho_mb'], 0)} MB"
            + (" · será reprojetada para UTM" if d["reprojetar"] else "")
        )
        if img.pista:
            st.caption(f"Polígono da pista: `{img.pista.name}`")
            pista = str(img.pista)
        else:
            pista = st.text_input(
                "Polígono da pista (GeoJSON/GPKG)",
                key=f"nova_pista_{img.nome}",
                help=f"Ou salve como {img.nome}.pista.geojson ao lado da imagem.",
            )
        digitado = st.text_input(
            "Nome do levantamento", value=img.nome, key=f"nova_nome_{img.nome}"
        )
        nome = D.nome_levantamento(digitado)
        if nome and nome != digitado:
            st.caption(f"Será gravado como `{nome}`.")
        existe = bool(nome) and (PASTA_RUNS / nome / "resumo.json").exists()
        confirma = True
        if existe:
            confirma = st.checkbox(f"Já existe um levantamento `{nome}`. Sobrescrever?")
        if st.button("Processar", type="primary", disabled=not (pista and nome and confirma)):
            if not Path(pista).is_file():
                st.error("Polígono da pista não encontrado. Confira o caminho.")
                return
            barra = st.progress(0.0, text="Começando")
            try:
                processar(
                    img.caminho,
                    Path(pista),
                    PASTA_RUNS / nome,
                    progresso=lambda f, msg: barra.progress(min(1.0, f), text=msg),
                )
            except Exception as e:  # mostra o erro ao usuario em vez de quebrar a pagina
                st.error(f"Falha ao processar: {e}")
                return
            st.session_state["run_escolhido"] = nome
            st.rerun()


def _limpar(padroes: dict) -> None:
    for k, v in padroes.items():
        st.session_state[k] = v


def _filtros(det, seg) -> dict:
    """Barra lateral. Devolve os argumentos de `D.filtrar`."""
    sb = st.sidebar
    sb.header("Filtros")
    a_min = float(det["area_m2"].min()) if len(det) else 0.0
    a_max = float(det["area_m2"].max()) if len(det) else 0.0
    todos_seg = [int(s) for s in seg["segmento"]]
    padroes = {
        "f_area": (a_min, a_max),
        "f_sev": list(D.SEVERIDADES),
        "f_conf": 0.0,
        "f_seg": [],
    }
    for k, v in padroes.items():
        st.session_state.setdefault(k, v)

    args: dict = {}
    if a_max > a_min:
        lo, hi = sb.slider(
            "Área do buraco (m²)", a_min, a_max, key="f_area", step=0.01, format="%.2f"
        )
        if lo > a_min:
            args["area_min"] = lo
        if hi < a_max:
            args["area_max"] = hi
    sev = sb.multiselect(
        "Severidade",
        D.SEVERIDADES,
        key="f_sev",
        format_func=lambda s: D.ROTULOS_SEVERIDADE[s],
    )
    if set(sev) != set(D.SEVERIDADES):
        args["severidade"] = sev
    conf = sb.slider("Confiança mínima", 0.0, 1.0, key="f_conf", step=0.05)
    if conf > 0:
        args["confianca_min"] = conf
    segs = sb.multiselect(
        "Segmentos (vazio = todos)",
        todos_seg,
        key="f_seg",
        placeholder="Todos",
        format_func=lambda s: (
            f"{s}  ({D.fmt(float(seg.set_index('segmento').loc[s, 'inicio_m']), 0)} m)"
        ),
    )
    if segs:
        args["segmentos"] = segs
    sb.button("Limpar filtros", on_click=_limpar, args=(padroes,), width="stretch")
    return args


def _indicadores(r: dict, total: int, filtrado: bool) -> None:
    c = st.columns(5)
    rotulo = f"{r['n_buracos']} de {total}" if filtrado else f"{r['n_buracos']}"
    c[0].metric("Buracos", rotulo)
    c[1].metric("Área total", f"{D.fmt(r['area_total_m2'])} m²")
    c[2].metric("% da pista afetada", f"{D.fmt(r['pct_afetada'])} %")
    c[3].metric("Buracos por 100 m", D.fmt(r["buracos_por_100m"], 1))
    c[4].metric("Maior buraco", f"{D.fmt(r['maior_buraco_m2'])} m²")


def _mapa(run: Path, det, seg_f, resumo: dict, mostrar_seg: bool) -> None:
    camadas = []
    img = _previa(str(run), _versao(run))
    (lat_s, lon_o), (lat_n, lon_l) = resumo["previa_limites"]
    if img:
        camadas.append(
            # o conversor JSON do deck.gl le string como expressao: "data:..." quebra no ":".
            # Entre aspas simples vira literal de string e volta como a URI original.
            pdk.Layer(
                "BitmapLayer", image=f"'{img}'", bounds=[lon_o, lat_s, lon_l, lat_n], opacity=1.0
            )
        )
    if mostrar_seg:
        s4 = D.poligonos_mapa(seg_f)
        pmax = float(s4["pct_afetada"].max()) if len(s4) else 0.0
        s4["cor"] = [D.cor_pct(p, pmax) for p in s4["pct_afetada"]]
        s4["dica"] = [
            f"Segmento {s}: {n} buracos, {D.fmt(p)} % afetada"
            for s, n, p in zip(s4["segmento"], s4["n_buracos"], s4["pct_afetada"], strict=True)
        ]
        camadas.append(
            pdk.Layer(
                "PolygonLayer",
                s4[["contorno", "cor", "dica"]],
                get_polygon="contorno",
                get_fill_color="cor",
                get_line_color=[255, 255, 255, 160],
                line_width_min_pixels=1,
                pickable=True,
            )
        )
    if len(det):
        d4 = D.poligonos_mapa(det)
        d4["cor"] = [D.cor_rgba(D.CORES_SEVERIDADE[s], 200) for s in d4["severidade"]]
        # contorno na propria cor: buraco pequeno tem poucos pixels na vista inteira, e um
        # contorno branco cobriria o preenchimento
        d4["borda"] = [D.cor_rgba(D.CORES_SEVERIDADE[s], 255) for s in d4["severidade"]]
        d4["dica"] = [
            f"Buraco {i} · {D.fmt(a)} m² · {D.fmt(w)} x {D.fmt(c)} m · confiança {D.fmt(k)}"
            for i, a, w, c, k in zip(
                d4["id"],
                d4["area_m2"],
                d4["largura_m"],
                d4["comprimento_m"],
                d4["confianca"],
                strict=True,
            )
        ]
        camadas.append(
            pdk.Layer(
                "PolygonLayer",
                d4[["contorno", "cor", "borda", "dica"]],
                get_polygon="contorno",
                get_fill_color="cor",
                get_line_color="borda",
                line_width_min_pixels=2,
                pickable=True,
                auto_highlight=True,
            )
        )
    vista = pdk.ViewState(
        **D.vista_inicial(resumo["previa_limites"], 900, ALTURA_MAPA), pitch=0, max_zoom=23
    )
    st.pydeck_chart(
        pdk.Deck(
            layers=camadas,
            initial_view_state=vista,
            map_provider="carto",
            map_style="light",
            tooltip={"text": "{dica}"},
        ),
        height=ALTURA_MAPA,
        key=f"mapa_{run.name}",  # remonta ao trocar de levantamento: senao fica a camera antiga
    )


def _graficos(det, seg_f) -> None:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Distribuição das áreas")
        tb = D.tabela(det)
        tb["Severidade"] = tb["severidade"].map(D.ROTULOS_SEVERIDADE)
        fig = px.histogram(
            tb,
            x="area_m2",
            color="Severidade",
            nbins=30,
            category_orders={"Severidade": [D.ROTULOS_SEVERIDADE[k] for k in D.SEVERIDADES]},
            color_discrete_map={D.ROTULOS_SEVERIDADE[k]: c for k, c in CORES_PLOTLY.items()},
            labels={"area_m2": "Área (m²)", "count": "Buracos"},
        )
        fig.update_layout(bargap=0.05, yaxis_title="Buracos", separators=",.", height=340)
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.subheader("Área afetada ao longo da pista")
        s = seg_f.assign(inicio=seg_f["inicio_m"].round(0).astype(int).astype(str) + " m")
        fig = px.bar(
            s,
            x="segmento",
            y="pct_afetada",
            hover_data={"inicio": True, "n_buracos": True, "area_buracos_m2": ":.2f"},
            labels={
                "segmento": "Segmento",
                "pct_afetada": "% afetada",
                "n_buracos": "Buracos",
                "area_buracos_m2": "Área (m²)",
                "inicio": "Início",
            },
            color_discrete_sequence=["#E8772E"],
        )
        fig.update_layout(separators=",.", height=340, xaxis={"dtick": 1})
        st.plotly_chart(fig, width="stretch")


def _num(casas: int):
    return lambda x: D.fmt(float(x), casas)


def _ranking_e_tabela(det, seg_f) -> None:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("Piores segmentos")
        rk = D.ranking(seg_f)
        if rk.empty:
            st.info("Nenhum segmento com buraco no filtro atual.")
        else:
            rk = rk.rename(
                columns={
                    "segmento": "Seg.",
                    "inicio_m": "Início (m)",
                    "fim_m": "Fim (m)",
                    "n_buracos": "Buracos",
                    "area_buracos_m2": "Área (m²)",
                    "pct_afetada": "% afetada",
                }
            )
            st.dataframe(
                rk.style.format(
                    {
                        "Início (m)": _num(0),
                        "Fim (m)": _num(0),
                        "Área (m²)": _num(2),
                        "% afetada": _num(2),
                    }
                ),
                hide_index=True,
                width="stretch",
            )
    with c2:
        st.subheader("Buracos")
        tb = D.tabela(det).rename(
            columns={
                "id": "Id",
                "area_m2": "Área (m²)",
                "largura_m": "Largura (m)",
                "comprimento_m": "Compr. (m)",
                "confianca": "Confiança",
                "severidade": "Severidade",
                "segmento": "Seg.",
                "x_centroide": "E (m)",
                "y_centroide": "N (m)",
            }
        )
        estilo = tb.style.format(
            {
                "Área (m²)": _num(3),
                "Largura (m)": _num(2),
                "Compr. (m)": _num(2),
                "Confiança": _num(2),
                "E (m)": _num(2),
                "N (m)": _num(2),
                "Severidade": lambda s: D.ROTULOS_SEVERIDADE.get(s, s),
            }
        ).map(
            lambda s: f"color: {D.CORES_SEVERIDADE.get(s, 'inherit')}; font-weight: 600",
            subset=["Severidade"],
        )
        st.dataframe(estilo, hide_index=True, width="stretch", height=300)


def _downloads(det, seg_f, nome: str) -> None:
    c = st.columns(3)
    c[0].download_button(
        "Baixar CSV",
        D.csv_bytes(det),
        f"{nome}_buracos.csv",
        "text/csv",
        width="stretch",
    )
    c[1].download_button(
        "Baixar XLSX",
        D.xlsx_bytes(det, seg_f),
        f"{nome}_buracos.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
    c[2].download_button(
        "Baixar GeoJSON",
        D.geojson_bytes(det),
        f"{nome}_buracos.geojson",
        "application/geo+json",
        width="stretch",
    )


def main() -> None:
    st.title("PaviScan")
    st.caption("Buracos em pavimento a partir de ortofoto: um retrato do trecho na data do voo.")

    runs = D.listar_runs(PASTA_RUNS)
    _processar_nova()
    if not runs:
        st.info(
            f"Nenhum levantamento em `{PASTA_RUNS}`. Processe uma imagem acima ou rode "
            "`paviscan run --orto X.tif --pista pista.geojson --saida runs/nome`."
        )
        return

    nomes = [r.name for r in runs]
    escolhido = st.session_state.get("run_escolhido")
    idx = nomes.index(escolhido) if escolhido in nomes else 0
    if len(runs) > 1:
        nome = st.sidebar.selectbox("Levantamento", nomes, index=idx)
    else:
        nome = nomes[0]
        st.sidebar.markdown(f"**Levantamento:** {nome}")
    if st.session_state.get("_run_atual") != nome:  # trocou de levantamento: zera os filtros
        for k in ("f_area", "f_sev", "f_conf", "f_seg"):
            st.session_state.pop(k, None)
        st.session_state["_run_atual"] = nome
    run = PASTA_RUNS / nome

    det_todos, seg, resumo = _carregar(str(run), _versao(run))
    args = _filtros(det_todos, seg)
    det = D.filtrar(det_todos, **args)
    seg_f = D.por_segmento(det, seg)

    # com filtro de segmento, % e buracos/100 m sao relativos aos segmentos escolhidos
    seg_base = seg[seg["segmento"].isin(args["segmentos"])] if "segmentos" in args else seg
    _indicadores(D.resumir(det, seg_base), len(det_todos), bool(args))
    if det_todos.empty:
        st.success("Nenhum buraco detectado neste trecho.")
    elif det.empty:
        st.warning("Nenhum buraco atende aos filtros. Use **Limpar filtros** na barra lateral.")

    mostrar_seg = st.toggle("Mostrar segmentos coloridos pela % afetada", value=False)
    _mapa(run, det, seg_f, resumo, mostrar_seg)
    if not det.empty:
        _graficos(det, seg_f)
        _ranking_e_tabela(det, seg_f)
        _downloads(det, seg_f, nome)

    st.markdown("---")
    st.caption(
        f"Detector {resumo.get('detector')} {resumo.get('versao')} · "
        f"GSD {D.fmt(100 * resumo['gsd_m'], 1)} cm · pista de {D.fmt(D.comprimento_m(seg), 0)} m "
        f"em {len(seg)} segmentos · SRC {resumo.get('src', '')}"
    )


main()
