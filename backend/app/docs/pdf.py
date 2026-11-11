"""Documentos PDF: memorial de cálculo, lista de materiais e prancha do desenho."""

from __future__ import annotations

import io
import math
from datetime import datetime

from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..engine.trace import fmt
from ..marca import ASSINATURA, NOME_SOFTWARE, PROGRAMADOR

ESTILOS = getSampleStyleSheet()
P = ParagraphStyle("p", parent=ESTILOS["BodyText"], fontSize=8.5, leading=11)
PS = ParagraphStyle("ps", parent=P, fontSize=7.5, leading=9)
H1 = ParagraphStyle("h1", parent=ESTILOS["Heading1"], fontSize=15, spaceAfter=6)
H2 = ParagraphStyle("h2", parent=ESTILOS["Heading2"], fontSize=11.5, spaceBefore=10, spaceAfter=4)
ALERTA = ParagraphStyle("al", parent=P, textColor=colors.HexColor("#B00020"), fontSize=9.5, leading=12)

TAB = TableStyle([
    ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F1")),
    ("FONTSIZE", (0, 0), (-1, -1), 7.5),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 3),
    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
])


def _esc(s) -> str:
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _tab(linhas, larguras=None):
    dados = [[Paragraph(_esc(c), PS) for c in linha] for linha in linhas]
    t = Table(dados, colWidths=larguras, repeatRows=1)
    t.setStyle(TAB)
    return t


def _rodape(texto):
    def f(c, doc):
        c.saveState()
        c.setFont("Helvetica", 7)
        c.drawString(15 * mm, 8 * mm, texto)
        c.drawCentredString(doc.pagesize[0] / 2, 4 * mm, ASSINATURA)
        c.drawRightString(doc.pagesize[0] - 15 * mm, 8 * mm, f"Página {doc.page}")
        c.restoreState()
    return f


def grafico_curvas(sel: dict, k_total: float, k_est: float, q_proj_m3h: float) -> Drawing | None:
    if not sel or not sel.get("curva_m3h_pa"):
        return None
    curva = [(q, p) for q, p in sel["curva_m3h_pa"]]
    k = k_est if sel.get("tipo_pressao_curva") == "estatica" else k_total
    qmax = max(q for q, _ in curva)
    sist = [(q, k * (q / 3600) ** 2) for q in [qmax * i / 30 for i in range(31)]]
    d = Drawing(170 * mm, 85 * mm)
    lp = LinePlot()
    lp.x, lp.y = 15 * mm, 12 * mm
    lp.width, lp.height = 145 * mm, 62 * mm
    lp.data = [curva, sist, [(sel["ponto_operacao"]["vazao_m3h"], sel["ponto_operacao"]["pressao_pa"])]]
    lp.lines[0].strokeColor = colors.HexColor("#1F4E79")
    lp.lines[1].strokeColor = colors.HexColor("#C00000")
    lp.lines[2].strokeColor = colors.transparent
    lp.lines[2].symbol = makeMarker("FilledCircle")
    lp.lines[0].strokeWidth = lp.lines[1].strokeWidth = 1.4
    pmax = max(max(p for _, p in curva), max(p for _, p in sist))
    lp.xValueAxis.valueMin, lp.xValueAxis.valueMax = 0, qmax
    lp.yValueAxis.valueMin, lp.yValueAxis.valueMax = 0, pmax * 1.1
    lp.xValueAxis.labels.fontSize = lp.yValueAxis.labels.fontSize = 6
    d.add(lp)
    d.add(String(85 * mm, 3 * mm, "Vazão (m³/h)", fontSize=7, textAnchor="middle"))
    d.add(String(2 * mm, 78 * mm, f"Pressão {'estática' if sel.get('tipo_pressao_curva') == 'estatica' else 'total'} (Pa)", fontSize=7))
    d.add(String(110 * mm, 78 * mm, "— curva do exaustor (corrigida)", fontSize=7, fillColor=colors.HexColor("#1F4E79")))
    d.add(String(110 * mm, 74 * mm, "— curva do sistema", fontSize=7, fillColor=colors.HexColor("#C00000")))
    return d


