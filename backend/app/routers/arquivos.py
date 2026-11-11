import io
import math
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import registrar
from ..cad import detect, dwg
from ..cad.dxf_import import ImportacaoErro, ler_dxf
from ..cad.pdf_import import PDFErro, ler_pdf
from ..config import get_settings
from ..db import get_db
from ..models import Arquivo, Planta, Projeto, Usuario
from ..security import exige
from ..storage import storage
from ..util import obter, to_dict

router = APIRouter(prefix="/api", tags=["arquivos e plantas"])

EXT_PROIBIDAS = {".exe", ".bat", ".cmd", ".sh", ".js", ".html", ".htm", ".svg", ".php"}


async def _ler_upload(f: UploadFile) -> bytes:
    lim = get_settings().max_upload_mb * 1024 * 1024
    dados = await f.read(lim + 1)
    if len(dados) > lim:
        raise HTTPException(413, f"Arquivo maior que {get_settings().max_upload_mb} MB")
    if not dados:
        raise HTTPException(422, "Arquivo vazio")
    return dados


def salvar_arquivo(db: Session, dados: bytes, nome: str, mime: str | None, u: Usuario, **kw) -> Arquivo:
    if Path(nome).suffix.lower() in EXT_PROIBIDAS:
        raise HTTPException(422, "Tipo de arquivo não permitido")
    chave, sha = storage().salvar(dados, nome)
    a = Arquivo(nome=Path(nome).name[:300], tipo_mime=mime, tamanho=len(dados), sha256=sha, chave=chave, enviado_por=u.id, **kw)
    db.add(a)
    db.flush()
    return a


@router.post("/arquivos")
async def enviar(arquivo: UploadFile = File(...), categoria: str = Form("documento"), projeto_id: int | None = Form(None),
                 visita_id: int | None = Form(None), projeto_antigo_id: int | None = Form(None), descricao: str | None = Form(None),
                 u: Usuario = Depends(exige("visitas.editar")), db: Session = Depends(get_db)):
    dados = await _ler_upload(arquivo)
    a = salvar_arquivo(db, dados, arquivo.filename or "arquivo", arquivo.content_type, u, categoria=categoria,
                       projeto_id=projeto_id, visita_id=visita_id, projeto_antigo_id=projeto_antigo_id, descricao=descricao)
    registrar(db, u, "enviar_arquivo", "arquivo", a.id, {"nome": a.nome, "projeto_id": projeto_id, "visita_id": visita_id, "projeto_antigo_id": projeto_antigo_id})
    db.commit()
    return to_dict(a, excluir=("chave",))


