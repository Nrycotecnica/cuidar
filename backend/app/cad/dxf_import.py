"""Importação de DXF com ezdxf.

Observação: o ezdxf lê apenas DXF. Arquivos DWG precisam ser convertidos
antes (ver ``dwg.py``).
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import Any

import ezdxf
from ezdxf import path as ezpath
from ezdxf import recover

# $INSUNITS → metros
INSUNITS_M = {1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0, 14: 0.1}
INSUNITS_NOME = {0: "sem unidade", 1: "polegada", 2: "pé", 4: "mm", 5: "cm", 6: "m", 14: "dm"}
MAX_ENTIDADES = 300_000


class ImportacaoErro(ValueError):
    pass


def _r(x: float) -> float:
    return round(float(x), 4)


def ler_dxf(dados: bytes) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "entrada.dxf"
        p.write_bytes(dados)
        try:
            doc, auditor = recover.readfile(str(p))
        except (IOError, ezdxf.DXFStructureError) as e:
            raise ImportacaoErro(f"Arquivo DXF inválido ou corrompido: {e}") from e
    return extrair(doc, auditor)


def extrair(doc, auditor=None) -> dict[str, Any]:
    msp = doc.modelspace()
    camadas: list[dict] = []
    idx: dict[str, int] = {}

    def li(nome: str) -> int:
        if nome not in idx:
            idx[nome] = len(camadas)
            cor = 7
            try:
                cor = doc.layers.get(nome).dxf.color
            except Exception:
                pass
            camadas.append({"nome": nome, "cor": cor})
        return idx[nome]

    ents: list[dict] = []
    avisos: list[str] = []
    ignorados: dict[str, int] = {}

    def add(e, depth=0):
        if len(ents) >= MAX_ENTIDADES:
            return
        t = e.dxftype()
        layer = e.dxf.get("layer", "0")
        try:
            if t == "LINE":
                s, f = e.dxf.start, e.dxf.end
                ents.append({"t": "L", "l": li(layer), "p": [_r(s.x), _r(s.y), _r(f.x), _r(f.y)]})
            elif t in ("LWPOLYLINE", "POLYLINE", "SPLINE", "ELLIPSE"):
                if t == "POLYLINE" and (e.is_poly_face_mesh or e.is_polygon_mesh):
                    ignorados[t] = ignorados.get(t, 0) + 1
                    return
                pth = ezpath.make_path(e)
                pts = list(pth.flattening(distance=0.01 if t != "SPLINE" else 0.05))
                if len(pts) >= 2:
                    flat = []
                    for v in pts:
                        flat += [_r(v.x), _r(v.y)]
                    closed = bool(getattr(e, "closed", False) or getattr(e, "is_closed", False))
                    if not closed and len(pts) > 2 and pts[0].isclose(pts[-1]):
                        closed = True
                    ents.append({"t": "P", "l": li(layer), "p": flat, "c": closed})
            elif t == "CIRCLE":
                c = e.dxf.center
                ents.append({"t": "C", "l": li(layer), "c": [_r(c.x), _r(c.y)], "r": _r(e.dxf.radius)})
            elif t == "ARC":
                c = e.dxf.center
                ents.append({"t": "A", "l": li(layer), "c": [_r(c.x), _r(c.y)], "r": _r(e.dxf.radius),
                             "a0": _r(e.dxf.start_angle), "a1": _r(e.dxf.end_angle)})
            elif t in ("TEXT", "ATTRIB"):
                ins = e.dxf.insert
                ents.append({"t": "T", "l": li(layer), "p": [_r(ins.x), _r(ins.y)], "h": _r(e.dxf.get("height", 1.0)),
                             "s": e.dxf.text, "r": _r(e.dxf.get("rotation", 0.0))})
            elif t == "MTEXT":
                ins = e.dxf.insert
                ents.append({"t": "T", "l": li(layer), "p": [_r(ins.x), _r(ins.y)], "h": _r(e.dxf.get("char_height", 1.0)),
                             "s": e.plain_text(), "r": _r(e.dxf.get("rotation", 0.0))})
            elif t == "INSERT":
                if depth > 8:
                    return
                for ve in e.virtual_entities():
                    add(ve, depth + 1)
                for a in e.attribs:
                    add(a, depth + 1)
            elif t == "DIMENSION":
                try:
                    for ve in e.virtual_entities():
                        add(ve, depth + 1)
                except Exception:
                    ignorados[t] = ignorados.get(t, 0) + 1
            else:
                ignorados[t] = ignorados.get(t, 0) + 1
        except Exception as ex:  # entidade problemática não derruba a importação
            ignorados[f"{t} (erro)"] = ignorados.get(f"{t} (erro)", 0) + 1
            if len(avisos) < 20:
                avisos.append(f"Entidade {t} ignorada: {ex}")

    for e in msp:
        add(e)
    if len(ents) >= MAX_ENTIDADES:
        avisos.append(f"Limite de {MAX_ENTIDADES} entidades atingido; o restante foi ignorado.")

    insunits = int(doc.header.get("$INSUNITS", 0) or 0)
    escala = INSUNITS_M.get(insunits)
    ext = extensao(ents)
    if escala is None:
        avisos.append("O DXF não declara unidade ($INSUNITS). Confirme a unidade/escala antes de usar as medidas.")
    if auditor is not None and auditor.has_errors:
        avisos.append(f"O arquivo apresentou {len(auditor.errors)} erro(s) estrutural(is) corrigidos na leitura.")
    return {
        "entidades": ents,
        "camadas": camadas,
        "extensao": ext,
        "insunits": insunits,
        "unidade": INSUNITS_NOME.get(insunits, f"código {insunits}"),
        "escala_m_por_unidade": escala,
        "versao_dxf": doc.dxfversion,
        "ignorados": ignorados,
        "avisos": avisos,
    }


def extensao(ents: list[dict]) -> list[float] | None:
    xs, ys = [], []
    for e in ents:
        if e["t"] == "L" or e["t"] == "P":
            xs += e["p"][0::2]
            ys += e["p"][1::2]
        elif e["t"] in ("C", "A"):
            xs += [e["c"][0] - e["r"], e["c"][0] + e["r"]]
            ys += [e["c"][1] - e["r"], e["c"][1] + e["r"]]
        elif e["t"] == "T":
            xs.append(e["p"][0])
            ys.append(e["p"][1])
    if not xs:
        return None
    return [min(xs), min(ys), max(xs), max(ys)]


def area_poligono(flat: list[float]) -> float:
    pts = list(zip(flat[0::2], flat[1::2]))
    a = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        a += x1 * y2 - x2 * y1
    return abs(a) / 2


def comprimento_flat(flat: list[float]) -> float:
    pts = list(zip(flat[0::2], flat[1::2]))
    return sum(math.dist(pts[i - 1], pts[i]) for i in range(1, len(pts)))