def memorial_pdf(ctx: dict) -> bytes:
    """ctx: projeto, cliente, entradas, calculo (resultados), seguranca, aprovacao, versoes."""
    buf = io.BytesIO()
    pr = ctx["projeto"]
    r = ctx["resultado"]
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm,
                            title=f"Memorial de cálculo - {pr['codigo']}", author=PROGRAMADOR, creator=NOME_SOFTWARE)
    el = []
    el.append(Paragraph(f"Memorial de cálculo — {_esc(pr['codigo'])} — {_esc(pr['nome'])}", H1))
    el.append(Paragraph(_esc(ASSINATURA), PS))
    if ctx.get("demonstrativo"):
        el.append(Paragraph("DADOS DEMONSTRATIVOS (FICTÍCIOS). Este documento não representa um projeto real e não pode ser usado para instalação.", ALERTA))
    if not ctx.get("aprovado"):
        el.append(Paragraph("DOCUMENTO PRELIMINAR — cálculo não aprovado por responsável técnico. Sujeito a revisão.", ALERTA))
    el.append(Spacer(1, 4))
    ident = [
        ["Campo", "Valor"],
        ["Cliente", pr.get("cliente") or "-"],
        ["Sistema", pr.get("modulo_nome")],
        ["Situação do projeto", pr.get("status")],
        ["Cálculo nº", f"{ctx['calculo_id']} em {ctx['calculo_data']}"],
        ["Versão do software / motor", f"{ctx['versao_app']} / {r.get('versao_motor')}"],
        ["Hash das entradas (SHA-256)", r.get("hash_entradas", "-")],
        ["Emitido em", datetime.now().strftime("%d/%m/%Y %H:%M")],
    ]
    el.append(_tab(ident, [55 * mm, 125 * mm]))

    el.append(Paragraph("1. Dados de entrada", H2))
    linhas = [["Dado", "Valor", "Situação", "Fonte"]]
    for k, v in (ctx.get("entradas") or {}).items():
        if isinstance(v, dict):
            linhas.append([v.get("rotulo", k), f"{v.get('valor')} {v.get('unidade') or ''}", v.get("status", "-"), v.get("fonte") or "-"])
    if len(linhas) > 1:
        el.append(_tab(linhas, [55 * mm, 45 * mm, 30 * mm, 50 * mm]))
    ar = r.get("ar") or {}
    if ar:
        el.append(Paragraph(f"Temperatura do ar: {fmt(ar['temperatura_c'],1)} °C — altitude: {fmt(ar['altitude_m'],0)} m — densidade: {fmt(ar['densidade'],4)} kg/m³", P))

    el.append(Paragraph("2. Hipóteses de cálculo", H2))
    for h in r.get("hipoteses", []):
        el.append(Paragraph("• " + _esc(h), P))

    el.append(Paragraph("3. Parâmetros técnicos utilizados", H2))
    linhas = [["Chave", "Valor", "Unid.", "Status", "Referência"]]
    for p in r.get("parametros_usados", []):
        st = p["status"] + (" (demonstrativo)" if p.get("demonstrativo") else "")
        linhas.append([p["chave"], str(p["valor"]), p.get("unidade") or "", st, p.get("referencia") or ""])
    el.append(_tab(linhas, [48 * mm, 18 * mm, 16 * mm, 30 * mm, 68 * mm]))

    el.append(Paragraph("4. Memória de cálculo", H2))
    linhas = [["Descrição", "Fórmula", "Substituição", "Resultado"]]
    for p in r.get("passos", []):
        res = p["resultado"]
        res = fmt(res, 4) if isinstance(res, float) else str(res)
        linhas.append([p["descricao"], p["formula"], p["substituicao"], f"{res} {p.get('unidade','')}"])
    el.append(_tab(linhas, [45 * mm, 38 * mm, 65 * mm, 32 * mm]))

    if r.get("trechos"):
        el.append(Paragraph("5. Resultados por trecho", H2))
        linhas = [["Trecho", "Lado", "Seção", "Vazão m³/h", "v m/s", "VP Pa", "L m", "f", "ΣK", "Perda Pa"]]
        for t in r["trechos"]:
            sec = f"Ø{fmt(t['diametro_mm'],0)}" if t.get("diametro_mm") else f"{t.get('largura_mm')}x{t.get('altura_mm')}"
            linhas.append([t["label"], t["lado"], sec, fmt(t["vazao_m3h"], 0), fmt(t["velocidade_ms"], 2), fmt(t["vp_pa"], 1),
                           fmt(t["comprimento_m"], 2), fmt(t["fator_atrito"], 4), fmt(t.get("k_total", 0), 2), fmt(t["perda_total_pa"], 1)])
        el.append(_tab(linhas))
        el.append(Spacer(1, 4))
        res = [
            ["Grandeza", "Valor"],
            ["Vazão total", f"{fmt(r['vazao_total_m3h'],0)} m³/h"],
            ["Perda no ramo governante (sucção)", f"{fmt(r['pressao_succao_pa'],1)} Pa"],
            ["Perda na descarga (inclui saída)", f"{fmt(r['pressao_descarga_pa'],1)} Pa"],
            ["Pressão total do ventilador (FTP)", f"{fmt(r['pressao_total_ventilador_pa'],1)} Pa"],
            ["Pressão estática do ventilador (FSP)", f"{fmt(r['pressao_estatica_ventilador_pa'],1)} Pa"],
            ["Potência transmitida ao ar", f"{fmt(r['potencia_ar_kw'],3)} kW"],
        ]
        el.append(_tab(res, [90 * mm, 60 * mm]))
    if r.get("equilibrio"):
        el.append(Paragraph("6. Equilíbrio de pressões nas junções", H2))
        linhas = [["Junção", "Ramal", "Perda ramal Pa", "Perda governante Pa", "Razão", "Situação / ação"]]
        for e in r["equilibrio"]:
            linhas.append([e["juncao"], e["trecho"], fmt(e["perda_ramal_pa"], 1), fmt(e["perda_governante_pa"], 1), fmt(e["razao"], 2), e["mensagem"]])
        el.append(_tab(linhas, [18 * mm, 18 * mm, 22 * mm, 25 * mm, 14 * mm, 83 * mm]))

    sel = r.get("selecao_exaustor")
    if sel is not None:
        el.append(Paragraph("7. Seleção do exaustor (catálogo próprio)", H2))
        s = sel.get("selecionado")
        if s:
            op = s["ponto_operacao"]
            el.append(Paragraph(
                f"Selecionado: <b>{_esc(s['nome'])}</b> — ponto de operação {fmt(op['vazao_m3h'],0)} m³/h a {fmt(op['pressao_pa'],0)} Pa "
                f"({'estática' if s['tipo_pressao_curva']=='estatica' else 'total'}); folga de vazão {fmt(s['folga_vazao_pct'] or 0,1)}%; "
                f"potência absorvida {fmt(s['potencia_absorvida_kw'],2) + ' kW' if s.get('potencia_absorvida_kw') is not None else 'não disponível (sem dados de potência)'}; "
                f"correção de densidade ρ/ρref = {fmt(s['fator_densidade'],3)}.", P))
            g = grafico_curvas(s, r["k_sistema_total"], r["k_sistema_estatica"], r["vazao_total_m3h"])
            if g:
                el.append(g)
            if ctx.get("exaustor_escolhido_manual"):
                el.append(Paragraph("Equipamento escolhido manualmente pelo usuário dentre os compatíveis.", P))
        else:
            el.append(Paragraph(_esc(sel.get("mensagem") or "Nenhum equipamento compatível."), ALERTA))
        if sel.get("compativeis"):
            linhas = [["Compatíveis", "Q op m³/h", "P op Pa", "Potência kW", "Folga %"]]
            for c in sel["compativeis"]:
                linhas.append([c["nome"], fmt(c["ponto_operacao"]["vazao_m3h"], 0), fmt(c["ponto_operacao"]["pressao_pa"], 0),
                               fmt(c["potencia_absorvida_kw"], 2) if c.get("potencia_absorvida_kw") is not None else "-", fmt(c.get("folga_vazao_pct") or 0, 1)])
            el.append(_tab(linhas))
        if sel.get("rejeitados"):
            linhas = [["Rejeitado", "Motivo"]] + [[x["nome"], x["motivo"]] for x in sel["rejeitados"]]
            el.append(Spacer(1, 3))
            el.append(_tab(linhas, [55 * mm, 125 * mm]))

    if r.get("vazao_requerida_m3h") is not None:  # renovação
        el.append(Paragraph("Resultados — renovação de ar", H2))
        linhas = [["Grandeza", "Valor"],
                  ["Volume", f"{fmt(r['volume_m3'],1)} m³"],
                  ["Critério governante", r["criterio_governante"]],
                  ["Vazão requerida", f"{fmt(r['vazao_requerida_m3h'],0)} m³/h"],
                  ["Exaustão / insuflamento", f"{fmt(r['vazao_exaustao_m3h'],0)} / {fmt(r['vazao_insuflamento_m3h'],0)} m³/h"],
                  ["Trocas por hora resultantes", fmt(r["trocas_hora_resultantes"], 1)],
                  ["Área livre de entrada de ar", f"{fmt(r['area_entrada_m2'],2)} m²"]]
        el.append(_tab(linhas, [80 * mm, 80 * mm]))
        if r.get("opcoes_equipamento"):
            linhas = [["Equipamento", "Qtd", "Q unit. m³/h", "Q total m³/h", "Potência kW"]]
            for o in r["opcoes_equipamento"]:
                linhas.append([o["nome"], o["quantidade"], fmt(o["vazao_unitaria_m3h"], 0), fmt(o["vazao_total_m3h"], 0),
                               fmt(o["potencia_total_kw"], 2) if o.get("potencia_total_kw") is not None else "-"])
            el.append(_tab(linhas))

    seg = ctx.get("seguranca") or {}
    el.append(Paragraph("8. Verificações de segurança", H2))
    if not seg.get("aplicaveis") and not seg.get("bloqueios"):
        el.append(Paragraph("Nenhum risco especial declarado no projeto (poeira combustível, atmosfera explosiva, contaminante perigoso, temperatura elevada, controle de fumaça). A declaração de riscos é responsabilidade do projetista.", P))
    for b in seg.get("bloqueios", []):
        el.append(Paragraph(_esc(b), ALERTA))
    for a in seg.get("aplicaveis", []):
        el.append(Paragraph(f"<b>{_esc(a['titulo'])}</b> — {_esc(a['referencias'])}", P))
        for it in a["itens"]:
            el.append(Paragraph(("☑ " if it["ok"] else "☐ ") + _esc(it["texto"]) + (f" — confirmado por {_esc(it['por'])}" if it.get("por") else ""), P))

    el.append(Paragraph("9. Avisos e bloqueios", H2))
    for b in r.get("bloqueios", []):
        el.append(Paragraph("BLOQUEIO: " + _esc(b), ALERTA))
    for a in r.get("avisos", []):
        el.append(Paragraph("Aviso: " + _esc(a), P))
    if not r.get("bloqueios") and not r.get("avisos"):
        el.append(Paragraph("Nenhum.", P))

    el.append(Paragraph("10. Responsabilidade técnica", H2))
    ap = ctx.get("aprovacao")
    if ap:
        el.append(Paragraph(f"Aprovado por {_esc(ap['nome'])} ({_esc(ap.get('registro') or 'registro não informado')}) em {_esc(ap['data'])}.", P))
    else:
        el.append(Paragraph("Aprovação técnica pendente. Os resultados são preliminares e dependem de validação por profissional legalmente habilitado.", P))
    el.append(Spacer(1, 6))
    el.append(Paragraph("Os cálculos foram executados por algoritmos determinísticos do motor de cálculo; nenhum valor foi gerado por inteligência artificial.", PS))
    rod = _rodape(f"{pr['codigo']} — memorial de cálculo — {'APROVADO' if ctx.get('aprovado') else 'PRELIMINAR'}{' — DEMONSTRATIVO' if ctx.get('demonstrativo') else ''}")
    doc.build(el, onFirstPage=rod, onLaterPages=rod)
    return buf.getvalue()


