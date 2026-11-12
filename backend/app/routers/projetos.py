from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import registrar
from ..db import get_db
from ..engine import seguranca as seg
from ..engine.routing import RoteamentoFalhou, rotear_rede
from ..models import Auditoria, Calculo, Cliente, Projeto, Rede, Usuario
from ..security import exige, tem
from .. import services as sv
from ..util import aplicar, obter, to_dict

router = APIRouter(prefix="/api/projetos", tags=["projetos"])

STATUS = {
    "rascunho": "Rascunho",
    "em_revisao": "Em revisão técnica",
    "aprovado": "Aprovado tecnicamente",
    "liberado_fabricacao": "Liberado para fabricação",
}
STATUS_ENTRADA = {"confirmado", "estimado", "nao_confirmado"}


def projeto_dict(db: Session, p: Projeto) -> dict:
    d = to_dict(p)
    d["status_nome"] = STATUS.get(p.status, p.status)
    d["modulo_nome"] = sv.MODULOS.get(p.modulo, p.modulo)
    d["cliente_nome"] = p.cliente.nome if p.cliente else None
    d["campos_entrada"] = [{"chave": c[0], "rotulo": c[1], "unidade": c[2], "obrigatorio": c[3]} for c in sv.campos_modulo(p.modulo)]
    return d


def exigir_editavel(p: Projeto):
    if p.status in ("aprovado", "liberado_fabricacao"):
        raise HTTPException(409, "Projeto aprovado: volte-o para rascunho (gera nova revisão) antes de editar.")


