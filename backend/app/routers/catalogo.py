import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import registrar
from ..db import get_db
from ..engine import units
from ..engine.air import densidade
from ..engine.fans import Curva, CurvaInvalida
from ..models import ComponenteDuto, Exaustor, ParametroTecnico, Usuario
from ..security import exige, tem
from ..util import aplicar, obter, to_dict

router = APIRouter(prefix="/api", tags=["catálogo técnico"])

CAMPOS_EX = {"codigo", "modelo", "tipo", "rotacao_rpm", "potencia_motor_kw", "rendimento", "diametro_rotor_mm", "boca_entrada_mm",
             "boca_saida", "dimensoes", "materiais", "temperatura_max_c", "limites", "densidade_referencia", "tipo_pressao_curva",
             "curva", "preco", "custo_fabricacao", "observacoes", "ativo"}
CAMPOS_CUSTO = {"preco", "custo_fabricacao"}
CAMPOS_COMP = {"codigo", "categoria", "descricao", "forma", "diametro_mm", "diametro2_mm", "largura_mm", "altura_mm", "espessura_mm",
               "material", "comprimento_m", "angulo_graus", "coef_perda_k", "massa_kg", "unidade", "custo_unitario", "ativo"}
CATEGORIAS_COMP = {"duto_circular": "Duto circular", "duto_retangular": "Duto retangular", "curva": "Curva", "reducao": "Redução",
                   "derivacao": "Derivação", "flange": "Flange", "conexao": "Conexão", "suporte": "Suporte", "captor": "Captor",
                   "registro": "Registro/damper", "chapeu": "Chapéu/terminal"}


def _validar_curva(curva, tipo_pressao):
    try:
        Curva.from_pontos(curva or [], tipo_pressao or "estatica")
    except (CurvaInvalida, KeyError, TypeError, ValueError) as e:
        raise HTTPException(422, f"Curva de desempenho inválida: {e}")


def _pode_editar_ex(u: Usuario, d: dict):
    campos = set(d) & CAMPOS_EX
    if campos - CAMPOS_CUSTO and not tem(u, "catalogo.editar"):
        raise HTTPException(403, "Sem permissão para editar dados técnicos do catálogo")
    if campos & CAMPOS_CUSTO and not (tem(u, "custos.editar") or tem(u, "catalogo.editar")):
        raise HTTPException(403, "Sem permissão para editar custos")


