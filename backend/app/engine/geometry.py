"""Utilitários geométricos 2D simples (coordenadas em metros)."""

from __future__ import annotations

import math


def comprimento_polilinha(pts: list[list[float]]) -> float:
    return sum(math.dist(pts[i - 1], pts[i]) for i in range(1, len(pts)))


def direcao(a, b) -> tuple[float, float] | None:
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    if n < 1e-9:
        return None
    return dx / n, dy / n


def angulo_entre(d1, d2) -> float:
    """Ângulo de desvio (0° = mesma direção) em graus."""
    c = max(-1.0, min(1.0, d1[0] * d2[0] + d1[1] * d2[1]))
    return math.degrees(math.acos(c))


def angulos_internos(pts: list[list[float]], tol_graus: float = 1.0) -> list[float]:
    """Desvios de direção nos vértices internos de uma polilinha."""
    pts = limpar(pts)
    angs = []
    for i in range(1, len(pts) - 1):
        d1 = direcao(pts[i - 1], pts[i])
        d2 = direcao(pts[i], pts[i + 1])
        if d1 and d2:
            a = angulo_entre(d1, d2)
            if a > tol_graus:
                angs.append(a)
    return angs


def limpar(pts: list[list[float]]) -> list[list[float]]:
    out: list[list[float]] = []
    for p in pts:
        if not out or math.dist(out[-1], p) > 1e-9:
            out.append([float(p[0]), float(p[1])])
    return out
