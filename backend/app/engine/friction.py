"""Perda por atrito em dutos — equação de Darcy-Weisbach com fator de atrito
de Colebrook-White (resolvido iterativamente) e diâmetro hidráulico para
seções retangulares."""

from __future__ import annotations

import math

RE_LAMINAR = 2300.0
RE_TURBULENTO = 4000.0


def reynolds(rho: float, v: float, d_h: float, mu: float) -> float:
    return rho * abs(v) * d_h / mu


def fator_atrito_swamee_jain(re: float, rugosidade_rel: float) -> float:
    return 0.25 / (math.log10(rugosidade_rel / 3.7 + 5.74 / re**0.9)) ** 2


def fator_atrito_colebrook(re: float, rugosidade_rel: float, tol: float = 1e-12, max_iter: int = 100) -> float:
    """1/√f = -2·log10(ε/(3,7·D) + 2,51/(Re·√f)).

    Para Re < 2300 usa-se f = 64/Re (laminar)."""
    if re <= 0:
        raise ValueError("Número de Reynolds deve ser positivo")
    if re < RE_LAMINAR:
        return 64.0 / re
    f = fator_atrito_swamee_jain(max(re, 5000.0), rugosidade_rel)
    x = 1.0 / math.sqrt(f)
    for _ in range(max_iter):
        x_new = -2.0 * math.log10(rugosidade_rel / 3.7 + 2.51 * x / re)
        if abs(x_new - x) < tol:
            x = x_new
            break
        x = x_new
    return 1.0 / (x * x)


def diametro_hidraulico_retangular(a_m: float, b_m: float) -> float:
    """Dh = 4·A/P = 2ab/(a+b)."""
    return 2.0 * a_m * b_m / (a_m + b_m)


def diametro_equivalente_huebscher(a_m: float, b_m: float) -> float:
    """De = 1,30·(ab)^0,625/(a+b)^0,25 — diâmetro circular de mesma perda e vazão."""
    return 1.30 * (a_m * b_m) ** 0.625 / (a_m + b_m) ** 0.25


def perda_atrito(f: float, comprimento_m: float, d_h: float, vp_pa: float) -> float:
    """ΔP = f·(L/Dh)·VP [Pa]."""
    return f * comprimento_m / d_h * vp_pa