# ------------------------------------------------------------------ exaustores
@router.get("/exaustores")
def listar_ex(u: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    out = []
    for e in db.scalars(select(Exaustor).order_by(Exaustor.codigo)).all():
        d = to_dict(e)
        if not tem(u, "orcamento.ver"):
            d["preco"] = d["custo_fabricacao"] = None
        out.append(d)
    return out


@router.post("/exaustores")
def criar_ex(d: dict, u: Usuario = Depends(exige("catalogo.editar")), db: Session = Depends(get_db)):
    if not d.get("codigo") or not d.get("modelo") or not d.get("tipo"):
        raise HTTPException(422, "Código, modelo e tipo são obrigatórios")
    if db.scalars(select(Exaustor).where(Exaustor.codigo == d["codigo"])).first():
        raise HTTPException(409, "Código já cadastrado")
    _validar_curva(d.get("curva"), d.get("tipo_pressao_curva"))
    e = Exaustor(**{k: v for k, v in d.items() if k in CAMPOS_EX}, status="proposto")
    db.add(e)
    db.flush()
    registrar(db, u, "criar", "exaustor", e.id, {"codigo": e.codigo})
    db.commit()
    return to_dict(e)


@router.get("/exaustores/{eid}")
def obter_ex(eid: int, u: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    d = to_dict(obter(db, Exaustor, eid, "Exaustor"))
    if not tem(u, "orcamento.ver"):
        d["preco"] = d["custo_fabricacao"] = None
    return d


@router.put("/exaustores/{eid}")
def editar_ex(eid: int, d: dict, u: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    _pode_editar_ex(u, d)
    e = obter(db, Exaustor, eid, "Exaustor")
    if "curva" in d or "tipo_pressao_curva" in d:
        _validar_curva(d.get("curva", e.curva), d.get("tipo_pressao_curva", e.tipo_pressao_curva))
    alt = aplicar(e, d, CAMPOS_EX)
    if set(alt) - CAMPOS_CUSTO:
        e.status = "proposto"  # dado técnico alterado volta a exigir aprovação
    registrar(db, u, "editar", "exaustor", e.id, alt)
    db.commit()
    return to_dict(e)


@router.post("/exaustores/{eid}/aprovar")
def aprovar_ex(eid: int, u: Usuario = Depends(exige("parametros.aprovar")), db: Session = Depends(get_db)):
    e = obter(db, Exaustor, eid, "Exaustor")
    if e.demonstrativo:
        raise HTTPException(409, "Equipamento demonstrativo (fictício) não pode ser aprovado")
    e.status = "aprovado"
    registrar(db, u, "aprovar", "exaustor", e.id)
    db.commit()
    return to_dict(e)


@router.get("/exaustores/{eid}/curva")
def consultar_curva(eid: int, vazao_m3h: float | None = None, temperatura_c: float = 20.0, altitude_m: float = 0.0,
                    _: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    """Consulta da curva com correção de densidade; retorna pontos e, opcionalmente, a pressão interpolada."""
    e = obter(db, Exaustor, eid, "Exaustor")
    c = Curva.from_pontos(e.curva, e.tipo_pressao_curva)
    rho = densidade(temperatura_c, altitude_m)
    fr = rho / (e.densidade_referencia or 1.2)
    out = {"tipo_pressao": e.tipo_pressao_curva, "densidade": rho, "fator_densidade": fr,
           "pontos": [{"vazao_m3h": q * 3600, "pressao_pa": p * fr, "potencia_kw": (c.pot[i] * fr / 1000 if c.pot else None)} for i, (q, p) in enumerate(zip(c.q, c.p))],
           "faixa_m3h": [c.q_min * 3600, c.q_max * 3600]}
    if vazao_m3h is not None:
        p = c.pressao(vazao_m3h / 3600)
        out["consulta"] = {"vazao_m3h": vazao_m3h, "pressao_pa": p * fr if p is not None else None,
                           "mensagem": None if p is not None else "Vazão fora da faixa cadastrada — não extrapolado"}
    return out


def _linhas_planilha(nome: str, dados: bytes) -> list[dict]:
    if nome.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(dados), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        cab = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
        return [dict(zip(cab, r)) for r in rows[1:] if any(v not in (None, "") for v in r)]
    txt = dados.decode("utf-8-sig", errors="replace")
    delim = ";" if txt.count(";") >= txt.count(",") else ","
    rd = csv.DictReader(io.StringIO(txt), delimiter=delim)
    return [{(k or "").strip().lower(): v for k, v in r.items()} for r in rd]


def _num(v):
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    return float(s)


@router.post("/exaustores/importar")
async def importar_ex(arquivo: UploadFile = File(...), u: Usuario = Depends(exige("catalogo.editar")), db: Session = Depends(get_db)):
    """Planilha com um ponto de curva por linha. Colunas: codigo, modelo, tipo, vazao, pressao, [potencia_kw],
    [unidade_vazao=m3/h], [unidade_pressao=pa], [tipo_pressao_curva=estatica], [rotacao_rpm], [potencia_motor_kw],
    [temperatura_max_c], [preco]."""
    linhas = _linhas_planilha(arquivo.filename or "", await arquivo.read())
    grupos: dict[str, list[dict]] = {}
    for r in linhas:
        cod = str(r.get("codigo") or "").strip()
        if cod:
            grupos.setdefault(cod, []).append(r)
    criados, atualizados, erros = [], [], []
    for cod, rs in grupos.items():
        r0 = rs[0]
        try:
            uq = r0.get("unidade_vazao") or "m3/h"
            up = r0.get("unidade_pressao") or "pa"
            curva = []
            for r in rs:
                q_m3s = units.convert(_num(r["vazao"]), uq, units.FLOW_TO_M3S)
                p_pa = units.convert(_num(r["pressao"]), up, units.PRESSURE_TO_PA)
                pt = {"vazao_m3h": round(q_m3s * 3600, 4), "pressao_pa": round(p_pa, 4)}
                if _num(r.get("potencia_kw")) is not None:
                    pt["potencia_kw"] = _num(r.get("potencia_kw"))
                curva.append(pt)
            tp = (r0.get("tipo_pressao_curva") or "estatica").strip().lower()
            Curva.from_pontos(curva, tp)
        except (ValueError, KeyError, TypeError, CurvaInvalida) as e:
            erros.append(f"{cod}: {e}")
            continue
        dados = {"modelo": r0.get("modelo") or cod, "tipo": r0.get("tipo") or "centrifugo", "curva": curva, "tipo_pressao_curva": tp,
                 "rotacao_rpm": _num(r0.get("rotacao_rpm")), "potencia_motor_kw": _num(r0.get("potencia_motor_kw")),
                 "temperatura_max_c": _num(r0.get("temperatura_max_c")), "preco": _num(r0.get("preco"))}
        e = db.scalars(select(Exaustor).where(Exaustor.codigo == cod)).first()
        if e:
            aplicar(e, dados, CAMPOS_EX)
            e.status = "proposto"
            atualizados.append(cod)
        else:
            db.add(Exaustor(codigo=cod, **dados, status="proposto"))
            criados.append(cod)
    registrar(db, u, "importar", "exaustor", None, {"arquivo": arquivo.filename, "criados": criados, "atualizados": atualizados, "erros": erros})
    db.commit()
    return {"criados": criados, "atualizados": atualizados, "erros": erros}


@router.get("/modelos/{tipo}.csv")
def modelo_planilha(tipo: str, _: Usuario = Depends(exige("ver"))):
    modelos = {
        "exaustores": "codigo;modelo;tipo;rotacao_rpm;potencia_motor_kw;temperatura_max_c;tipo_pressao_curva;unidade_vazao;unidade_pressao;vazao;pressao;potencia_kw;preco\n"
                      "EX-EXEMPLO;Modelo exemplo;centrifugo_radial;1750;7,5;80;estatica;m3/h;pa;2000;2500;3,1;\n"
                      "EX-EXEMPLO;;;;;;;;;4000;2300;4,4;\n",
        "componentes": "codigo;categoria;descricao;forma;diametro_mm;diametro2_mm;espessura_mm;material;comprimento_m;angulo_graus;massa_kg;unidade;custo_unitario\n"
                       "DT-300-GALV;duto_circular;Duto Ø300 galvanizado #24;circular;300;;0,65;galvanizado;3;;14,5;pç;\n",
        "parametros": "chave;valor;unidade;categoria;descricao;referencia\n"
                      "vel_transporte_min.poeira_exemplo;18;m/s;Velocidade de transporte;Descrição;Fonte bibliográfica\n",
    }
    if tipo not in modelos:
        raise HTTPException(404, "Modelo inexistente")
    return Response(("﻿" + modelos[tipo]).encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="modelo_{tipo}.csv"'})


# ------------------------------------------------------------------ componentes de dutos
@router.get("/componentes")
def listar_comp(u: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    out = []
    for c in db.scalars(select(ComponenteDuto).order_by(ComponenteDuto.categoria, ComponenteDuto.diametro_mm)).all():
        d = to_dict(c)
        if not tem(u, "orcamento.ver"):
            d["custo_unitario"] = None
        out.append(d)
    return out


@router.get("/componentes/categorias")
def categorias(_: Usuario = Depends(exige("ver"))):
    return CATEGORIAS_COMP


@router.post("/componentes")
def criar_comp(d: dict, u: Usuario = Depends(exige("catalogo.editar")), db: Session = Depends(get_db)):
    if not d.get("codigo") or d.get("categoria") not in CATEGORIAS_COMP or not d.get("descricao"):
        raise HTTPException(422, "Código, categoria válida e descrição são obrigatórios")
    if db.scalars(select(ComponenteDuto).where(ComponenteDuto.codigo == d["codigo"])).first():
        raise HTTPException(409, "Código já cadastrado")
    c = ComponenteDuto(**{k: v for k, v in d.items() if k in CAMPOS_COMP})
    db.add(c)
    db.flush()
    registrar(db, u, "criar", "componente", c.id, {"codigo": c.codigo})
    db.commit()
    return to_dict(c)


@router.put("/componentes/{cid}")
def editar_comp(cid: int, d: dict, u: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    if set(d) - {"custo_unitario"} and not tem(u, "catalogo.editar"):
        raise HTTPException(403, "Sem permissão para editar o catálogo")
    if "custo_unitario" in d and not (tem(u, "custos.editar") or tem(u, "catalogo.editar")):
        raise HTTPException(403, "Sem permissão para editar custos")
    c = obter(db, ComponenteDuto, cid, "Componente")
    alt = aplicar(c, d, CAMPOS_COMP)
    registrar(db, u, "editar", "componente", c.id, alt)
    db.commit()
    return to_dict(c)


@router.post("/componentes/importar")
async def importar_comp(arquivo: UploadFile = File(...), u: Usuario = Depends(exige("catalogo.editar")), db: Session = Depends(get_db)):
    linhas = _linhas_planilha(arquivo.filename or "", await arquivo.read())
    criados, atualizados, erros = [], [], []
    numericos = {"diametro_mm", "diametro2_mm", "largura_mm", "altura_mm", "espessura_mm", "comprimento_m", "angulo_graus", "coef_perda_k", "massa_kg", "custo_unitario"}
    for i, r in enumerate(linhas, 2):
        try:
            d = {}
            for k in CAMPOS_COMP:
                if k in r and r[k] not in (None, ""):
                    d[k] = _num(r[k]) if k in numericos else str(r[k]).strip()
            if not d.get("codigo") or d.get("categoria") not in CATEGORIAS_COMP or not d.get("descricao"):
                raise ValueError("código, categoria válida e descrição são obrigatórios")
        except ValueError as e:
            erros.append(f"Linha {i}: {e}")
            continue
        c = db.scalars(select(ComponenteDuto).where(ComponenteDuto.codigo == d["codigo"])).first()
        if c:
            aplicar(c, d, CAMPOS_COMP)
            atualizados.append(d["codigo"])
        else:
            db.add(ComponenteDuto(**d))
            criados.append(d["codigo"])
    registrar(db, u, "importar", "componente", None, {"arquivo": arquivo.filename, "criados": len(criados), "atualizados": len(atualizados), "erros": erros})
    db.commit()
    return {"criados": criados, "atualizados": atualizados, "erros": erros}


# ------------------------------------------------------------------ parâmetros técnicos
@router.get("/parametros")
def listar_par(_: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    return [to_dict(p) for p in db.scalars(select(ParametroTecnico).order_by(ParametroTecnico.categoria, ParametroTecnico.chave)).all()]


@router.post("/parametros")
def criar_par(d: dict, u: Usuario = Depends(exige("parametros.editar")), db: Session = Depends(get_db)):
    if not d.get("chave") or d.get("valor") in (None, ""):
        raise HTTPException(422, "Chave e valor são obrigatórios")
    if db.scalars(select(ParametroTecnico).where(ParametroTecnico.chave == d["chave"])).first():
        raise HTTPException(409, "Chave já cadastrada")
    if not (d.get("referencia") or "").strip():
        raise HTTPException(422, "Informe a referência técnica (norma, literatura ou ensaio) do parâmetro")
    p = ParametroTecnico(chave=d["chave"].strip(), valor=d["valor"], unidade=d.get("unidade"), categoria=d.get("categoria") or "Geral",
                         descricao=d.get("descricao"), referencia=d.get("referencia"), status="proposto")
    db.add(p)
    db.flush()
    registrar(db, u, "criar", "parametro", p.id, {"chave": p.chave, "valor": p.valor})
    db.commit()
    return to_dict(p)


@router.put("/parametros/{pid}")
def editar_par(pid: int, d: dict, u: Usuario = Depends(exige("parametros.editar")), db: Session = Depends(get_db)):
    p = obter(db, ParametroTecnico, pid, "Parâmetro")
    alt = aplicar(p, d, {"valor", "unidade", "categoria", "descricao", "referencia"})
    if "valor" in alt or "referencia" in alt or "unidade" in alt:
        p.status = "proposto"
        p.aprovado_por = p.aprovado_em = None
        if "referencia" in alt or "valor" in alt:
            p.demonstrativo = False if d.get("referencia") else p.demonstrativo
    registrar(db, u, "editar", "parametro", p.id, {"chave": p.chave, **alt})
    db.commit()
    return to_dict(p)


@router.post("/parametros/{pid}/aprovar")
def aprovar_par(pid: int, u: Usuario = Depends(exige("parametros.aprovar")), db: Session = Depends(get_db)):
    p = obter(db, ParametroTecnico, pid, "Parâmetro")
    if p.demonstrativo:
        raise HTTPException(409, "Valor demonstrativo: revise o valor e informe a referência técnica antes de aprovar")
    p.status = "aprovado"
    p.aprovado_por = u.id
    p.aprovado_em = datetime.now(timezone.utc)
    registrar(db, u, "aprovar", "parametro", p.id, {"chave": p.chave, "valor": p.valor})
    db.commit()
    return to_dict(p)
