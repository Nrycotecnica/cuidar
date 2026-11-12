import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import registrar
from ..cad.dxf_export import gerar_dxf
from ..db import get_db
from ..docs import apresentacao, bom, pdf
from ..engine.cotas import cota_da_rede
from ..models import Calculo, Exaustor, Projeto, Rede, Usuario
from ..security import exige, tem
from .. import services as sv
from ..util import obter, to_dict

router = APIRouter(prefix="/api/calculos", tags=["cálculos e exportações"])


def _ctx(db: Session, cid: int):
    c = obter(db, Calculo, cid, "Cálculo")
    p = db.get(Projeto, c.projeto_id)
    rede = (c.entradas or {}).get("rede") or {"nodes": [], "segments": []}
    aprovado = p.calculo_aprovado_id == c.id and p.status in ("aprovado", "liberado_fabricacao")
    pd = {"codigo": p.codigo, "nome": p.nome, "cliente": p.cliente.nome if p.cliente else None, "modulo": p.modulo,
          "modulo_nome": sv.MODULOS.get(p.modulo), "status": p.status}
    return c, p, rede, aprovado, pd


@router.get("/{cid}")
def obter_calculo(cid: int, _: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    return to_dict(obter(db, Calculo, cid, "Cálculo"))


def _nome(p: Projeto, c: Calculo, ext: str, aprovado: bool) -> str:
    return f"{p.codigo}_calc{c.id}_{'APROVADO' if aprovado else 'PRELIMINAR'}.{ext}"


def _resp(dados: bytes, nome: str, tipo: str) -> Response:
    return Response(dados, media_type=tipo, headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@router.get("/{cid}/dxf")
def exportar_dxf(cid: int, u: Usuario = Depends(exige("exportar")), db: Session = Depends(get_db)):
    c, p, rede, aprovado, pd = _ctx(db, cid)
    ref = None
    from sqlalchemy import select
    from ..models import Planta
    pl = db.scalars(select(Planta).where(Planta.projeto_id == p.id, Planta.escala_confirmada.is_(True), Planta.origem == "dxf").order_by(Planta.id.desc())).first()
    if pl:
        ref = {**pl.geometria, "escala_m_por_unidade": pl.escala_m_por_unidade}
    dados = gerar_dxf(pd, rede, c.resultados, p.ambiente, ref, aprovado, p.demonstrativo)
    registrar(db, u, "exportar_dxf", "projeto", p.id, {"calculo_id": c.id})
    db.commit()
    return _resp(dados, _nome(p, c, "dxf", aprovado), "application/dxf")


@router.get("/{cid}/desenho.pdf")
def exportar_desenho_pdf(cid: int, u: Usuario = Depends(exige("exportar")), db: Session = Depends(get_db)):
    c, p, rede, aprovado, pd = _ctx(db, cid)
    dados = pdf.desenho_pdf(pd, rede, c.resultados if c.tipo == "rede" else None, p.ambiente, aprovado, p.demonstrativo)
    return _resp(dados, _nome(p, c, "pdf", aprovado).replace(".pdf", "_desenho.pdf"), "application/pdf")


@router.get("/{cid}/memorial.pdf")
def exportar_memorial(cid: int, u: Usuario = Depends(exige("exportar")), db: Session = Depends(get_db)):
    c, p, rede, aprovado, pd = _ctx(db, cid)
    ap = None
    if aprovado and p.aprovado_por:
        eng = db.get(Usuario, p.aprovado_por)
        ap = {"nome": eng.nome, "registro": eng.registro_profissional, "data": p.aprovado_em.strftime("%d/%m/%Y %H:%M")}
    ctx = {
        "projeto": pd, "resultado": c.resultados, "entradas": (c.entradas or {}).get("entradas_projeto") or {},
        "calculo_id": c.id, "calculo_data": c.criado_em.strftime("%d/%m/%Y %H:%M"), "versao_app": c.versao_app,
        "seguranca": sv.avaliar_seguranca(p), "aprovado": aprovado, "aprovacao": ap, "demonstrativo": p.demonstrativo,
        "exaustor_escolhido_manual": (c.resultados.get("selecao_exaustor") or {}).get("escolha_manual"),
    }
    dados = pdf.memorial_pdf(ctx)
    registrar(db, u, "exportar_memorial", "projeto", p.id, {"calculo_id": c.id})
    db.commit()
    return _resp(dados, _nome(p, c, "pdf", aprovado).replace(".pdf", "_memorial.pdf"), "application/pdf")


VISTAS = {"geral", "oposta", "cima", "lateral"}
LIMITE_IMAGEM = 12 * 1024 * 1024  # PNG de 2400 px fica em ~1–4 MB; acima disso é erro, não foto


@router.post("/{cid}/apresentacao.pdf")
def exportar_apresentacao(cid: int, d: dict, u: Usuario = Depends(exige("exportar")), db: Session = Depends(get_db)):
    """PDF para o cliente com as vistas 3D renderizadas no navegador.

    Só aceita o cálculo da rede ATUAL: as imagens mostram a rede de agora, e uma
    capa com o desenho novo e os números de um cálculo antigo seria uma
    apresentação que se contradiz."""
    c, p, rede, aprovado, pd = _ctx(db, cid)
    if c.tipo != "rede":
        raise HTTPException(422, "Apresentação disponível para cálculos de rede de dutos")
    atual = db.scalars(select(Rede).where(Rede.projeto_id == p.id).order_by(Rede.id)).first()
    if not atual or c.rede_versao != atual.versao:
        raise HTTPException(409, f"O cálculo nº {c.id} é de uma versão anterior da rede. Calcule de novo antes de gerar a apresentação.")
    brutas = d.get("imagens") or {}
    if not isinstance(brutas, dict) or "geral" not in brutas or not set(brutas) <= VISTAS:
        raise HTTPException(422, "Envie as imagens das vistas (geral obrigatória; oposta, cima e lateral opcionais)")
    imagens = {}
    for chave, b64 in brutas.items():
        try:
            dados = base64.b64decode(str(b64).split(",", 1)[-1], validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(422, f"Imagem '{chave}' em formato inválido")
        if len(dados) > LIMITE_IMAGEM:
            raise HTTPException(413, f"Imagem '{chave}' grande demais")
        try:
            imagens[chave] = apresentacao.validar_imagem(dados, chave)
        except apresentacao.ImagemInvalida as e:
            raise HTTPException(422, str(e))
    ap = None
    if aprovado and p.aprovado_por:
        eng = db.get(Usuario, p.aprovado_por)
        ap = {"nome": eng.nome, "registro": eng.registro_profissional, "data": p.aprovado_em.strftime("%d/%m/%Y")}
    ctx = {
        "projeto": {**pd, "revisao": p.versao}, "resultado": c.resultados, "calculo_id": c.id,
        "calculo_data": c.criado_em.strftime("%d/%m/%Y"), "aprovado": aprovado, "aprovacao": ap,
        "demonstrativo": p.demonstrativo, "cotas_informadas": cota_da_rede(atual.dados or {}) is not None,
    }
    dados_pdf = apresentacao.apresentacao_pdf(ctx, imagens)
    registrar(db, u, "exportar_apresentacao", "projeto", p.id, {"calculo_id": c.id, "vistas": sorted(imagens)})
    db.commit()
    return _resp(dados_pdf, _nome(p, c, "pdf", aprovado).replace(".pdf", "_apresentacao.pdf"), "application/pdf")


def _lista(db: Session, c: Calculo, p: Projeto, rede: dict, u: Usuario) -> dict:
    if c.tipo != "rede":
        raise HTTPException(422, "Lista de materiais disponível para cálculos de rede de dutos")
    ps = sv.parametros(db)
    esp = float(ps.get("espacamento_suportes_m")) if ps.tem("espacamento_suportes_m") else None
    sel = (c.resultados.get("selecao_exaustor") or {}).get("selecionado")
    ex = sv.exaustor_dict(db.get(Exaustor, sel["id"])) if sel and db.get(Exaustor, sel["id"]) else None
    liberado = p.status == "liberado_fabricacao" and p.calculo_aprovado_id == c.id
    lista = bom.gerar_lista({}, rede, c.resultados, sv.componentes_dict(db), ex, esp, liberado)
    if not tem(u, "orcamento.ver"):
        for i in lista["itens"]:
            i["custo_unitario"] = i["custo_total"] = None
        lista["total_custo"] = None
    if p.demonstrativo:
        lista["situacao"] += " — DADOS DEMONSTRATIVOS (FICTÍCIOS)"
    return lista


@router.get("/{cid}/lista")
def lista_json(cid: int, u: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    c, p, rede, aprovado, pd = _ctx(db, cid)
    return _lista(db, c, p, rede, u)


@router.get("/{cid}/lista.{fmt_}")
def lista_arquivo(cid: int, fmt_: str, u: Usuario = Depends(exige("exportar")), db: Session = Depends(get_db)):
    c, p, rede, aprovado, pd = _ctx(db, cid)
    lista = _lista(db, c, p, rede, u)
    lista.setdefault("total_custo", 0)
    if lista["total_custo"] is None:
        lista["total_custo"] = 0
    titulo = f"Lista de materiais — {p.codigo} — {p.nome} (cálculo {c.id})"
    nome = f"{p.codigo}_calc{c.id}_lista_{'LIBERADA' if lista['liberado'] else 'PRELIMINAR'}"
    registrar(db, u, f"exportar_lista_{fmt_}", "projeto", p.id, {"calculo_id": c.id})
    db.commit()
    if fmt_ == "csv":
        return _resp(bom.para_csv(lista), nome + ".csv", "text/csv; charset=utf-8")
    if fmt_ == "xlsx":
        return _resp(bom.para_xlsx(lista, titulo), nome + ".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if fmt_ == "pdf":
        return _resp(pdf.lista_pdf(lista, titulo), nome + ".pdf", "application/pdf")
    raise HTTPException(404, "Formato não suportado (csv, xlsx, pdf)")