@router.get("/arquivos")
def listar(projeto_id: int | None = None, visita_id: int | None = None, projeto_antigo_id: int | None = None,
           _: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    q = select(Arquivo)
    if projeto_id:
        q = q.where(Arquivo.projeto_id == projeto_id)
    if visita_id:
        q = q.where(Arquivo.visita_id == visita_id)
    if projeto_antigo_id:
        q = q.where(Arquivo.projeto_antigo_id == projeto_antigo_id)
    return [to_dict(a, excluir=("chave",)) for a in db.scalars(q.order_by(Arquivo.id.desc()).limit(500)).all()]


@router.get("/arquivos/{aid}/download")
def baixar(aid: int, _: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    a = obter(db, Arquivo, aid, "Arquivo")
    return FileResponse(storage().caminho(a.chave), filename=a.nome, media_type=a.tipo_mime or "application/octet-stream")


# ------------------------------------------------------------------ plantas
def planta_resumo(p: Planta) -> dict:
    d = to_dict(p, excluir=("geometria",))
    g = p.geometria or {}
    d["n_entidades"] = len(g.get("entidades", []))
    d["camadas"] = g.get("camadas", [])
    d["extensao"] = g.get("extensao")
    d["avisos"] = g.get("avisos", [])
    d["sugestao_escala"] = g.get("sugestao_escala")
    return d


@router.post("/projetos/{pid}/plantas")
async def importar_planta(pid: int, arquivo: UploadFile = File(...), pagina: int = Form(1),
                          u: Usuario = Depends(exige("projetos.editar")), db: Session = Depends(get_db)):
    obter(db, Projeto, pid, "Projeto")
    dados = await _ler_upload(arquivo)
    nome = arquivo.filename or "planta"
    ext = Path(nome).suffix.lower()
    a = salvar_arquivo(db, dados, nome, arquivo.content_type, u, categoria="planta", projeto_id=pid)
    img_id = None
    if ext == ".dwg":
        try:
            dados = dwg.converter_dwg_para_dxf(dados)
        except dwg.DWGIndisponivel as e:
            db.commit()  # mantém o arquivo anexado ao projeto
            raise HTTPException(422, str(e))
        ext = ".dxf"
        origem = "dwg"
    else:
        origem = {".dxf": "dxf", ".pdf": "pdf", ".png": "imagem", ".jpg": "imagem", ".jpeg": "imagem"}.get(ext)
    if origem is None:
        raise HTTPException(422, "Formato não suportado. Use DXF, DWG (com conversor configurado), PDF, PNG ou JPG.")
    escala, confirmada, unidade, info = None, False, None, {}
    if ext == ".dxf":
        try:
            geo = ler_dxf(dados)
        except ImportacaoErro as e:
            raise HTTPException(422, str(e))
        escala = geo.get("escala_m_por_unidade")
        unidade = geo.get("unidade")
        info = {"fonte": f"$INSUNITS do DXF ({unidade})"} if escala else {}
        # Escala declarada no arquivo ainda deve ser conferida pelo usuário
        confirmada = False
    elif ext == ".pdf":
        try:
            geo = ler_pdf(dados, pagina - 1)
        except PDFErro as e:
            raise HTTPException(422, str(e))
        png = geo.pop("png")
        img = salvar_arquivo(db, png, Path(nome).stem + f"_p{pagina}.png", "image/png", u, categoria="planta_imagem", projeto_id=pid)
        img_id = img.id
        unidade = "pt"
        geo["imagem"] = {"largura": geo.pop("largura_png_pt"), "altura": geo.pop("altura_png_pt")}
    else:
        from PIL import Image
        try:
            im = Image.open(io.BytesIO(dados))
            w, h = im.size
        except Exception:
            raise HTTPException(422, "Imagem inválida")
        img_id = a.id
        unidade = "px"
        geo = {"entidades": [], "camadas": [], "extensao": [0, 0, w, h], "imagem": {"largura": w, "altura": h},
               "avisos": ["Imagem raster: identificação automática não disponível. Calibre a escala e desenhe os elementos manualmente."]}
    pl = Planta(projeto_id=pid, arquivo_id=a.id, nome=nome, origem=origem, unidade_original=unidade, escala_m_por_unidade=escala,
                escala_confirmada=confirmada, escala_info=info, geometria=geo, deteccoes=detect.detectar(geo, escala),
                imagem_arquivo_id=img_id, pagina=pagina if ext == ".pdf" else None)
    db.add(pl)
    db.flush()
    registrar(db, u, "importar_planta", "projeto", pid, {"planta_id": pl.id, "arquivo": nome, "origem": origem})
    db.commit()
    return planta_resumo(pl)


@router.get("/projetos/{pid}/plantas")
def listar_plantas(pid: int, _: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    return [planta_resumo(p) for p in db.scalars(select(Planta).where(Planta.projeto_id == pid).order_by(Planta.id.desc())).all()]


@router.get("/plantas/{plid}")
def obter_planta(plid: int, _: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    p = obter(db, Planta, plid, "Planta")
    d = planta_resumo(p)
    d["geometria"] = p.geometria
    d["deteccoes"] = p.deteccoes
    return d


@router.put("/plantas/{plid}/escala")
def calibrar(plid: int, d: dict, u: Usuario = Depends(exige("projetos.editar")), db: Session = Depends(get_db)):
    """Opções: {"escala_m_por_unidade": x, "confirmar": true} ou
    {"p1": [x,y], "p2": [x,y], "distancia_m": D} (coordenadas do desenho)."""
    p = obter(db, Planta, plid, "Planta")
    if "p1" in d:
        dist_un = math.dist(d["p1"], d["p2"])
        if dist_un <= 0 or not d.get("distancia_m") or float(d["distancia_m"]) <= 0:
            raise HTTPException(422, "Pontos/distância inválidos")
        esc = float(d["distancia_m"]) / dist_un
        info = {"metodo": "calibracao_2_pontos", "p1": d["p1"], "p2": d["p2"], "distancia_m": float(d["distancia_m"])}
    elif d.get("escala_m_por_unidade"):
        esc = float(d["escala_m_por_unidade"])
        info = {"metodo": "informada", "fonte": d.get("fonte") or "usuário"}
    else:
        raise HTTPException(422, "Informe a escala ou dois pontos com a distância real")
    if not (1e-7 < esc < 1e4):
        raise HTTPException(422, "Escala fora de faixa plausível")
    p.escala_m_por_unidade = esc
    p.escala_confirmada = bool(d.get("confirmar", True))
    p.escala_info = {**info, "por": u.nome}
    p.deteccoes = detect.detectar(p.geometria, esc)
    registrar(db, u, "calibrar_planta", "projeto", p.projeto_id, {"planta_id": p.id, "escala_m_por_unidade": esc, "metodo": info["metodo"]})
    db.commit()
    return planta_resumo(p)


@router.put("/plantas/{plid}/deteccoes")
def editar_deteccoes(plid: int, d: dict, u: Usuario = Depends(exige("projetos.editar")), db: Session = Depends(get_db)):
    p = obter(db, Planta, plid, "Planta")
    p.deteccoes = d
    registrar(db, u, "editar_deteccoes", "projeto", p.projeto_id, {"planta_id": p.id})
    db.commit()
    return {"ok": True}


@router.post("/plantas/{plid}/aplicar-ambiente")
def aplicar_ambiente(plid: int, u: Usuario = Depends(exige("projetos.editar")), db: Session = Depends(get_db)):
    """Copia contorno, pilares e máquinas (em metros) para o ambiente do projeto."""
    p = obter(db, Planta, plid, "Planta")
    if not p.escala_confirmada:
        raise HTTPException(409, "Confirme a escala da planta antes de usar suas medidas.")
    proj = db.get(Projeto, p.projeto_id)
    det = p.deteccoes or {}
    amb = dict(proj.ambiente or {})
    if det.get("contorno"):
        amb["contorno"] = det["contorno"]["pontos"]
    amb["pilares"] = [{"pontos": x["pontos"]} for x in det.get("pilares", [])]
    amb["obstaculos"] = [{"pontos": x["pontos"], "nome": x.get("nome")} for x in det.get("maquinas", [])]
    amb["planta_id"] = p.id
    proj.ambiente = amb
    ent = dict(proj.entradas or {})
    pts = amb.get("contorno")
    if pts:
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        for k, v, rot in (("comprimento_m", max(xs) - min(xs), "Comprimento do ambiente"), ("largura_m", max(ys) - min(ys), "Largura do ambiente")):
            if k not in ent or ent[k].get("status") != "confirmado":
                ent[k] = {"valor": round(v, 2), "unidade": "m", "rotulo": rot, "status": "estimado", "fonte": f"Planta {p.nome}"}
    if det.get("pe_direito_m") and ent.get("pe_direito_m", {}).get("status") != "confirmado":
        ent["pe_direito_m"] = {"valor": det["pe_direito_m"]["valor_m"], "unidade": "m", "rotulo": "Pé-direito", "status": "estimado", "fonte": f"Texto da planta: {det['pe_direito_m']['texto']}"}
    proj.entradas = ent
    registrar(db, u, "aplicar_planta_ambiente", "projeto", proj.id, {"planta_id": p.id, "pilares": len(amb["pilares"]), "obstaculos": len(amb["obstaculos"])})
    db.commit()
    return {"ambiente": amb}
