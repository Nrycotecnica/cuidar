"""Importação de PDF de plantas.

* Extração vetorial com pdfplumber (linhas, retângulos e curvas) — unidades em
  pontos tipográficos (1/72 pol) no papel.
* Renderização da página em PNG com pypdfium2 para uso como fundo.
* A escala NUNCA é assumida: o usuário deve calibrar (dois pontos + distância
  real). Uma indicação textual "ESC 1:100" é apenas sugestão.
"""

from __future__ import annotations

import io
import re
import tempfile
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium

PT_M = 0.0254 / 72.0
RE_ESCALA = re.compile(r"ESC(?:ALA)?\.?\s*[:=]?\s*1\s*[:/]\s*([0-9]{1,5})", re.I)
MAX_ENT = 200_000


class PDFErro(ValueError):
    pass


def ler_pdf(dados: bytes, pagina: int = 0) -> dict:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "entrada.pdf"
        p.write_bytes(dados)
        try:
            pdf = pdfplumber.open(str(p))
        except Exception as e:  # pdfminer lança várias exceções
            raise PDFErro(f"PDF inválido: {e}") from e
        with pdf:
            n = len(pdf.pages)
            if pagina < 0 or pagina >= n:
                raise PDFErro(f"Página {pagina+1} inexistente (o PDF tem {n})")
            pg = pdf.pages[pagina]
            H = float(pg.height)
            ents = []

            def yy(top):
                return round(H - float(top), 3)

            for ln in pg.lines:
                pts = ln.get("pts") or [(ln["x0"], ln["top"]), (ln["x1"], ln["bottom"])]
                flat = []
                for x, t in pts:
                    flat += [round(float(x), 3), yy(t)]
                ents.append({"t": "P", "l": 0, "p": flat, "c": False})
            for r in pg.rects:
                x0, x1 = float(r["x0"]), float(r["x1"])
                y0, y1 = yy(r["bottom"]), yy(r["top"])
                ents.append({"t": "P", "l": 1, "p": [x0, y0, x1, y0, x1, y1, x0, y1], "c": True})
            for c in pg.curves:
                flat = []
                for x, t in c.get("pts") or []:
                    flat += [round(float(x), 3), yy(t)]
                if len(flat) >= 4:
                    ents.append({"t": "P", "l": 2, "p": flat, "c": False})
                if len(ents) > MAX_ENT:
                    break
            sugestao = None
            textos = []
            for w in pg.extract_words()[:5000]:
                textos.append({"t": "T", "l": 3, "p": [round(float(w["x0"]), 2), yy(w["bottom"])],
                               "h": round(float(w["bottom"]) - float(w["top"]), 2), "s": w["text"], "r": 0})
            texto_pg = pg.extract_text() or ""
            m = RE_ESCALA.search(texto_pg)
            if m:
                den = int(m.group(1))
                sugestao = {"texto": m.group(0), "denominador": den, "escala_m_por_unidade": PT_M * den}
            largura, altura = float(pg.width), H
        png = renderizar(dados, pagina)
    ents += textos
    return {
        "entidades": ents,
        "camadas": [{"nome": "PDF-LINHAS", "cor": 7}, {"nome": "PDF-RETANGULOS", "cor": 5},
                    {"nome": "PDF-CURVAS", "cor": 3}, {"nome": "PDF-TEXTO", "cor": 2}],
        "extensao": [0.0, 0.0, largura, altura],
        "unidade": "pt",
        "paginas": n,
        "pagina": pagina,
        "sugestao_escala": sugestao,
        "vetorial": len(ents) - len(textos) > 0,
        "avisos": ([] if len(ents) - len(textos) > 0 else ["Nenhum vetor encontrado: o PDF provavelmente é digitalizado (imagem). Use a imagem de fundo e calibre a escala."]),
        "png": png,
        "largura_png_pt": largura,
        "altura_png_pt": altura,
    }


def renderizar(dados: bytes, pagina: int = 0, escala: float = 2.0) -> bytes:
    doc = pdfium.PdfDocument(dados)
    try:
        pg = doc[pagina]
        img = pg.render(scale=escala).to_pil()
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    finally:
        doc.close()
