"""Propriedades do ar seco (hipótese: ar seco, gás ideal)."""

from __future__ import annotations

import math

from .units import c_to_k

R_AIR = 287.05  # J/(kg·K) constante do ar seco
P_STD = 101325.0  # Pa
RHO_STD = 1.2  # kg/m³ — referência usual de catálogos (ar padrão ~20 °C, nível do mar)


def pressao_atmosferica(altitude_m: float) -> float:
    """Pressão barométrica pela atmosfera padrão ISA (troposfera, h < 11 km)."""
    if altitude_m < -500 or altitude_m > 11000:
        raise ValueError("Altitude fora da faixa válida do modelo ISA troposférico")
    return P_STD * (1.0 - 2.25577e-5 * altitude_m) ** 5.25588


def densidade(temperatura_c: float, altitude_m: float = 0.0) -> float:
    """ρ = p / (R·T)."""
    t = c_to_k(temperatura_c)
    if t <= 0:
        raise ValueError("Temperatura absoluta inválida")
    return pressao_atmosferica(altitude_m) / (R_AIR * t)


def viscosidade_dinamica(temperatura_c: float) -> float:
    """Lei de Sutherland para o ar: μ = 1,458e-6·T^1,5/(T+110,4) [Pa·s]."""
    t = c_to_k(temperatura_c)
    return 1.458e-6 * t**1.5 / (t + 110.4)


def pressao_dinamica(rho: float, v: float) -> float:
    """VP = ρ·v²/2 [Pa]."""
    return 0.5 * rho * v * v


def velocidade(q_m3s: float, area_m2: float) -> float:
    if area_m2 <= 0:
        raise ValueError("Área deve ser positiva")
    return q_m3s / area_m2


def area_circular(d_m: float) -> float:
    return math.pi * d_m * d_m / 4.0