@router.get("")
def listar(_: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    return [projeto_dict(db, p) for p in db.scalars(select(Projeto).order_by(Projeto.atualizado_em.desc())).all()]


@router.post("")
def criar(d: dict, u: Usuario = Depends(exige("projetos.editar")), db: Session = Depends(get_db)):
    if d.get("modulo") not in sv.MODULOS:
        raise HTTPException(422, "Módulo inválido (poeira, fumos ou renovacao)")
    if not (d.get("nome") or "").strip():
        raise HTTPException(422, "Nome do projeto é obrigatório")
    if d.get("cliente_id"):
        obter(db, Cliente, d["cliente_id"], "Cliente")
    n = (db.scalar(select(func.count(Projeto.id))) or 0) + 1
    p = Projeto(
        codigo=d.get("codigo") or f"PRJ-{datetime.now().year}-{n:04d}",
        nome=d["nome"], cliente_id=d.get("cliente_id"), modulo=d["modulo"], descricao=d.get("descricao"),
        entradas={}, ambiente={}, riscos={}, checklist_seguranca={}, criado_por=u.id,
    )
    db.add(p)
    db.flush()
    db.add(Rede(projeto_id=p.id, dados={"nodes": [], "segments": []}))
    registrar(db, u, "criar", "projeto", p.id, {"codigo": p.codigo, "modulo": p.modulo})
    db.commit()
    return projeto_dict(db, p)


@router.get("/{pid}")
def obter_projeto(pid: int, _: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    return projeto_dict(db, obter(db, Projeto, pid, "Projeto"))


@router.put("/{pid}")
def editar(pid: int, d: dict, u: Usuario = Depends(exige("projetos.editar")), db: Session = Depends(get_db)):
    p = obter(db, Projeto, pid, "Projeto")
    exigir_editavel(p)
    alt = aplicar(p, d, {"nome", "cliente_id", "descricao", "ambiente"})
    registrar(db, u, "editar", "projeto", p.id, alt)
    db.commit()
    return projeto_dict(db, p)


@router.put("/{pid}/entradas")
def editar_entradas(pid: int, d: dict, u: Usuario = Depends(exige("projetos.editar")), db: Session = Depends(get_db)):
    """d = {chave: {valor, status, fonte}} — status: confirmado | estimado | nao_confirmado.
    Apenas engenheiro/administrador pode marcar como 'confirmado'."""
    p = obter(db, Projeto, pid, "Projeto")
    exigir_editavel(p)
    campos = {c[0]: c for c in sv.campos_modulo(p.modulo)}
    ent = dict(p.entradas or {})
    log = {}
    for k, v in d.items():
        if k not in campos:
            raise HTTPException(422, f"Campo desconhecido: {k}")
        st = v.get("status", "nao_confirmado")
        if st not in STATUS_ENTRADA:
            raise HTTPException(422, f"Status inválido: {st}")
        anterior = ent.get(k) or {}
        if st == "confirmado" and anterior.get("status") != "confirmado" and not tem(u, "projetos.aprovar"):
            # projetista pode registrar a medição, mas a confirmação é do responsável
            st = "nao_confirmado"
        val = v.get("valor")
        if anterior.get("valor") != val and anterior.get("status") == "confirmado" and not tem(u, "projetos.aprovar"):
            st = "nao_confirmado"
        ent[k] = {"valor": val, "unidade": campos[k][2], "rotulo": campos[k][1], "status": st,
                  "fonte": v.get("fonte"), "atualizado_por": u.nome}
        if anterior.get("valor") != val or anterior.get("status") != st:
            log[k] = {"de": anterior.get("valor"), "para": val, "status": st}
    p.entradas = ent
    registrar(db, u, "editar_entradas", "projeto", p.id, log)
    db.commit()
    return projeto_dict(db, p)


@router.delete("/{pid}")
def excluir(pid: int, u: Usuario = Depends(exige("usuarios.gerenciar")), db: Session = Depends(get_db)):
    p = obter(db, Projeto, pid, "Projeto")
    if p.status != "rascunho":
        raise HTTPException(409, "Somente projetos em rascunho podem ser excluídos")
    for m in (Calculo, Rede):
        for o in db.scalars(select(m).where(m.projeto_id == pid)).all():
            db.delete(o)
    registrar(db, u, "excluir", "projeto", p.id, {"codigo": p.codigo})
    db.delete(p)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ segurança
@router.get("/{pid}/seguranca")
def seguranca(pid: int, _: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    p = obter(db, Projeto, pid, "Projeto")
    return {"riscos": p.riscos or {}, "avaliacao": sv.avaliar_seguranca(p),
            "tipos": {k: v["titulo"] for k, v in seg.RISCOS.items()} | {"controle_fumaca_incendio": "Controle de fumaça de incêndio"}}


@router.put("/{pid}/seguranca")
def editar_seguranca(pid: int, d: dict, u: Usuario = Depends(exige("projetos.editar")), db: Session = Depends(get_db)):
    p = obter(db, Projeto, pid, "Projeto")
    exigir_editavel(p)
    if "riscos" in d:
        p.riscos = {k: bool(v) for k, v in d["riscos"].items()}
    if "checklist" in d:
        if not tem(u, "projetos.aprovar"):
            raise HTTPException(403, "Somente o engenheiro responsável confirma itens de segurança")
        ck = dict(p.checklist_seguranca or {})
        for k, v in d["checklist"].items():
            ck[k] = {"ok": bool(v), "por": u.nome, "em": datetime.now(timezone.utc).isoformat()} if v else {"ok": False}
        p.checklist_seguranca = ck
    registrar(db, u, "editar_seguranca", "projeto", p.id, d)
    db.commit()
    return seguranca(pid, u, db)


# ------------------------------------------------------------------ fluxo de aprovação
@router.get("/{pid}/pendencias")
def pendencias(pid: int, _: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    p = obter(db, Projeto, pid, "Projeto")
    calc = db.get(Calculo, p.calculo_aprovado_id) if p.calculo_aprovado_id else sv.ultimo_calculo(db, pid)
    return {"pendencias": sv.pendencias_aprovacao(db, p, calc), "calculo_id": calc.id if calc else None}


@router.post("/{pid}/status")
def mudar_status(pid: int, d: dict, u: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    p = obter(db, Projeto, pid, "Projeto")
    acao = d.get("acao")
    if acao == "enviar_revisao":
        if not tem(u, "projetos.editar") or p.status != "rascunho":
            raise HTTPException(409, "Ação não permitida")
        p.status = "em_revisao"
    elif acao == "voltar_rascunho":
        if not tem(u, "projetos.editar"):
            raise HTTPException(403, "Sem permissão")
        if p.status in ("aprovado", "liberado_fabricacao"):
            if not tem(u, "projetos.aprovar"):
                raise HTTPException(403, "Somente o engenheiro responsável reabre projeto aprovado")
            p.versao += 1
        p.status = "rascunho"
        p.aprovado_por = p.aprovado_em = p.calculo_aprovado_id = None
    elif acao == "aprovar":
        if not tem(u, "projetos.aprovar"):
            raise HTTPException(403, "Somente o engenheiro responsável aprova")
        if p.status != "em_revisao":
            raise HTTPException(409, "Envie o projeto para revisão antes de aprovar")
        calc_id = d.get("calculo_id")
        calc = db.get(Calculo, calc_id) if calc_id else sv.ultimo_calculo(db, pid)
        if not calc or calc.projeto_id != pid:
            raise HTTPException(422, "Cálculo inválido")
        pend = sv.pendencias_aprovacao(db, p, calc)
        if pend:
            raise HTTPException(409, {"mensagem": "Aprovação bloqueada", "pendencias": pend})
        p.status = "aprovado"
        p.aprovado_por = u.id
        p.aprovado_em = datetime.now(timezone.utc)
        p.calculo_aprovado_id = calc.id
    elif acao == "liberar_fabricacao":
        if not tem(u, "fabricacao.liberar"):
            raise HTTPException(403, "Sem permissão para liberar fabricação")
        if p.status != "aprovado":
            raise HTTPException(409, "Somente projetos aprovados podem ser liberados para fabricação")
        p.status = "liberado_fabricacao"
    else:
        raise HTTPException(422, "Ação desconhecida")
    registrar(db, u, f"status:{acao}", "projeto", p.id, {"status": p.status, "versao": p.versao})
    db.commit()
    return projeto_dict(db, p)


@router.get("/{pid}/historico")
def historico(pid: int, _: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    q = select(Auditoria).where(Auditoria.entidade == "projeto", Auditoria.entidade_id == str(pid)).order_by(Auditoria.id.desc()).limit(500)
    return [to_dict(a) for a in db.scalars(q).all()]


# ------------------------------------------------------------------ rede
def _rede(db, pid) -> Rede:
    r = db.scalars(select(Rede).where(Rede.projeto_id == pid).order_by(Rede.id)).first()
    if not r:
        r = Rede(projeto_id=pid, dados={"nodes": [], "segments": []})
        db.add(r)
        db.flush()
    return r


@router.get("/{pid}/rede")
def obter_rede(pid: int, _: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    obter(db, Projeto, pid, "Projeto")
    r = _rede(db, pid)
    db.commit()
    return to_dict(r)


def _validar_cota(v, rotulo: str):
    # Cota vazia é permitida (ainda não levantada); texto ou número absurdo não:
    # uma cota de 4000 por engano de unidade (mm em vez de m) viraria 4 km de duto.
    if v is None:
        return
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not -10 <= v <= 200:
        raise HTTPException(422, f"{rotulo}: informe em metros, entre -10 e 200")


def _cotas_preservadas(r: Rede, dados: dict) -> dict:
    # O editor de planta salva só nós e trechos; sem isto, cada "Salvar" na aba
    # Rede apagaria a cota da rede definida na aba 3D.
    if "cotas" in dados:
        return dados["cotas"] or {}
    return (r.dados or {}).get("cotas") or {}


def _validar_rede_basica(dados: dict):
    ids = set()
    for n in dados.get("nodes", []):
        if not n.get("id") or n["id"] in ids:
            raise HTTPException(422, "Nó sem id ou id repetido")
        ids.add(n["id"])
        for k in ("x", "y"):
            if not isinstance(n.get(k), (int, float)):
                raise HTTPException(422, f"Nó {n['id']} sem coordenada {k}")
        _validar_cota(n.get("z_m"), f"Cota do nó {n['id']}")
    for s in dados.get("segments", []):
        _validar_cota(s.get("cota_m"), f"Cota do trecho {s.get('id')}")
    if "cotas" in dados:
        if not isinstance(dados["cotas"], dict):
            raise HTTPException(422, "Cotas da rede inválidas")
        _validar_cota(dados["cotas"].get("rede_m"), "Cota da rede")
    for s in dados.get("segments", []):
        if s.get("from") not in ids or s.get("to") not in ids:
            raise HTTPException(422, f"Trecho {s.get('id')} referencia nó inexistente")


@router.put("/{pid}/rede")
def salvar_rede(pid: int, d: dict, u: Usuario = Depends(exige("projetos.editar")), db: Session = Depends(get_db)):
    p = obter(db, Projeto, pid, "Projeto")
    exigir_editavel(p)
    r = _rede(db, pid)
    dados = d.get("dados", d)
    _validar_rede_basica(dados)
    r.dados = {"nodes": dados.get("nodes", []), "segments": dados.get("segments", []), "cotas": _cotas_preservadas(r, dados)}
    r.versao += 1
    registrar(db, u, "salvar_rede", "projeto", pid, {"rede_versao": r.versao, "nos": len(r.dados["nodes"]), "trechos": len(r.dados["segments"])})
    db.commit()
    return to_dict(r)


@router.post("/{pid}/rede/rotear")
def rotear(pid: int, d: dict | None = None, u: Usuario = Depends(exige("projetos.editar")), db: Session = Depends(get_db)):
    """Roteia automaticamente os trechos de sucção (captores → filtro/exaustor).
    Trechos travados e o lado de descarga são preservados."""
    d = d or {}
    p = obter(db, Projeto, pid, "Projeto")
    exigir_editavel(p)
    r = _rede(db, pid)
    dados = r.dados or {}
    nos = {n["id"]: n for n in dados.get("nodes", [])}
    fans = [n for n in nos.values() if n["type"] == "exaustor"]
    if len(fans) != 1:
        raise HTTPException(422, "Posicione exatamente um exaustor antes de rotear")
    fan = fans[0]
    filtros = [n for n in nos.values() if n["type"] == "filtro"]
    alvo = filtros[0] if filtros else fan
    segs = dados.get("segments", [])
    travados = [s for s in segs if s.get("travado")]
    capt_travados = {s["from"] for s in travados}
    captores = [n for n in nos.values() if n["type"] == "captor" and n["id"] not in capt_travados]
    if not captores:
        raise HTTPException(422, "Nenhum captor para rotear")
    # preserva trechos a jusante do alvo (filtro→exaustor→descarga) e travados
    manter = [s for s in segs if s.get("travado")]
    jus = {alvo["id"]}
    mudou = True
    while mudou:
        mudou = False
        for s in segs:
            if s["from"] in jus and s not in manter:
                manter.append(s)
                jus.add(s["to"])
                mudou = True
    if filtros and not any(s["from"] == alvo["id"] for s in manter):
        manter.append({"id": "R_FLT", "from": alvo["id"], "to": fan["id"], "label": "R-FLT"})
    amb = p.ambiente or {}
    try:
        res = rotear_rede(
            captores, alvo, ambiente=amb.get("contorno"),
            obstaculos=[o["pontos"] for o in amb.get("pilares", []) + amb.get("obstaculos", [])],
            bloqueios=[b["pontos"] for b in amb.get("bloqueios", [])],
            folga=float(d.get("folga_m", 0.3)), passo=float(d.get("passo_m", 0.25)), penal_curva=float(d.get("penal_curva_m", 2.0)),
        )
    except RoteamentoFalhou as e:
        raise HTTPException(422, str(e))
    nos_mantidos = [n for n in nos.values() if n["type"] != "juncao" or any(n["id"] in (s["from"], s["to"]) for s in manter)]
    ids = {n["id"] for n in nos_mantidos}
    novos_nos = []
    for n in res["nodes"]:
        nid = n["id"]
        k = 1
        while nid in ids:
            nid = f"{n['id']}_{k}"
            k += 1
        ren = {n["id"]: nid}
        for s in res["segments"]:
            s["from"] = ren.get(s["from"], s["from"])
            s["to"] = ren.get(s["to"], s["to"])
        n["id"] = nid
        n["label"] = nid
        ids.add(nid)
        novos_nos.append(n)
    r.dados = {"nodes": nos_mantidos + novos_nos, "segments": manter + res["segments"], "cotas": _cotas_preservadas(r, {})}
    r.versao += 1
    registrar(db, u, "rotear_rede", "projeto", pid, {"comprimento_m": round(res["comprimento_total_m"], 2), "rede_versao": r.versao})
    db.commit()
    return {"rede": to_dict(r), "avisos": res["avisos"], "comprimento_total_m": res["comprimento_total_m"]}


# ------------------------------------------------------------------ cálculos
@router.post("/{pid}/calcular")
def calcular(pid: int, d: dict | None = None, u: Usuario = Depends(exige("calculos.executar")), db: Session = Depends(get_db)):
    d = d or {}
    p = obter(db, Projeto, pid, "Projeto")
    if p.modulo == "renovacao" and not (_rede(db, pid).dados or {}).get("segments"):
        res = sv.executar_renovacao(db, p)
        c = sv.salvar_calculo(db, p, None, "renovacao", res, u)
    else:
        r = _rede(db, pid)
        res = sv.executar_rede(db, p, r, d.get("estrategia", "menor_perda"), d.get("exaustor_id"))
        c = sv.salvar_calculo(db, p, r, "rede", res, u)
        sel = res["selecao_exaustor"]["selecionado"]
        if p.status == "rascunho":
            p.exaustor_id = sel["id"] if sel else None
        if d.get("aplicar_diametros"):
            for s in r.dados.get("segments", []):
                t = next((t for t in res["trechos"] if t["id"] == s["id"]), None)
                if t and t.get("diametro_mm") and not s.get("diametro_mm"):
                    s["diametro_mm"] = t["diametro_mm"]
            r.dados = dict(r.dados)
            r.versao += 1
            c.rede_versao = r.versao
    registrar(db, u, "calcular", "projeto", pid, {"calculo_id": c.id, "situacao": c.situacao, "hash": c.hash_entradas[:12]})
    db.commit()
    return to_dict(c)


@router.post("/{pid}/alternativas")
def gerar_alternativas(pid: int, u: Usuario = Depends(exige("calculos.executar")), db: Session = Depends(get_db)):
    p = obter(db, Projeto, pid, "Projeto")
    if p.modulo == "renovacao":
        raise HTTPException(422, "Alternativas de rede não se aplicam a renovação sem dutos")
    return {"alternativas": sv.alternativas(db, p, _rede(db, pid))}


@router.get("/{pid}/calculos")
def listar_calculos(pid: int, _: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    q = select(Calculo).where(Calculo.projeto_id == pid).order_by(Calculo.id.desc()).limit(50)
    out = []
    for c in db.scalars(q).all():
        r = c.resultados or {}
        out.append({"id": c.id, "tipo": c.tipo, "situacao": c.situacao, "criado_em": c.criado_em.isoformat(),
                    "versao_motor": c.versao_motor, "hash_entradas": c.hash_entradas, "rede_versao": c.rede_versao,
                    "vazao_total_m3h": r.get("vazao_total_m3h") or r.get("vazao_exaustao_m3h"),
                    "pressao_total_pa": r.get("pressao_total_ventilador_pa"),
                    "exaustor": ((r.get("selecao_exaustor") or {}).get("selecionado") or {}).get("nome"),
                    "bloqueios": len(r.get("bloqueios", []))})
    return out