def lista_pdf(lista: dict, titulo: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=14 * mm, title=titulo, author=PROGRAMADOR, creator=NOME_SOFTWARE)
    el = [Paragraph(_esc(titulo), H1), Paragraph(_esc(lista["situacao"]), ALERTA if not lista["liberado"] else P), Spacer(1, 4)]
    linhas = [["Item", "Categoria", "Código", "Descrição", "Qtd", "Un", "Custo unit. R$", "Custo total R$", "Observação"]]
    for i in lista["itens"]:
        q = i["quantidade"]
        linhas.append([i["item"], i["categoria"], i["codigo"] or "", i["descricao"], fmt(q, 2) if isinstance(q, float) else q, i["unidade"],
                       fmt(i["custo_unitario"], 2) if i["custo_unitario"] is not None else "-",
                       fmt(i["custo_total"], 2) if i["custo_total"] is not None else "-", i["observacao"]])
    linhas.append(["", "", "", "TOTAL (itens com custo cadastrado)", "", "", "", fmt(lista["total_custo"], 2), f"{lista['itens_sem_custo']} item(ns) sem custo"])
    el.append(_tab(linhas, [10 * mm, 24 * mm, 24 * mm, 80 * mm, 14 * mm, 10 * mm, 22 * mm, 24 * mm, 63 * mm]))
    el.append(Paragraph("Regras de contagem", H2))
    for rg in lista["regras"]:
        el.append(Paragraph("• " + _esc(rg), P))
    doc.build(el, onFirstPage=_rodape(titulo), onLaterPages=_rodape(titulo))
    return buf.getvalue()


