"""PDF de apresentação para o cliente: capa, vistas 3D, resumo técnico e observações.

As imagens 3D são renderizadas no navegador (a mesma cena da aba 3D) e chegam
prontas aqui; o servidor não desenha 3D. O documento vai para o cliente, então:
- nada de preço, custo ou orçamento (o resultado do cálculo carrega o preço do
  exaustor em ``custo`` — ele NÃO entra aqui);
- a situação do projeto (preliminar/aprovado/demonstrativo) aparece na capa e
  em todas as páginas, porque uma imagem bonita de um projeto não aprovado é
  fácil de ser confundida com projeto pronto para executar.
"""

from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas

from ..engine.trace import fmt
from ..marca import ASSINATURA, NOME_SOFTWARE, PROGRAMADOR

AZUL = colors.HexColor("#1f4e79")
AZUL_CLARO = colors.HexColor("#DCE6F1")
CINZA = colors.HexColor("#5f6b78")
VERMELHO = colors.HexColor("#B00020")
VERDE = colors.HexColor("#2e7d32")
W, H = landscape(A4)
M = 14 * mm

PNG = b"\x89PNG\r\n\x1a\n"


class ImagemInvalida(ValueError):
    pass


def validar_imagem(dados: bytes, rotulo: str) -> ImageReader:
    if not dados.startswith(PNG):
        raise ImagemInvalida(f"Imagem '{rotulo}' não é PNG")
    try:
        img = ImageReader(io.BytesIO(dados))
        img.getSize()
    except Exception as e:  # reportlab/PIL levantam tipos variados para arquivo corrompido
        raise ImagemInvalida(f"Imagem '{rotulo}' corrompida: {e}") from e
    return img


def _situacao(ctx: dict) -> tuple[str, colors.Color]:
    if ctx["demonstrativo"]:
        return "DEMONSTRATIVO — DADOS FICTÍCIOS, NÃO USAR EM INSTALAÇÃO", VERMELHO
    if ctx["aprovado"]:
        ap = ctx.get("aprovacao") or {}
        reg = f" ({ap['registro']})" if ap.get("registro") else ""
        return f"APROVADO por {ap.get('nome', '-')}{reg} em {ap.get('data', '-')}", VERDE
    return "PRELIMINAR — sujeito à aprovação do engenheiro responsável", colors.HexColor("#b26a00")


def _rodape(c, ctx: dict, pagina: int):
    texto, cor = _situacao(ctx)
    c.setFillColor(cor)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(M, 9 * mm, texto)
    c.setFillColor(CINZA)
    c.setFont("Helvetica", 7)
    c.drawRightString(W - M, 9 * mm, f"{ctx['projeto']['codigo']} · cálculo nº {ctx['calculo_id']} de {ctx['calculo_data']} · página {pagina}")
    c.drawCentredString(W / 2, 4.5 * mm, ASSINATURA)


def _imagem(c, img: ImageReader, x, y, w, h, legenda: str | None = None):
    """Encaixa a imagem na caixa mantendo a proporção, com moldura e legenda."""
    iw, ih = img.getSize()
    alt_leg = 6 * mm if legenda else 0
    escala = min(w / iw, (h - alt_leg) / ih)
    dw, dh = iw * escala, ih * escala
    dx = x + (w - dw) / 2
    dy = y + alt_leg + (h - alt_leg - dh) / 2
    c.drawImage(img, dx, dy, dw, dh)
    c.setStrokeColor(colors.HexColor("#c9d2dc"))
    c.setLineWidth(0.6)
    c.rect(dx, dy, dw, dh)
    if legenda:
        c.setFillColor(CINZA)
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(x + w / 2, y + 1.5 * mm, legenda)


