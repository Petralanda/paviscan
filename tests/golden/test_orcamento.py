"""M3: orcamento fecha com a conta feita a mao."""

import json

import geopandas as gpd
import pandas as pd


def test_orcamento_consistente(saida_cena):
    orc = pd.read_csv(saida_cena / "orcamento.csv")
    for col in ("id", "opcao", "servico", "unidade", "quantidade", "preco_unit", "custo"):
        assert col in orc.columns, col
    assert ((orc["quantidade"] * orc["preco_unit"] - orc["custo"]).abs() < 0.01).all()
    assert set(orc["opcao"]) >= {"A", "B"}


def test_todo_defeito_tem_opcao_a_e_b(saida_cena):
    det = gpd.read_file(saida_cena / "defeitos.geojson")
    orc = pd.read_csv(saida_cena / "orcamento.csv")
    for op in ("A", "B"):
        assert set(orc.loc[orc["opcao"] == op, "id"]) == set(det["id"]), op


def test_b_custa_mais_que_a_e_resumo_bate(saida_cena):
    orc = pd.read_csv(saida_cena / "orcamento.csv")
    tot = orc.groupby("opcao")["custo"].sum()
    assert tot["B"] > tot["A"] > 0
    r = json.loads((saida_cena / "resumo.json").read_text())
    for op in ("A", "B"):
        assert abs(r["custo_por_opcao"][op] - tot[op]) < 0.01
