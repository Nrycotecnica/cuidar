"""Geração de desenho 2D editável em DXF (compatível com o fluxo do AutoCAD).

* Unidades: milímetros ($INSUNITS = 4), escala 1:1 no espaço do modelo.
* Camadas padronizadas (VENT-*, ARQ-*, REF-*), blocos com atributos para
  equipamentos, cotas associadas a um estilo próprio, textos e legenda.
* Nada é rasterizado: todas as entidades permanecem editáveis.
"""

from __future__ import annotations

import math
import tempfile
from datetime import date
from pathlib import Path

import ezdxf
from ezdxf import bbox, units
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import LineString

from ..engine.trace import fmt

CAMADAS = {
    "VENT-DUTO": (1, "CONTINUOUS"),
    "VENT-DUTO-EIXO": (8, "CENTER"),
    "VENT-CAPTOR": (3, "CONTINUOUS"),
    "VENT-EXAUSTOR": (5, "CONTINUOUS"),
    "VENT-FILTRO": (6, "CONTINUOUS"),
    "VENT-ACESSORIO": (4, "CONTINUOUS"),
    "VENT-COTA": (2, "CONTINUOUS"),
    "VENT-TEXTO": (7, "CONTINUOUS"),
    "VENT-LEGENDA": (7, "CONTINUOUS"),
    "ARQ-CONTORNO": (8, "CONTINUOUS"),
    "ARQ-PILAR": (8, "CONTINUOUS"),
    "ARQ-OBSTACULO": (9, "DASHED"),
}

MM = 1000.0


def _bloco_captor(doc):
    b = doc.blocks.new("VENT_CAPTOR")
    b.add_lwpolyline([(-300, -300), (300, -300), (300, 300), (-300, 300)], close=True)
    b.add_line((-300, -300), (300, 300))
    b.add_line((-300, 300), (300, -300))
    b.add_attdef("TAG", (0, 380), dxfattribs={"height": 150})
    b.add_attdef("VAZAO", (0, -520), dxfattribs={"height": 120})


def _bloco_exaustor(doc):
    b = doc.blocks.new("VENT_EXAUSTOR")
    b.add_circle((0, 0), 450)
    b.add_lwpolyline([(0, 450), (650, 450), (650, 150), (380, 150)])
    b.add_circle((0, 0), 120)
    b.add_attdef("TAG", (0, 650), dxfattribs={"height": 180})
    b.add_attdef("MODELO", (0, -700), dxfattribs={"height": 140})
    b.add_attdef("VAZAO", (0, -900), dxfattribs={"height": 120})
    b.add_attdef("PRESSAO", (0, -1080), dxfattribs={"height": 120})


def _bloco_filtro(doc):
    b = doc.blocks.new("VENT_FILTRO")
    b.add_lwpolyline([(-600, -500), (600, -500), (600, 500), (-600, 500)], close=True)
    for x in (-400, -200, 0, 200, 400):
        b.add_line((x, -450), (x, 450))
    b.add_attdef("TAG", (0, 650), dxfattribs={"height": 160})
    b.add_attdef("PERDA", (0, -750), dxfattribs={"height": 120})


def _bloco_descarga(doc):
    b = doc.blocks.new("VENT_DESCARGA")
    b.add_circle((0, 0), 300)
    b.add_line((-300, 0), (300, 0))
    b.add_line((0, -300), (0, 300))
    b.add_attdef("TAG", (0, 420), dxfattribs={"height": 140})


def _ponto(p):
    return (p[0] * MM, p[1] * MM)


