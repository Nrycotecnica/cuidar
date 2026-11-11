"""Lista de materiais (quantitativos) a partir da rede calculada e do catálogo.

Regras de contagem (estimativas, exibidas no documento):
* dutos retos: comprimento total por diâmetro/material; peças = teto(L/comprimento comercial);
* curvas: uma por mudança de direção, agrupadas por diâmetro e ângulo;
* reduções: mudança de diâmetro no tronco; derivações: uma por ramal que entra em junção;
* flanges: 2 por peça (duto, curva, redução) e 3 por derivação;
* suportes: teto(L/espaçamento) por diâmetro (parâmetro espacamento_suportes_m).
"""

from __future__ import annotations

import csv
import io
import math
from collections import defaultdict

from ..engine.trace import fmt

ANGULOS_PADRAO = [15, 30, 45, 60, 90]

REGRAS = [
    "Dutos: peças = teto(comprimento total / comprimento comercial cadastrado).",
    "Curvas: uma por mudança de direção, ângulo arredondado ao padrão mais próximo (15°, 30°, 45°, 60°, 90°).",
    "Flanges (estimativa): 2 por peça reta, curva e redução; 3 por derivação.",
    "Suportes: teto(comprimento / espaçamento) por diâmetro.",
    "Itens sem custo cadastrado aparecem com custo em branco e não entram no total.",
]


def _ang_padrao(a: float) -> int:
    return min(ANGULOS_PADRAO, key=lambda x: abs(x - a))


def _buscar(componentes, categoria, **kw):
    for c in componentes:
        if c.get("categoria") != categoria or not c.get("ativo", True):
            continue
        ok = True
        for k, v in kw.items():
            if v is None:
                continue
            cv = c.get(k)
            if isinstance(v, (int, float)) and cv is not None:
                if abs(float(cv) - float(v)) > 1e-6:
                    ok = False
            elif cv != v:
                ok = False
        if ok:
            return c
    return None


def gerar_lista(projeto: dict, rede: dict, resultado: dict, componentes: list[dict], exaustor: dict | None,
                espacamento_suportes: float | None, liberado: bool) -> dict:
    itens = []
    avisos = []

    def add(categoria, descricao, qtd, unidade, comp=None, obs=""):
        cu = comp.get("custo_unitario") if comp else None
        itens.append({
            "categoria": categoria, "codigo": comp.get("codigo") if comp else "", "descricao": descricao,
            "quantidade": qtd, "unidade": unidade, "custo_unitario": cu,
            "custo_total": (cu * qtd) if cu is not None else None, "observacao": obs,
        })

    trechos = resultado.get("trechos", [])
    por_secao = defaultdict(float)
    for t in trechos:
        if t.get("diametro_mm"):
            por_secao[("circular", t["diametro_mm"], None, t["material"])] += t["comprimento_m"]
        else:
            por_secao[("retangular", t.get("largura_mm"), t.get("altura_mm"), t["material"])] += t["comprimento_m"]

    n_pecas = 0
    for (forma, d1, d2, mat), L in sorted(por_secao.items(), key=lambda x: (x[0][0], x[0][1] or 0)):
        if forma == "circular":
            comp = _buscar(componentes, "duto_circular", diametro_mm=d1, material=mat) or _buscar(componentes, "duto_circular", diametro_mm=d1)
            desc = f"Duto circular Ø{fmt(d1,0)} mm - {mat}"
        else:
            comp = _buscar(componentes, "duto_retangular", largura_mm=d1, altura_mm=d2)
            desc = f"Duto retangular {fmt(d1 or 0,0)}x{fmt(d2 or 0,0)} mm - {mat}"
        if comp and comp.get("comprimento_m"):
            pecas = math.ceil(L / comp["comprimento_m"] - 1e-9)
            n_pecas += pecas
            unit_cost = comp.get("custo_unitario")
            itens.append({"categoria": "Dutos", "codigo": comp.get("codigo"), "descricao": desc + f" (peças de {fmt(comp['comprimento_m'],2)} m)",
                          "quantidade": pecas, "unidade": "pç", "custo_unitario": unit_cost,
                          "custo_total": unit_cost * pecas if unit_cost is not None else None,
                          "observacao": f"Comprimento total {fmt(L,2)} m"})
        else:
            add("Dutos", desc, round(L, 2), "m", comp, "Comprimento comercial não cadastrado — informado em metros")
            if not comp:
                avisos.append(f"Componente não cadastrado: {desc}")
            n_pecas += max(1, math.ceil(L / 3.0))
        if espacamento_suportes:
            sup = _buscar(componentes, "suporte", diametro_mm=d1) or _buscar(componentes, "suporte")
            add("Suportes", f"Suporte para duto {('Ø'+fmt(d1,0)) if forma=='circular' else ''} mm".replace("  ", " "),
                math.ceil(L / espacamento_suportes), "un", sup, f"Espaçamento {fmt(espacamento_suportes,1)} m")

    curvas = defaultdict(int)
    for t in trechos:
        for a in t.get("curvas", []):
            curvas[(t.get("diametro_mm"), _ang_padrao(a), t["material"])] += 1
    for (d, a, mat), q in sorted(curvas.items(), key=lambda x: (x[0][0] or 0, x[0][1])):
        comp = _buscar(componentes, "curva", diametro_mm=d, angulo_graus=a)
        add("Curvas", f"Curva {a}° Ø{fmt(d or 0,0)} mm - {mat}", q, "un", comp)
        if not comp:
            avisos.append(f"Curva {a}° Ø{fmt(d or 0,0)} não cadastrada")

    # Reduções e derivações
    nos = {n["id"]: n for n in rede.get("nodes", [])}
    por_id = {t["id"]: t for t in trechos}
    saidas = {t["de"]: t for t in trechos}
    entradas = defaultdict(list)
    for t in trechos:
        entradas[t["para"]].append(t)
    n_red, n_der = 0, 0
    for nid, n in nos.items():
        so = saidas.get(nid)
        if not so:
            continue
        for ti in entradas.get(nid, []):
            if n["type"] == "juncao" and ti.get("tronco_em") != nid:
                comp = _buscar(componentes, "derivacao", diametro_mm=so.get("diametro_mm"), diametro2_mm=ti.get("diametro_mm"))
                ang = next((s["descricao"] for s in ti["singulares"] if s["tipo"] == "entrada_ramal"), "")
                add("Derivações", f"Derivação Ø{fmt(so.get('diametro_mm') or 0,0)} × ramal Ø{fmt(ti.get('diametro_mm') or 0,0)} mm", 1, "un", comp, ang)
                n_der += 1
            elif ti.get("diametro_mm") and so.get("diametro_mm") and ti["diametro_mm"] != so["diametro_mm"] and n["type"] in ("juncao", "ponto"):
                comp = _buscar(componentes, "reducao", diametro_mm=max(ti["diametro_mm"], so["diametro_mm"]), diametro2_mm=min(ti["diametro_mm"], so["diametro_mm"]))
                add("Reduções", f"Redução concêntrica Ø{fmt(ti['diametro_mm'],0)} → Ø{fmt(so['diametro_mm'],0)} mm", 1, "un", comp, f"Nó {n.get('label') or nid}")
                n_red += 1

    n_curvas = sum(curvas.values())
    n_flanges = 2 * (n_pecas + n_curvas + n_red) + 3 * n_der
    comp_fl = _buscar(componentes, "flange")
    add("Flanges", "Flanges (estimativa por regra de contagem)", n_flanges, "un", comp_fl, "Ver regras de contagem")

    for n in rede.get("nodes", []):
        if n["type"] == "captor":
            c = n.get("captor") or {}
            add("Captores", f"Captor {n.get('label') or n['id']} - {c.get('tipo','')}".strip(" -"), 1, "un",
                _buscar(componentes, "captor"), "Detalhar geometria para fabricação")
        elif n["type"] in ("filtro", "equipamento"):
            add("Equipamentos", f"{n['type'].capitalize()} {n.get('label') or n['id']} ({n.get('filtro_tipo') or n.get('equipamento_tipo') or 'a especificar'})", 1, "un")
    if exaustor:
        itens.append({"categoria": "Exaustores", "codigo": exaustor.get("codigo"), "descricao": f"Exaustor {exaustor.get('modelo')}",
                      "quantidade": 1, "unidade": "un", "custo_unitario": exaustor.get("preco"),
                      "custo_total": exaustor.get("preco"), "observacao": ""})
    else:
        add("Exaustores", "Exaustor - não selecionado", 1, "un", None, "Sem equipamento compatível ou cálculo pendente")

    total = sum(i["custo_total"] for i in itens if i["custo_total"] is not None)
    sem_custo = sum(1 for i in itens if i["custo_total"] is None)
    for i, it in enumerate(itens, 1):
        it["item"] = i
    return {
        "situacao": "LIBERADO PARA FABRICAÇÃO" if liberado else "PRELIMINAR - quantitativos estimados, não liberados para fabricação",
        "liberado": liberado,
        "itens": itens,
        "total_custo": total,
        "itens_sem_custo": sem_custo,
        "regras": REGRAS,
        "avisos": avisos,
    }


