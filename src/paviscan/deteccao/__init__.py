"""Detectores de buraco. O resto do pipeline so conhece `criar` e o contrato de `base`."""

from __future__ import annotations

from paviscan.deteccao.base import Deteccao, Detector

__all__ = ["Deteccao", "Detector", "criar"]


def criar(nome: str, params: dict) -> Detector:
    """Instancia o detector `nome` com a secao de mesmo nome de params.yaml."""
    if nome == "classico":
        from paviscan.deteccao.classico import DetectorClassico

        return DetectorClassico(params["classico"])
    raise ValueError(f"detector desconhecido: {nome}")
