"""Conversões de unidades com fatores exatos ou de definição.

Unidades internas do motor (SI): m, m², m³/s, Pa, kg/m³, K, W.
"""

from __future__ import annotations

# Fatores de definição
G0 = 9.80665  # m/s² (gravidade padrão, definição)
MMH2O_PA = G0  # 1 mmH2O (a 4 °C, convencional) = 9,80665 Pa
INH2O_PA = 249.08891  # 1 inH2O convencional (25,4 mmH2O) = 249,08891 Pa
FT3_M3 = 0.028316846592  # definição (0,3048³)
CFM_M3S = FT3_M3 / 60.0
FPM_MS = 0.3048 / 60.0
IN_MM = 25.4
HP_W = 745.69987158227022  # horsepower mecânico (550 ft·lbf/s)
CV_W = 735.49875  # cavalo-vapor métrico (75 kgf·m/s)
ZERO_C_K = 273.15


def m3h_to_m3s(q: float) -> float:
    return q / 3600.0


def m3s_to_m3h(q: float) -> float:
    return q * 3600.0


def cfm_to_m3s(q: float) -> float:
    return q * CFM_M3S


def m3s_to_cfm(q: float) -> float:
    return q / CFM_M3S


def mmh2o_to_pa(p: float) -> float:
    return p * MMH2O_PA


def pa_to_mmh2o(p: float) -> float:
    return p / MMH2O_PA


def inh2o_to_pa(p: float) -> float:
    return p * INH2O_PA


def c_to_k(t: float) -> float:
    return t + ZERO_C_K


def mm_to_m(x: float) -> float:
    return x / 1000.0


def m_to_mm(x: float) -> float:
    return x * 1000.0


def cv_to_kw(p: float) -> float:
    return p * CV_W / 1000.0


def hp_to_kw(p: float) -> float:
    return p * HP_W / 1000.0


# Tabelas para conversão genérica usadas na importação de catálogos
FLOW_TO_M3S = {
    "m3/s": 1.0,
    "m3/h": 1.0 / 3600.0,
    "m3/min": 1.0 / 60.0,
    "l/s": 1.0e-3,
    "cfm": CFM_M3S,
}
PRESSURE_TO_PA = {
    "pa": 1.0,
    "kpa": 1000.0,
    "mmh2o": MMH2O_PA,
    "mmca": MMH2O_PA,
    "inh2o": INH2O_PA,
}
POWER_TO_W = {"w": 1.0, "kw": 1000.0, "cv": CV_W, "hp": HP_W}
LENGTH_TO_M = {"mm": 1e-3, "cm": 1e-2, "m": 1.0, "in": 0.0254, "ft": 0.3048}


def convert(value: float, unit: str, table: dict[str, float]) -> float:
    key = unit.strip().lower().replace("³", "3").replace(" ", "")
    if key not in table:
        raise ValueError(f"Unidade não suportada: {unit!r}. Aceitas: {sorted(table)}")
    return value * table[key]