def para_csv(lista: dict) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([f"# {lista['situacao']}"])
    w.writerow(["Item", "Categoria", "Código", "Descrição", "Quantidade", "Unidade", "Custo unitário", "Custo total", "Observação"])
    for i in lista["itens"]:
        w.writerow([i["item"], i["categoria"], i["codigo"] or "", i["descricao"], fmt(i["quantidade"], 2) if isinstance(i["quantidade"], float) else i["quantidade"],
                    i["unidade"], fmt(i["custo_unitario"], 2) if i["custo_unitario"] is not None else "",
                    fmt(i["custo_total"], 2) if i["custo_total"] is not None else "", i["observacao"]])
    w.writerow([])
    w.writerow(["", "", "", "TOTAL (itens com custo cadastrado)", "", "", "", fmt(lista["total_custo"], 2)])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def para_xlsx(lista: dict, titulo: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Lista de materiais"
    ws.append([titulo])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([lista["situacao"]])
    ws["A2"].font = Font(bold=True, color="C00000" if not lista["liberado"] else "006100")
    ws.append([])
    cab = ["Item", "Categoria", "Código", "Descrição", "Quantidade", "Unidade", "Custo unitário (R$)", "Custo total (R$)", "Observação"]
    ws.append(cab)
    for c in ws[4]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="305496")
    for i in lista["itens"]:
        ws.append([i["item"], i["categoria"], i["codigo"], i["descricao"], i["quantidade"], i["unidade"], i["custo_unitario"], i["custo_total"], i["observacao"]])
    ws.append([])
    ws.append(["", "", "", "TOTAL (itens com custo cadastrado)", "", "", "", lista["total_custo"]])
    for col, w in zip("ABCDEFGHI", (6, 14, 14, 55, 12, 9, 18, 16, 40)):
        ws.column_dimensions[col].width = w
    ws2 = wb.create_sheet("Regras")
    for r in lista["regras"]:
        ws2.append([r])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