ESCALAS = [20, 25, 50, 75, 100, 125, 150, 200, 250, 300, 400, 500, 750, 1000, 1500, 2000]


def desenho_pdf(projeto: dict, rede: dict, resultado: dict | None, ambiente: dict | None, aprovado: bool, demonstrativo: bool) -> bytes:
    """Prancha A3 vetorial na escala normalizada que couber."""
    W, H = landscape(A3)
    margem = 12 * mm
    carimbo_h = 32 * mm
    area_w, area_h = W - 2 * margem, H - 2 * margem - carimbo_h
    nos = {n["id"]: n for n in rede.get("nodes", [])}
    pts = [(n["x"], n["y"]) for n in nos.values()]
    amb = ambiente or {}
    for p in (amb.get("contorno") or []):
        pts.append(tuple(p))
    for grupo in ("pilares", "obstaculos"):
        for o in amb.get(grupo, []):
            pts += [tuple(p) for p in o["pontos"]]
    for s in rede.get("segments", []):
        pts += [tuple(p) for p in (s.get("path") or [])]
    if not pts:
        pts = [(0, 0), (10, 10)]
    x0, y0 = min(p[0] for p in pts) - 1, min(p[1] for p in pts) - 1
    x1, y1 = max(p[0] for p in pts) + 1, max(p[1] for p in pts) + 1
    esc = next((e for e in ESCALAS if (x1 - x0) * 1000 / e * mm <= area_w and (y1 - y0) * 1000 / e * mm <= area_h), ESCALAS[-1])
    k = 1000 / esc * mm  # pontos por metro

    def T(x, y):
        return margem + (x - x0) * k, margem + carimbo_h + (y - y0) * k

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle(f"Desenho - {projeto.get('codigo')}")
    c.setAuthor(PROGRAMADOR)
    c.setCreator(NOME_SOFTWARE)
    c.setLineWidth(0.2)
    c.setStrokeColor(colors.grey)
    if amb.get("contorno"):
        pp = [T(*p) for p in amb["contorno"]]
        path = c.beginPath()
        path.moveTo(*pp[0])
        for p in pp[1:]:
            path.lineTo(*p)
        path.close()
        c.drawPath(path)
    for grupo, cor in (("pilares", colors.darkgrey), ("obstaculos", colors.lightgrey)):
        for o in amb.get(grupo, []):
            pp = [T(*p) for p in o["pontos"]]
            path = c.beginPath()
            path.moveTo(*pp[0])
            for p in pp[1:]:
                path.lineTo(*p)
            path.close()
            c.setFillColor(cor)
            c.drawPath(path, fill=1)
    trechos = {t["id"]: t for t in (resultado or {}).get("trechos", [])}
    c.setFillColor(colors.black)
    for s in rede.get("segments", []):
        a, b = nos[s["from"]], nos[s["to"]]
        ptsS = [[a["x"], a["y"]]] + list(s.get("path") or []) + [[b["x"], b["y"]]]
        t = trechos.get(s["id"], {})
        d = (t.get("diametro_mm") or s.get("diametro_mm") or t.get("largura_mm") or 200) / 1000
        c.setStrokeColor(colors.HexColor("#C00000"))
        c.setLineWidth(max(d * k, 0.8))
        c.setLineCap(0)
        path = c.beginPath()
        path.moveTo(*T(*ptsS[0]))
        for p in ptsS[1:]:
            path.lineTo(*T(*p))
        c.drawPath(path)
        p0, p1 = max(zip(ptsS, ptsS[1:]), key=lambda pp: math.dist(pp[0], pp[1]))
        mx, my = T((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
        c.setFont("Helvetica", 6)
        lbl = f"{s.get('label') or s['id']} Ø{fmt(t.get('diametro_mm') or s.get('diametro_mm') or 0,0)}"
        if t:
            lbl += f" {fmt(t['vazao_m3h'],0)} m³/h"
        c.drawCentredString(mx, my + max(d * k, 1) / 2 + 2, lbl)
    for n in nos.values():
        x, y = T(n["x"], n["y"])
        c.setLineWidth(0.6)
        c.setStrokeColor(colors.black)
        cores = {"captor": "#2E7D32", "exaustor": "#1F4E79", "filtro": "#6A1B9A", "descarga": "#555555", "juncao": "#000000"}
        c.setFillColor(colors.HexColor(cores.get(n["type"], "#000000")))
        r = 4 if n["type"] in ("captor", "exaustor", "filtro") else 2
        if n["type"] == "captor":
            c.rect(x - r, y - r, 2 * r, 2 * r, fill=1)
        else:
            c.circle(x, y, r, fill=1)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 6.5)
        if n["type"] != "juncao":
            c.drawString(x + r + 2, y + r, n.get("label") or n["id"])
    # escala gráfica
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    bx, by = W - margem - 60 * mm, margem + carimbo_h + 5 * mm
    seg_m = 5 if esc <= 200 else 10
    c.line(bx, by, bx + seg_m * k, by)
    c.setFont("Helvetica", 7)
    c.drawString(bx, by + 3, f"0        {seg_m} m")
    # carimbo
    c.rect(margem, margem, W - 2 * margem, carimbo_h)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margem + 4 * mm, margem + carimbo_h - 8 * mm, f"{projeto.get('codigo')} — {projeto.get('nome')}")
    c.drawRightString(W - margem - 4 * mm, margem + carimbo_h - 8 * mm, NOME_SOFTWARE)
    c.setFont("Helvetica", 8)
    c.drawRightString(W - margem - 4 * mm, margem + carimbo_h - 14 * mm, f"Desenvolvido por {PROGRAMADOR}")
    c.setFont("Helvetica", 8)
    c.drawString(margem + 4 * mm, margem + carimbo_h - 14 * mm, f"Cliente: {projeto.get('cliente') or '-'}   Sistema: {projeto.get('modulo_nome')}   Escala 1:{esc} (A3)   Unidades: m")
    r = resultado or {}
    if r:
        c.drawString(margem + 4 * mm, margem + carimbo_h - 20 * mm,
                     f"Vazão total {fmt(r.get('vazao_total_m3h',0),0)} m³/h   Pressão total {fmt(r.get('pressao_total_ventilador_pa',0),0)} Pa   Motor de cálculo v{r.get('versao_motor')}")
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#B00020") if not aprovado else colors.HexColor("#006100"))
    c.drawString(margem + 4 * mm, margem + 5 * mm, "APROVADO PELO RESPONSÁVEL TÉCNICO" if aprovado else "PRELIMINAR — NÃO APROVADO PARA EXECUÇÃO")
    if demonstrativo:
        c.drawString(margem + 110 * mm, margem + 5 * mm, "DADOS DEMONSTRATIVOS (FICTÍCIOS)")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 7)
    c.drawRightString(W - margem - 4 * mm, margem + 5 * mm, f"Emitido em {datetime.now().strftime('%d/%m/%Y %H:%M')} — o desenho editável é o DXF")
    c.showPage()
    c.save()
    return buf.getvalue()
