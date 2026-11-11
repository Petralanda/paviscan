"""Detector classico: anomalia escura local com limiar robusto e filtros de forma em metros."""

from __future__ import annotations

import cv2
import numpy as np
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.measure import label, regionprops
from skimage.segmentation import watershed

from paviscan.deteccao.base import Deteccao

_LADO_FUNDO_PX = 31  # tamanho do filtro de mediana depois de reduzir a imagem


def _disco(raio_px: float) -> np.ndarray:
    r = max(1, int(round(raio_px)))
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def fundo_local(cinza: np.ndarray, janela_px: float) -> np.ndarray:
    """Mediana numa janela de `janela_px`, calculada em versao reduzida e ampliada de volta."""
    h, w = cinza.shape
    f = max(1, int(janela_px // _LADO_FUNDO_PX))
    pequena = cv2.resize(cinza, (max(1, w // f), max(1, h // f)), interpolation=cv2.INTER_AREA)
    k = max(3, int(round(janela_px / f)) | 1)
    med = cv2.medianBlur(np.clip(pequena, 0, 255).astype(np.uint8), k)
    return cv2.resize(med, (w, h), interpolation=cv2.INTER_LINEAR).astype(np.float32)


def limiar_robusto(valores: np.ndarray, k_mad: float, piso: float) -> float:
    """max(piso, mediana + k x MAD). Nao divide a imagem em duas classes a forca, como o Otsu."""
    med = float(np.median(valores))
    mad = float(np.median(np.abs(valores - med)))
    return max(piso, med + k_mad * mad)


class DetectorClassico:
    nome = "classico"
    versao = "0.2.0"

    def __init__(self, params: dict):
        self.p = dict(params)

    def _separar(self, reg_mask: np.ndarray, gsd: float) -> list[np.ndarray]:
        """Watershed na distancia so quando a regiao tem mais de um pico claro."""
        dist = ndi.distance_transform_edt(reg_mask)
        sep = max(1, int(round(self.p["separacao_min_m"] / gsd)))
        picos = peak_local_max(
            dist, min_distance=sep, labels=reg_mask.astype(int), exclude_border=False
        )
        if len(picos) < 2:
            return [reg_mask]
        marcas = np.zeros(reg_mask.shape, np.int32)
        for i, (r, c) in enumerate(picos, 1):
            marcas[r, c] = i
        rot = watershed(-dist, marcas, mask=reg_mask)
        return [rot == i for i in range(1, rot.max() + 1) if (rot == i).any()]

    def _forma_ok(self, m: np.ndarray, gsd: float) -> tuple[bool, object]:
        props = regionprops(m.astype(np.uint8))
        if not props:
            return False, None
        pr = props[0]
        area_m2 = pr.area * gsd * gsd
        if not (self.p["area_min_m2"] <= area_m2 <= self.p["area_max_m2"]):
            return False, pr
        if pr.solidity < self.p["solidez_min"]:
            return False, pr
        menor = max(pr.axis_minor_length, 1e-6)
        if pr.axis_major_length / menor > self.p["alongamento_max"]:
            return False, pr
        return True, pr

    def _confianca(self, m: np.ndarray, anom: np.ndarray, grad_m: np.ndarray) -> float:
        borda = m & ~cv2.erode(m.astype(np.uint8), _disco(1)).astype(bool)
        contraste = float(anom[m].mean())
        nitidez = float(grad_m[borda].mean()) if borda.any() else 0.0
        c1 = min(1.0, contraste / self.p["conf_contraste_ref"])
        c2 = min(1.0, nitidez / self.p["conf_borda_ref"])
        return float(np.clip(0.5 * c1 + 0.5 * c2, 0.0, 1.0))

    def _colado_a_objeto_claro(
        self, m: np.ndarray, cinza: np.ndarray, valida: np.ndarray, asfalto: float, gsd: float
    ) -> bool:
        """True se o anel em volta da regiao e em boa parte muito mais claro que o asfalto.

        E o caso de para-brisa e sombra de veiculo: escuro colado a lataria clara. Buraco,
        mancha e remendo ficam cercados de asfalto. Faixa pintada e fina e ocupa pouco do anel.
        """
        raio = self.p["anel_claro_m"] / gsd
        if raio < 1:
            return False
        r = int(np.ceil(raio)) + 1
        lin, col = np.nonzero(m)
        r0, r1 = max(0, lin.min() - r), min(m.shape[0], lin.max() + r + 1)
        c0, c1 = max(0, col.min() - r), min(m.shape[1], col.max() + r + 1)
        sub = m[r0:r1, c0:c1].astype(np.uint8)
        anel = cv2.dilate(sub, _disco(raio)).astype(bool) & ~sub.astype(bool)
        anel &= valida[r0:r1, c0:c1]
        if not anel.any():
            return False
        claros = cinza[r0:r1, c0:c1][anel] > asfalto + self.p["claro_delta"]
        return float(claros.mean()) > self.p["claro_frac_max"]

    def detectar(self, img: np.ndarray, gsd_m: float, valida: np.ndarray) -> list[Deteccao]:
        p, gsd = self.p, float(gsd_m)
        valida = valida.astype(bool)
        if valida.sum() * gsd * gsd < p["area_min_m2"] * 4:
            return []

        cinza = img.astype(np.float32).mean(axis=2)
        sigma = p["sigma_m"] / gsd
        if sigma >= 0.3:
            cinza = cv2.GaussianBlur(cinza, (0, 0), sigma)

        # fora da pista vira asfalto tipico, para nao puxar o fundo
        preenchida = np.where(valida, cinza, np.median(cinza[valida])).astype(np.float32)
        fundo = fundo_local(preenchida, p["janela_fundo_m"] / gsd)
        anom = fundo - preenchida

        nucleo = valida.copy()
        margem = p["margem_borda_m"] / gsd
        if margem >= 0.5:
            nucleo = cv2.erode(valida.astype(np.uint8), _disco(margem)).astype(bool)
        if not nucleo.any():
            return []
        anom[~nucleo] = 0

        lim = limiar_robusto(anom[nucleo], p["k_mad"], p["contraste_min"])
        binaria = (anom > lim).astype(np.uint8)
        el = _disco(p["elemento_m"] / gsd / 2)
        binaria = cv2.morphologyEx(binaria, cv2.MORPH_OPEN, el)
        binaria = cv2.morphologyEx(binaria, cv2.MORPH_CLOSE, el)
        binaria = ndi.binary_fill_holes(binaria) & nucleo

        asfalto = float(np.median(preenchida[nucleo]))
        gy, gx = np.gradient(preenchida)
        grad_m = np.hypot(gx, gy) / gsd  # niveis de cinza por metro

        saida: list[Deteccao] = []
        rotulos = label(binaria, connectivity=2)
        for reg in regionprops(rotulos):
            r0, c0, r1, c1 = reg.bbox
            sub = rotulos[r0:r1, c0:c1] == reg.label
            ok, pr = self._forma_ok(sub, gsd)
            pedacos = [sub]
            if not ok and pr is not None and pr.solidity < p["solidez_min"]:
                pedacos = self._separar(sub, gsd)
                if len(pedacos) < 2:
                    continue
            elif not ok:
                continue
            for ped in pedacos:
                if len(pedacos) > 1 and not self._forma_ok(ped, gsd)[0]:
                    continue
                m = np.zeros(valida.shape, bool)
                m[r0:r1, c0:c1] = ped
                if self._colado_a_objeto_claro(m, preenchida, valida, asfalto, gsd):
                    continue
                saida.append(Deteccao(mascara=m, confianca=self._confianca(m, anom, grad_m)))
        return saida