def _titulo_pagina(c, texto: str):
    c.setFillColor(AZUL)
    c.rect(0, H - 16 * mm, W, 16 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(M, H - 10.5 * mm, texto)


def _cartao(c, x, y, w, h, rotulo: str, valor: str, unidade: str = ""):
    c.setFillColor(AZUL_CLARO)
    c.roundRect(x, y, w, h, 2.5 * mm, stroke=0, fill=1)
    c.setFillColor(CINZA)
    c.setFont("Helvetica", 8)
    c.drawString(x + 4 * mm, y + h - 6 * mm, rotulo)
    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(x + 4 * mm, y + 5 * mm, valor)
    if unidade:
        c.setFont("Helvetica", 9)
        c.drawString(x + 4 * mm + c.stringWidth(valor, "Helvetica-Bold", 17) + 1.5 * mm, y + 5 * mm, unidade)


def _tabela(c, x, y_topo, larguras, linhas, alt=6 * mm) -> float:
    """Tabela simples; devolve o y logo abaixo dela."""
    y = y_topo
    for i, linha in enumerate(linhas):
        if i == 0:
            c.setFillColor(AZUL_CLARO)
            c.rect(x, y - alt, sum(larguras), alt, stroke=0, fill=1)
        c.setFillColor(colors.black if i else AZUL)
        c.setFont("Helvetica-Bold" if i == 0 else "Helvetica", 8.5)
        cx = x
        for j, (cel, lw) in enumerate(zip(linha, larguras)):
            texto = str(cel)
            while c.stringWidth(texto, "Helvetica", 8.5) > lw - 3 * mm and len(texto) > 3:
                texto = texto.rstrip("…")[:-1] + "…"
            if j == len(linha) - 1 and i > 0:
                c.drawRightString(cx + lw - 2 * mm, y - alt + 1.8 * mm, texto)
            else:
                c.drawString(cx + 2 * mm, y - alt + 1.8 * mm, texto)
            cx += lw
        c.setStrokeColor(colors.HexColor("#d5dbe2"))
        c.setLineWidth(0.4)
        c.line(x, y - alt, x + sum(larguras), y - alt)
        y -= alt
    return y


def apresentacao_pdf(ctx: dict, imagens: dict[str, ImageReader]) -> bytes:
    """ctx: projeto, resultado, calculo_id, calculo_data, aprovado, aprovacao,
    demonstrativo, cotas_informadas. imagens: 'geral' obrigatória; 'oposta',
    'cima', 'lateral' opcionais."""
    p = ctx["projeto"]
    r = ctx["resultado"]
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle(f"{p['codigo']} — Apresentação do sistema")
    c.setAuthor(PROGRAMADOR)
    c.setCreator(NOME_SOFTWARE)
    pagina = 1

    # ------------------------------------------------------------ capa
    c.setFillColor(AZUL)
    c.rect(0, H - 34 * mm, W, 34 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 10)
    c.drawString(M, H - 11 * mm, f"Apresentação do sistema · {p.get('modulo_nome') or ''}")
    c.setFont("Helvetica-Bold", 21)
    c.drawString(M, H - 21 * mm, p["nome"][:80])
    c.setFont("Helvetica", 10.5)
    linha = f"Cliente: {p.get('cliente') or 'não informado'}   ·   Projeto {p['codigo']}   ·   revisão {p.get('revisao', '-')}   ·   {datetime.now().strftime('%d/%m/%Y')}"
    c.drawString(M, H - 29 * mm, linha)
    texto, cor = _situacao(ctx)
    c.setFillColor(cor)
    c.roundRect(M, H - 44 * mm, c.stringWidth(texto, "Helvetica-Bold", 9.5) + 8 * mm, 7.5 * mm, 1.5 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(M + 4 * mm, H - 41.4 * mm, texto)
    _imagem(c, imagens["geral"], M, 16 * mm, W - 2 * M, H - 64 * mm, "Vista geral do sistema")
    _rodape(c, ctx, pagina)
    c.showPage()

    # ------------------------------------------------------------ vistas
    outras = [(k, t) for k, t in (("oposta", "Vista pelo lado oposto"), ("cima", "Vista de cima (planta)"), ("lateral", "Vista lateral (alturas)")) if k in imagens]
    if outras:
        pagina += 1
        _titulo_pagina(c, "Vistas do sistema")
        topo, base = H - 22 * mm, 16 * mm
        if len(outras) == 1:
            _imagem(c, imagens[outras[0][0]], M, base, W - 2 * M, topo - base, outras[0][1])
        else:
            # lateral (larga e baixa) ocupa a faixa de baixo inteira; as outras
            # dividem a faixa de cima
            lateral = next((x for x in outras if x[0] == "lateral"), None)
            cima = [x for x in outras if x[0] != "lateral"]
            meio = base + (topo - base) * (0.42 if lateral else 0)
            if lateral:
                _imagem(c, imagens["lateral"], M, base, W - 2 * M, meio - base - 2 * mm, lateral[1])
            larg = (W - 2 * M - 4 * mm * (len(cima) - 1)) / max(len(cima), 1)
            for i, (k, t) in enumerate(cima):
                _imagem(c, imagens[k], M + i * (larg + 4 * mm), meio, larg, topo - meio, t)
        _rodape(c, ctx, pagina)
        c.showPage()

    # ------------------------------------------------------------ resumo técnico
    pagina += 1
    _titulo_pagina(c, "Resumo técnico")
    sel = (r.get("selecao_exaustor") or {}).get("selecionado")
    cw = (W - 2 * M - 9 * mm) / 4
    y_c = H - 46 * mm
    _cartao(c, M, y_c, cw, 22 * mm, "Vazão total de exaustão", fmt(r.get("vazao_total_m3h"), 0), "m³/h")
    _cartao(c, M + (cw + 3 * mm), y_c, cw, 22 * mm, "Pressão estática do ventilador", fmt(r.get("pressao_estatica_ventilador_pa"), 0), "Pa")
    pot = sel.get("potencia_absorvida_kw") if sel else None
    _cartao(c, M + 2 * (cw + 3 * mm), y_c, cw, 22 * mm, "Potência absorvida", fmt(pot, 1) if pot is not None else "—", "kW" if pot is not None else "")
    _cartao(c, M + 3 * (cw + 3 * mm), y_c, cw, 22 * mm, "Pontos de captação", str(len(r.get("captores") or [])))

    col = (W - 2 * M - 8 * mm) / 2
    y = y_c - 8 * mm
    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(M, y, "Pontos de captação")
    linhas = [["Ponto", "Vazão (m³/h)"]] + [[x["label"], fmt(x["vazao_m3h"], 0)] for x in (r.get("captores") or [])]
    y_esq = _tabela(c, M, y - 3 * mm, [col - 35 * mm, 35 * mm], linhas[:16])
    if len(linhas) > 16:
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(CINZA)
        c.drawString(M, y_esq - 4 * mm, f"… e mais {len(linhas) - 16} ponto(s) — ver memorial de cálculo.")

    x2 = M + col + 8 * mm
    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x2, y, "Exaustor")
    c.setFont("Helvetica", 9.5)
    c.setFillColor(colors.black)
    if sel:
        op = sel["ponto_operacao"]
        tipo = "estática" if sel.get("tipo_pressao_curva") == "estatica" else "total"
        c.drawString(x2, y - 7 * mm, sel["nome"][:70])
        c.setFillColor(CINZA)
        c.drawString(x2, y - 12.5 * mm, f"Ponto de operação: {fmt(op['vazao_m3h'], 0)} m³/h a {fmt(op['pressao_pa'], 0)} Pa (pressão {tipo})")
    else:
        c.setFillColor(VERMELHO)
        c.drawString(x2, y - 7 * mm, "Nenhum exaustor do catálogo atende — equipamento a definir.")

    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x2, y - 24 * mm, "Dutos")
    resumo = r.get("resumo_dutos_m") or {}
    nomes_mat = {"galvanizado": "galvanizado", "aco_carbono": "aço carbono", "inox": "inox", "pvc": "PVC"}
    linhas = [["Seção / material", "Comprimento (m)"]]
    for chave, comp in sorted(resumo.items()):
        sec, _, mat = chave.partition("|")
        linhas.append([f"{sec} {nomes_mat.get(mat, mat)}", fmt(comp, 1)])
    linhas.append(["Total", fmt(sum(resumo.values()), 1)])
    _tabela(c, x2, y - 27 * mm, [col - 35 * mm, 35 * mm], linhas[:14])
    _rodape(c, ctx, pagina)
    c.showPage()

    # ------------------------------------------------------------ observações
    pagina += 1
    _titulo_pagina(c, "Observações")
    obs = [
        "Os valores desta apresentação vêm do cálculo indicado no rodapé, feito pelo software com os dados de projeto "
        "disponíveis naquela data. O memorial de cálculo traz fórmulas, hipóteses e parâmetros utilizados.",
        "As imagens são uma representação do traçado: coifas, filtro e exaustor aparecem como símbolos, sem as dimensões reais "
        "dos equipamentos, e obstáculos com altura ilustrativa.",
    ]
    if not ctx.get("cotas_informadas"):
        obs.append("As alturas dos dutos e equipamentos nas imagens são ILUSTRATIVAS: as cotas ainda não foram levantadas e "
                   "as descidas verticais não estão no cálculo.")
    if ctx["demonstrativo"]:
        obs.append("PROJETO DEMONSTRATIVO com dados fictícios: não serve para orçamento, fabricação ou instalação.")
    elif not ctx["aprovado"]:
        obs.append("Projeto PRELIMINAR: só deve ser usado para fabricação e instalação depois de aprovado pelo engenheiro "
                   "responsável legalmente habilitado.")
    if r.get("bloqueios"):
        obs.append(f"O cálculo tem {len(r['bloqueios'])} pendência(s) técnica(s) em aberto, listadas no memorial de cálculo.")
    y = H - 30 * mm
    c.setFont("Helvetica", 10)
    for i, o in enumerate(obs, 1):
        c.setFillColor(VERMELHO if ("FICTÍCIOS" in o or "ILUSTRATIVAS" in o or "fictícios" in o) else colors.black)
        palavras, linha = o.split(), f"{i}. "
        for pal in palavras:
            if c.stringWidth(linha + pal, "Helvetica", 10) > W - 2 * M - 6 * mm:
                c.drawString(M, y, linha)
                y -= 5.2 * mm
                linha = "    "
            linha += pal + " "
        c.drawString(M, y, linha)
        y -= 8 * mm
    _rodape(c, ctx, pagina)
    c.showPage()
    c.save()
    return buf.getvalue()
