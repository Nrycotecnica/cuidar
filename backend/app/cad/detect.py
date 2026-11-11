"""Identificação heurística de elementos em plantas (paredes, pilares, máquinas,
contorno do ambiente e pé-direito).

Os resultados são SUGESTÕES com nível de confiança e precisam ser revisados
pelo usuário (todos são editáveis no visualizador). Coordenadas devolvidas em
METROS, já aplicada a escala informada.
"""

from __future__ import annotations

import re

from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from .dxf_import import area_poligono

RE_PILAR = re.compile(r"PILAR|COLUN|COLUMN|PIL\b|ESTRUT", re.I)
RE_PAREDE = re.compile(r"PARED|WALL|ALVEN|MURO|ARQ", re.I)
RE_MAQ = re.compile(r"MAQ|M[ÁA]QUIN|EQUIP|MACH|LAYOUT", re.I)
RE_PD = re.compile(r"(P[ÉE][- ]?DIREITO|PD)\s*[=:]?\s*([0-9]+(?:[.,][0-9]+)?)\s*(m|cm|mm)?", re.I)


def _pts(flat, k):
    return [[round(x * k, 4), round(y * k, 4)] for x, y in zip(flat[0::2], flat[1::2])]


def detectar(geo: dict, escala_m: float | None) -> dict:
    if not escala_m:
        return {"pilares": [], "paredes": [], "maquinas": [], "contorno": None, "pe_direito_m": None,
                "avisos": ["Escala não definida: identificação automática adiada até a calibração."]}
    k = escala_m
    camadas = [c["nome"] for c in geo.get("camadas", [])]
    pilares, maquinas, paredes, fechados = [], [], [], []
    for e in geo.get("entidades", []):
        nome_camada = camadas[e["l"]] if e.get("l") is not None and e["l"] < len(camadas) else ""
        if e["t"] == "P" and e.get("c") and len(e["p"]) >= 6:
            area = area_poligono(e["p"]) * k * k
            pts = _pts(e["p"], k)
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            w, h = max(xs) - min(xs), max(ys) - min(ys)
            fechados.append((area, pts, nome_camada))
            if RE_PILAR.search(nome_camada) or (0.05 <= area <= 1.5 and max(w, h) <= 1.5 and min(w, h) >= 0.12 and max(w, h) / max(min(w, h), 1e-6) <= 3):
                conf = 0.9 if RE_PILAR.search(nome_camada) else 0.5
                pilares.append({"pontos": pts, "confianca": conf, "camada": nome_camada})
            elif RE_MAQ.search(nome_camada) and area > 0.2:
                maquinas.append({"pontos": pts, "confianca": 0.7, "camada": nome_camada, "nome": None})
        elif e["t"] == "C" and RE_PILAR.search(nome_camada) and e["r"] * k <= 1.0:
            cx, cy, r = e["c"][0] * k, e["c"][1] * k, e["r"] * k
            poly = Point(cx, cy).buffer(r, quad_segs=4) if r > 0 else None
            if poly is not None:
                pts = [[round(x, 4), round(y, 4)] for x, y in poly.exterior.coords[:-1]]
                pilares.append({"pontos": pts, "confianca": 0.8, "camada": nome_camada})
        elif e["t"] in ("L", "P") and RE_PAREDE.search(nome_camada):
            pts = _pts(e["p"], k)
            if len(pts) >= 2:
                paredes.append({"pontos": pts, "confianca": 0.7, "camada": nome_camada})

    # contorno: maior polígono fechado com área razoável
    contorno = None
    grandes = sorted((f for f in fechados if f[0] > 4.0), key=lambda f: -f[0])
    if grandes:
        contorno = {"pontos": grandes[0][1], "confianca": 0.6, "area_m2": round(grandes[0][0], 2)}
    elif paredes:
        try:
            u = unary_union([LineString(p["pontos"]) for p in paredes])
            env = u.envelope
            if env.geom_type == "Polygon":
                contorno = {"pontos": [[round(x, 4), round(y, 4)] for x, y in env.exterior.coords[:-1]],
                            "confianca": 0.3, "area_m2": round(env.area, 2)}
        except Exception:
            pass
    if contorno is None and geo.get("extensao"):
        x0, y0, x1, y1 = (v * k for v in geo["extensao"])
        contorno = {"pontos": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], "confianca": 0.2,
                    "area_m2": round((x1 - x0) * (y1 - y0), 2)}

    pe_direito = None
    for e in geo.get("entidades", []):
        if e["t"] == "T" and e.get("s"):
            m = RE_PD.search(e["s"])
            if m:
                v = float(m.group(2).replace(",", "."))
                un = (m.group(3) or "m").lower()
                v = v / 1000 if un == "mm" else v / 100 if un == "cm" else v
                if 1.5 <= v <= 40:
                    pe_direito = {"valor_m": v, "texto": e["s"], "confianca": 0.6}
                    break

    # evita pilares duplicados dentro de máquinas grandes
    return {
        "pilares": pilares[:2000],
        "paredes": paredes[:5000],
        "maquinas": maquinas[:2000],
        "contorno": contorno,
        "pe_direito_m": pe_direito,
        "avisos": ["Elementos identificados automaticamente — revise antes de usar no roteamento."],
    }