def gerar_dxf(projeto: dict, rede: dict, resultado: dict | None, ambiente: dict | None = None,
              referencia: dict | None = None, aprovado: bool = False, demonstrativo: bool = False) -> bytes:
    doc = ezdxf.new("R2010", setup=True)
    doc.units = units.MM
    doc.header["$MEASUREMENT"] = 1
    doc.header["$LUNITS"] = 2
    doc.header["$INSUNITS"] = 4
    for nome, (cor, lt) in CAMADAS.items():
        if lt not in doc.linetypes:
            lt = "CONTINUOUS"
        doc.layers.add(nome, color=cor, linetype=lt)
    if "VENT" not in doc.dimstyles:
        doc.dimstyles.new("VENT", dxfattribs={
            "dimtxt": 150, "dimasz": 120, "dimexe": 60, "dimexo": 60, "dimgap": 40,
            "dimdec": 0, "dimlunit": 2, "dimtad": 1, "dimclrd": 2, "dimclre": 2, "dimclrt": 2,
        })
    _bloco_captor(doc)
    _bloco_exaustor(doc)
    _bloco_filtro(doc)
    _bloco_descarga(doc)
    msp = doc.modelspace()

    # Referência arquitetônica importada (já em metros)
    if referencia:
        k = referencia["escala_m_por_unidade"] * MM
        camadas_ref = referencia.get("camadas") or []
        for e in referencia.get("entidades", []):
            nome = camadas_ref[e["l"]]["nome"] if e.get("l") is not None and e["l"] < len(camadas_ref) else "0"
            lay = ("REF-" + "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in nome))[:60]
            if lay not in doc.layers:
                doc.layers.add(lay, color=8)
            at = {"layer": lay}
            if e["t"] == "L":
                p = e["p"]
                msp.add_line((p[0] * k, p[1] * k), (p[2] * k, p[3] * k), dxfattribs=at)
            elif e["t"] == "P":
                pts = [(x * k, y * k) for x, y in zip(e["p"][0::2], e["p"][1::2])]
                msp.add_lwpolyline(pts, close=bool(e.get("c")), dxfattribs=at)
            elif e["t"] == "C":
                msp.add_circle((e["c"][0] * k, e["c"][1] * k), e["r"] * k, dxfattribs=at)
            elif e["t"] == "A":
                msp.add_arc((e["c"][0] * k, e["c"][1] * k), e["r"] * k, e["a0"], e["a1"], dxfattribs=at)
            elif e["t"] == "T" and e.get("s"):
                msp.add_text(e["s"][:250], height=max(e.get("h", 1) * k, 1), dxfattribs={**at, "insert": (e["p"][0] * k, e["p"][1] * k), "rotation": e.get("r", 0)})

    amb = ambiente or {}
    if amb.get("contorno"):
        msp.add_lwpolyline([_ponto(p) for p in amb["contorno"]], close=True, dxfattribs={"layer": "ARQ-CONTORNO"})
    for pil in amb.get("pilares", []):
        msp.add_lwpolyline([_ponto(p) for p in pil["pontos"]], close=True, dxfattribs={"layer": "ARQ-PILAR"})
    for ob in amb.get("obstaculos", []):
        msp.add_lwpolyline([_ponto(p) for p in ob["pontos"]], close=True, dxfattribs={"layer": "ARQ-OBSTACULO"})
        if ob.get("nome"):
            xs = [p[0] for p in ob["pontos"]]
            ys = [p[1] for p in ob["pontos"]]
            msp.add_text(ob["nome"], height=150, dxfattribs={"layer": "ARQ-OBSTACULO"}).set_placement(
                _ponto(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)), align=TextEntityAlignment.MIDDLE_CENTER)

    nos = {n["id"]: n for n in rede.get("nodes", [])}
    trechos = {t["id"]: t for t in (resultado or {}).get("trechos", [])}

    # Dutos
    for s in rede.get("segments", []):
        a, b = nos[s["from"]], nos[s["to"]]
        pts = [[a["x"], a["y"]]] + list(s.get("path") or []) + [[b["x"], b["y"]]]
        t = trechos.get(s["id"], {})
        d_mm = t.get("diametro_mm") or s.get("diametro_mm")
        w_mm = t.get("largura_mm") or s.get("largura_mm")
        larg = (d_mm or w_mm or 200) / 1000.0
        line = LineString(pts)
        if line.length <= 0:
            continue
        msp.add_lwpolyline([_ponto(p) for p in pts], dxfattribs={"layer": "VENT-DUTO-EIXO"})
        contorno = line.buffer(larg / 2, cap_style="flat", join_style="mitre")
        if contorno.geom_type == "Polygon":
            msp.add_lwpolyline([_ponto(p) for p in list(contorno.exterior.coords)[:-1]], close=True, dxfattribs={"layer": "VENT-DUTO"})
        # cotas por trecho reto
        for p0, p1 in zip(pts, pts[1:]):
            comp = math.dist(p0, p1)
            if comp < 0.3:
                continue
            dim = msp.add_aligned_dim(p1=_ponto(p0), p2=_ponto(p1), distance=larg * MM / 2 + 350,
                                      dimstyle="VENT", dxfattribs={"layer": "VENT-COTA"})
            dim.render()
        # rótulo no maior trecho reto
        p0, p1 = max(zip(pts, pts[1:]), key=lambda pp: math.dist(pp[0], pp[1]))
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        ang = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
        if ang > 90 or ang < -90:
            ang += 180
        sec = f"Ø{fmt(d_mm, 0)}" if d_mm else f"{fmt(w_mm or 0, 0)}x{fmt(t.get('altura_mm') or s.get('altura_mm') or 0, 0)}"
        txt = f"{s.get('label') or s['id']} {sec}"
        if t:
            txt += f" - {fmt(t['vazao_m3h'], 0)} m³/h - {fmt(t['velocidade_ms'], 1)} m/s"
        n = math.radians(ang + 90)
        off = larg / 2 + 0.15
        msp.add_text(txt, height=140, rotation=ang, dxfattribs={"layer": "VENT-TEXTO"}).set_placement(
            (mx * MM + math.cos(n) * off * MM * -1, my * MM + math.sin(n) * off * MM * -1), align=TextEntityAlignment.TOP_CENTER)

    res = resultado or {}
    capt_res = {c["id"]: c for c in res.get("captores", [])}
    sel = (res.get("selecao_exaustor") or {}).get("selecionado")
    for n in rede.get("nodes", []):
        pos = _ponto((n["x"], n["y"]))
        tag = n.get("label") or n["id"]
        if n["type"] == "captor":
            q = capt_res.get(n["id"], {}).get("vazao_m3h")
            ref = msp.add_blockref("VENT_CAPTOR", pos, dxfattribs={"layer": "VENT-CAPTOR"})
            ref.add_auto_attribs({"TAG": tag, "VAZAO": f"{fmt(q, 0)} m³/h" if q else "-"})
        elif n["type"] == "exaustor":
            ref = msp.add_blockref("VENT_EXAUSTOR", pos, dxfattribs={"layer": "VENT-EXAUSTOR"})
            ref.add_auto_attribs({
                "TAG": tag,
                "MODELO": sel["nome"] if sel else "A DEFINIR",
                "VAZAO": f"{fmt(res.get('vazao_total_m3h', 0), 0)} m³/h" if res else "-",
                "PRESSAO": f"PT {fmt(res.get('pressao_total_ventilador_pa', 0), 0)} Pa" if res else "-",
            })
        elif n["type"] in ("filtro", "equipamento"):
            perda = next((p["perda_pa"] for p in res.get("perdas_nos", []) if p["id"] == n["id"]), None)
            ref = msp.add_blockref("VENT_FILTRO", pos, dxfattribs={"layer": "VENT-FILTRO"})
            ref.add_auto_attribs({"TAG": tag, "PERDA": f"{fmt(perda, 0)} Pa" if perda is not None else "-"})
        elif n["type"] == "descarga":
            ref = msp.add_blockref("VENT_DESCARGA", pos, dxfattribs={"layer": "VENT-ACESSORIO"})
            ref.add_auto_attribs({"TAG": tag})
        elif n["type"] == "juncao":
            msp.add_circle(pos, 80, dxfattribs={"layer": "VENT-ACESSORIO"})

    # Legenda / carimbo
    ext = bbox.extents(msp, fast=True)
    xs = [ext.extmin.x, ext.extmax.x] if ext.has_data else []
    ys = [ext.extmin.y, ext.extmax.y] if ext.has_data else []
    x0 = (max(xs) if xs else 0) + 1500
    y0 = min(ys) if ys else 0
    linhas = [
        "MEMÓRIA DO DESENHO",
        f"Projeto: {projeto.get('codigo', '')} - {projeto.get('nome', '')}",
        f"Cliente: {projeto.get('cliente') or '-'}",
        f"Sistema: {projeto.get('modulo_nome', projeto.get('modulo', ''))}",
        f"Data: {date.today().strftime('%d/%m/%Y')}   Unidades: mm   Escala do modelo 1:1",
        f"Vazão total: {fmt(res.get('vazao_total_m3h', 0), 0)} m³/h" if res else "Vazão total: não calculada",
        f"Pressão total do ventilador: {fmt(res.get('pressao_total_ventilador_pa', 0), 0)} Pa" if res else "",
        f"Exaustor: {sel['nome']}" if sel else "Exaustor: não selecionado",
        f"Versão do motor de cálculo: {res.get('versao_motor', '-')}",
        "SITUAÇÃO: APROVADO PELO RESPONSÁVEL TÉCNICO" if aprovado else "SITUAÇÃO: PRELIMINAR - NÃO APROVADO PARA EXECUÇÃO",
    ]
    if demonstrativo:
        linhas.append("DADOS DEMONSTRATIVOS (FICTÍCIOS) - NÃO UTILIZAR EM OBRA")
    altura_linha = 260
    larg_carimbo = 9000
    h = altura_linha * (len(linhas) + 1)
    msp.add_lwpolyline([(x0, y0), (x0 + larg_carimbo, y0), (x0 + larg_carimbo, y0 + h), (x0, y0 + h)], close=True, dxfattribs={"layer": "VENT-LEGENDA"})
    for i, txt in enumerate(linhas):
        if not txt:
            continue
        msp.add_text(txt, height=160 if i else 200, dxfattribs={"layer": "VENT-LEGENDA", "insert": (x0 + 150, y0 + h - altura_linha * (i + 1))})
    # Tabela de trechos
    yt = y0 + h + 600
    msp.add_text("TRECHOS (Ø mm | vazão m³/h | velocidade m/s | comprimento m)", height=160, dxfattribs={"layer": "VENT-LEGENDA", "insert": (x0 + 150, yt)})
    for i, t in enumerate(res.get("trechos", [])[:80]):
        sec = f"Ø{fmt(t['diametro_mm'], 0)}" if t.get("diametro_mm") else f"{t.get('largura_mm')}x{t.get('altura_mm')}"
        msp.add_text(f"{t['label']}: {sec} | {fmt(t['vazao_m3h'], 0)} | {fmt(t['velocidade_ms'], 1)} | {fmt(t['comprimento_m'], 2)}",
                     height=130, dxfattribs={"layer": "VENT-LEGENDA", "insert": (x0 + 150, yt + 230 * (i + 1))})

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "saida.dxf"
        doc.saveas(p)
        return p.read_bytes()


def validar_dxf(dados: bytes) -> dict:
    """Relê o DXF gerado e executa a auditoria do ezdxf."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "v.dxf"
        p.write_bytes(dados)
        doc = ezdxf.readfile(p)
        aud = doc.audit()
        msp = doc.modelspace()
        return {
            "versao": doc.dxfversion,
            "insunits": doc.header.get("$INSUNITS"),
            "erros": len(aud.errors),
            "correcoes": len(aud.fixes),
            "camadas": sorted(l.dxf.name for l in doc.layers),
            "entidades": len(msp),
            "blocos": sorted(b.name for b in doc.blocks if not b.name.startswith("*")),
        }
