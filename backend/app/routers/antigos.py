from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import registrar
from ..db import get_db
from ..models import Arquivo, Calculo, Projeto, ProjetoAntigo, Usuario
from ..security import exige
from .. import services as sv
from ..util import aplicar, obter, to_dict

router = APIRouter(prefix="/api/antigos", tags=["biblioteca de projetos anteriores"])
CAMPOS = {"nome", "cliente", "ano", "modulo", "descricao", "dados", "desempenho_real", "confiabilidade"}
CONFIABILIDADE = {"nao_verificado": "Não verificado", "conferido": "Conferido por engenheiro", "medido_em_campo": "Desempenho medido em campo"}


def antigo_dict(db, a: ProjetoAntigo) -> dict:
    d = to_dict(a)
    d["arquivos"] = [to_dict(x, excluir=("chave",)) for x in db.scalars(select(Arquivo).where(Arquivo.projeto_antigo_id == a.id)).all()]
    d["confiabilidade_nome"] = CONFIABILIDADE.get(a.confiabilidade, a.confiabilidade)
    return d


@router.get("")
def listar(_: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    return [antigo_dict(db, a) for a in db.scalars(select(ProjetoAntigo).order_by(ProjetoAntigo.id.desc())).all()]


@router.post("")
def criar(d: dict, u: Usuario = Depends(exige("antigos.editar")), db: Session = Depends(get_db)):
    if not d.get("nome"):
        raise HTTPException(422, "Nome é obrigatório")
    if d.get("confiabilidade", "nao_verificado") not in CONFIABILIDADE:
        raise HTTPException(422, "Confiabilidade inválida")
    a = ProjetoAntigo(**{k: v for k, v in d.items() if k in CAMPOS}, criado_por=u.id)
    db.add(a)
    db.flush()
    registrar(db, u, "criar", "projeto_antigo", a.id, {"nome": a.nome})
    db.commit()
    return antigo_dict(db, a)


@router.get("/{aid}")
def obter_antigo(aid: int, _: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    return antigo_dict(db, obter(db, ProjetoAntigo, aid, "Projeto antigo"))


@router.put("/{aid}")
def editar(aid: int, d: dict, u: Usuario = Depends(exige("antigos.editar")), db: Session = Depends(get_db)):
    a = obter(db, ProjetoAntigo, aid, "Projeto antigo")
    if "confiabilidade" in d and d["confiabilidade"] not in CONFIABILIDADE:
        raise HTTPException(422, "Confiabilidade inválida")
    alt = aplicar(a, d, CAMPOS)
    registrar(db, u, "editar", "projeto_antigo", a.id, alt)
    db.commit()
    return antigo_dict(db, a)


def _div(ref, novo, tol_pct=10.0):
    if ref in (None, "") or novo in (None, ""):
        return {"referencia": ref, "gerado": novo, "diferenca_pct": None, "situacao": "sem_dado"}
    ref, novo = float(ref), float(novo)
    dif = (novo - ref) / ref * 100 if ref else None
    return {"referencia": ref, "gerado": novo, "diferenca_pct": dif,
            "situacao": "ok" if dif is not None and abs(dif) <= tol_pct else "divergente"}


@router.get("/{aid}/comparar/{pid}")
def comparar(aid: int, pid: int, calculo_id: int | None = None, tolerancia_pct: float = 10.0,
             _: Usuario = Depends(exige("ver")), db: Session = Depends(get_db)):
    """Compara o projeto antigo com o cálculo de um projeto gerado pelo software.
    Serve para validação: o projeto antigo NÃO é considerado automaticamente correto."""
    a = obter(db, ProjetoAntigo, aid, "Projeto antigo")
    p = obter(db, Projeto, pid, "Projeto")
    c = db.get(Calculo, calculo_id) if calculo_id else sv.ultimo_calculo(db, pid)
    if not c or c.projeto_id != pid:
        raise HTTPException(422, "Projeto sem cálculo para comparar")
    r = c.resultados
    ad = a.dados or {}
    sel = ((r.get("selecao_exaustor") or {}).get("selecionado") or {})
    diams_novo = sorted({t["diametro_mm"] for t in r.get("trechos", []) if t.get("diametro_mm")})
    diams_ref = sorted(float(x) for x in (ad.get("diametros_mm") or []))
    comp = {
        "vazao_total_m3h": _div(ad.get("vazao_total_m3h"), r.get("vazao_total_m3h") or r.get("vazao_exaustao_m3h"), tolerancia_pct),
        "pressao_total_pa": _div(ad.get("pressao_total_pa"), r.get("pressao_total_ventilador_pa"), tolerancia_pct),
        "pressao_estatica_pa": _div(ad.get("pressao_estatica_pa"), r.get("pressao_estatica_ventilador_pa"), tolerancia_pct),
        "potencia_kw": _div(ad.get("potencia_kw"), sel.get("potencia_absorvida_kw"), tolerancia_pct),
        "comprimento_dutos_m": _div(ad.get("comprimento_total_m"), sum(t["comprimento_m"] for t in r.get("trechos", [])) or None, tolerancia_pct),
        "numero_captores": _div(ad.get("numero_captores"), len(r.get("captores", [])) or None, 0.0),
    }
    eq = {"referencia": ad.get("exaustor"), "gerado": sel.get("nome"),
          "situacao": "sem_dado" if not ad.get("exaustor") else ("ok" if (sel.get("codigo") and sel["codigo"] in str(ad.get("exaustor"))) else "divergente")}
    diam = {"referencia": diams_ref, "gerado": diams_novo,
            "somente_referencia": [d for d in diams_ref if d not in diams_novo],
            "somente_gerado": [d for d in diams_novo if d not in diams_ref]}
    trajeto = {"observacao": "Comparação de trajetos é visual: abra as plantas do projeto antigo e o desenho gerado lado a lado. "
                             "A comparação geométrica automática ainda não está implementada."}
    observacoes = []
    if a.confiabilidade == "nao_verificado":
        observacoes.append("Projeto antigo não verificado: divergências não indicam necessariamente erro do cálculo novo.")
    if any(v["situacao"] == "divergente" for v in comp.values()):
        observacoes.append("Há divergências acima da tolerância. Investigue hipóteses, parâmetros e dados de entrada antes de concluir qualquer coisa. Fórmulas do motor não são alteradas com base nesta comparação.")
    return {"projeto_antigo": a.nome, "projeto": p.codigo, "calculo_id": c.id, "tolerancia_pct": tolerancia_pct,
            "grandezas": comp, "exaustor": eq, "diametros": diam, "trajetos": trajeto, "observacoes": observacoes}
