"""Orquestração entre banco de dados e motor de cálculo."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .docs.bom import gerar_lista
from .engine import ENGINE_VERSION
from .engine.fans import selecionar_exaustor
from .engine.network import RedeInvalida, analisar_rede
from .engine.params import ParameterSet
from .engine.renovacao import dimensionar_renovacao
from .engine import seguranca as seg
from .models import Calculo, ComponenteDuto, Exaustor, ParametroTecnico, Projeto, Rede, Usuario

MODULOS = {
    "poeira": "Exaustão de poeiras",
    "fumos": "Exaustão de fumaças, gases e vapores",
    "renovacao": "Renovação de ar",
}

# Campos de entrada por módulo: (chave, rótulo, unidade, obrigatório para cálculo)
CAMPOS_ENTRADA = {
    "comum": [
        ("temperatura_c", "Temperatura do ar transportado", "°C", True),
        ("altitude_m", "Altitude do local", "m", True),
        ("comprimento_m", "Comprimento do ambiente", "m", False),
        ("largura_m", "Largura do ambiente", "m", False),
        ("pe_direito_m", "Pé-direito", "m", False),
        ("horas_operacao_ano", "Horas de operação por ano", "h", False),
    ],
    "poeira": [
        ("contaminante", "Contaminante (poeira)", "", True),
        ("material_dutos", "Material dos dutos", "", True),
    ],
    "fumos": [
        ("contaminante", "Contaminante (fumos/gases)", "", True),
        ("material_dutos", "Material dos dutos", "", True),
    ],
    "renovacao": [
        ("uso", "Uso do ambiente", "", True),
        ("ocupantes", "Número de ocupantes", "pessoas", False),
        ("modo_pressao", "Pressurização desejada (negativa/positiva/neutra)", "", True),
        ("vazao_termica_m3h", "Vazão para carga térmica (cálculo externo)", "m³/h", False),
    ],
}

def campos_modulo(modulo: str):
    base = list(CAMPOS_ENTRADA["comum"])
    if modulo == "renovacao":
        base = [c if c[0] not in ("comprimento_m", "largura_m", "pe_direito_m") else (c[0], c[1], c[2], True) for c in base]
        base = [c for c in base if c[0] != "temperatura_c"] + [("temperatura_c", "Temperatura interna", "°C", False)]
    return base + CAMPOS_ENTRADA.get(modulo, [])


def valor(projeto: Projeto, chave: str, padrao=None):
    d = (projeto.entradas or {}).get(chave)
    if isinstance(d, dict):
        v = d.get("valor")
        return padrao if v in (None, "") else v
    return padrao


def parametros(db: Session) -> ParameterSet:
    rows = db.scalars(select(ParametroTecnico)).all()
    return ParameterSet.from_list([
        {"chave": r.chave, "valor": r.valor, "unidade": r.unidade or "", "status": r.status,
         "referencia": r.referencia or "", "demonstrativo": r.demonstrativo}
        for r in rows
    ])


def exaustor_dict(e: Exaustor) -> dict:
    return {
        "id": e.id, "codigo": e.codigo, "modelo": e.modelo, "tipo": e.tipo, "curva": e.curva,
        "tipo_pressao_curva": e.tipo_pressao_curva, "densidade_referencia": e.densidade_referencia,
        "temperatura_max_c": e.temperatura_max_c, "potencia_motor_kw": e.potencia_motor_kw,
        "rendimento": e.rendimento, "preco": e.preco, "status": e.status, "demonstrativo": e.demonstrativo,
    }


def componentes_dict(db: Session) -> list[dict]:
    out = []
    for c in db.scalars(select(ComponenteDuto)).all():
        out.append({k: getattr(c, k) for k in ("id", "codigo", "categoria", "descricao", "forma", "diametro_mm", "diametro2_mm",
                                               "largura_mm", "altura_mm", "espessura_mm", "material", "comprimento_m",
                                               "angulo_graus", "custo_unitario", "ativo", "massa_kg")})
    return out


def diametros_disponiveis(db: Session, material: str | None) -> list[float]:
    q = select(ComponenteDuto).where(ComponenteDuto.categoria == "duto_circular", ComponenteDuto.ativo.is_(True))
    rows = db.scalars(q).all()
    ds = {r.diametro_mm for r in rows if r.diametro_mm and (not material or r.material in (None, material))}
    if not ds:
        ds = {r.diametro_mm for r in rows if r.diametro_mm}
    return sorted(ds)


def entradas_usadas(projeto: Projeto, chaves: list[str]) -> list[dict]:
    out = []
    for k in chaves:
        d = (projeto.entradas or {}).get(k)
        if isinstance(d, dict) and d.get("valor") not in (None, ""):
            out.append({"chave": k, "rotulo": d.get("rotulo", k), "valor": d.get("valor"), "status": d.get("status", "nao_confirmado")})
        else:
            out.append({"chave": k, "rotulo": k, "valor": None, "status": "ausente"})
    return out


def config_rede(db: Session, projeto: Projeto, estrategia: str) -> dict:
    material = valor(projeto, "material_dutos", "galvanizado")
    return {
        "modulo": projeto.modulo,
        "contaminante": valor(projeto, "contaminante"),
        "temperatura_c": float(valor(projeto, "temperatura_c", 20)),
        "altitude_m": float(valor(projeto, "altitude_m", 0)),
        "material_padrao": material,
        "diametros_disponiveis_mm": diametros_disponiveis(db, material),
        "estrategia": estrategia,
    }


def executar_rede(db: Session, projeto: Projeto, rede: Rede, estrategia: str = "menor_perda", exaustor_id: int | None = None) -> dict:
    ps = parametros(db)
    cfg = config_rede(db, projeto, estrategia)
    for k in ("temperatura_c", "altitude_m"):
        if valor(projeto, k) is None:
            raise HTTPException(422, f"Informe '{k}' nos dados de entrada do projeto antes de calcular.")
    try:
        res = analisar_rede(rede.dados or {}, cfg, ps)
    except RedeInvalida as e:
        raise HTTPException(422, f"Rede inválida: {e}")
    exaustores = [exaustor_dict(e) for e in db.scalars(select(Exaustor).where(Exaustor.ativo.is_(True))).all()]
    tol = float(ps.get("tolerancia_vazao_selecao")) if ps.tem("tolerancia_vazao_selecao") else 0.2
    requisitos = {}
    if ps.tem(f"tipos_exaustor_permitidos.{projeto.modulo}"):
        requisitos["tipos_permitidos"] = ps.get(f"tipos_exaustor_permitidos.{projeto.modulo}")
    sel = selecionar_exaustor(exaustores, res["vazao_total_m3s"], res["k_sistema_total"], res["k_sistema_estatica"],
                              res["ar"]["densidade"], res["ar"]["temperatura_c"], tol, requisitos)
    if exaustor_id:
        escolhido = next((c for c in sel["compativeis"] if c["id"] == exaustor_id), None)
        if not escolhido:
            raise HTTPException(422, "O exaustor escolhido não é compatível com o ponto de projeto (ver rejeitados).")
        sel["selecionado"] = escolhido
        sel["escolha_manual"] = True
    res["selecao_exaustor"] = sel
    res["parametros_usados"] = ps.relatorio_usados()
    res["parametros_nao_aprovados"] = ps.nao_aprovados()
    chaves = [c[0] for c in campos_modulo(projeto.modulo) if c[3]]
    res["entradas_usadas"] = entradas_usadas(projeto, chaves)
    res["configuracao"] = cfg
    return res


def custo_energia(potencia_kw: float | None, horas: float | None) -> float | None:
    if potencia_kw is None or not horas:
        return None
    return potencia_kw * float(horas)


def alternativas(db: Session, projeto: Projeto, rede: Rede) -> list[dict]:
    comps = componentes_dict(db)
    ps = parametros(db)
    esp = float(ps.get("espacamento_suportes_m")) if ps.tem("espacamento_suportes_m") else None
    horas = valor(projeto, "horas_operacao_ano")
    out = []
    for est, nome in (("menor_perda", "Menor perda de carga"), ("intermediaria", "Intermediária"), ("economica", "Menor diâmetro (menos material)")):
        try:
            r = executar_rede(db, projeto, rede, est)
        except HTTPException as e:
            out.append({"estrategia": est, "nome": nome, "erro": e.detail})
            continue
        sel = r["selecao_exaustor"]["selecionado"]
        ex = None
        if sel:
            e = db.get(Exaustor, sel["id"])
            ex = exaustor_dict(e) if e else None
        lista = gerar_lista({}, rede.dados, r, comps, ex, esp, False)
        massa = 0.0
        for t in r["trechos"]:
            c = next((c for c in comps if c["categoria"] == "duto_circular" and c["diametro_mm"] == t.get("diametro_mm") and c.get("massa_kg") and c.get("comprimento_m")), None)
            if c:
                massa += c["massa_kg"] / c["comprimento_m"] * t["comprimento_m"]
        pot = sel["potencia_absorvida_kw"] if sel else None
        out.append({
            "estrategia": est, "nome": nome,
            "vazao_m3h": r["vazao_total_m3h"],
            "pressao_total_pa": r["pressao_total_ventilador_pa"],
            "exaustor": sel["nome"] if sel else None,
            "potencia_kw": pot,
            "energia_kwh_ano": custo_energia(pot, horas),
            "custo_materiais": lista["total_custo"],
            "itens_sem_custo": lista["itens_sem_custo"],
            "massa_dutos_kg": massa or None,
            "comprimento_dutos_m": sum(t["comprimento_m"] for t in r["trechos"]),
            "diametros": sorted({t["diametro_mm"] for t in r["trechos"] if t.get("diametro_mm")}),
            "bloqueios": r["bloqueios"],
            "avisos": len(r["avisos"]),
        })
    return out


def executar_renovacao(db: Session, projeto: Projeto) -> dict:
    ps = parametros(db)
    amb = {k: valor(projeto, k) for k in ("comprimento_m", "largura_m", "pe_direito_m", "uso", "ocupantes", "modo_pressao", "temperatura_c", "altitude_m", "vazao_termica_m3h")}
    exaustores = [exaustor_dict(e) for e in db.scalars(select(Exaustor).where(Exaustor.ativo.is_(True))).all()]
    res = dimensionar_renovacao(amb, ps, exaustores)
    chaves = [c[0] for c in campos_modulo("renovacao") if c[3]]
    res["entradas_usadas"] = entradas_usadas(projeto, chaves)
    return res


def salvar_calculo(db: Session, projeto: Projeto, rede: Rede | None, tipo: str, res: dict, usuario: Usuario, entradas_extra: dict | None = None) -> Calculo:
    c = Calculo(
        projeto_id=projeto.id, rede_id=rede.id if rede else None, rede_versao=rede.versao if rede else None,
        tipo=tipo, versao_motor=ENGINE_VERSION, versao_app=get_settings().app_version,
        hash_entradas=res.get("hash_entradas", ""),
        entradas={"rede": rede.dados if rede else None, "configuracao": res.get("configuracao"),
                  "entradas_projeto": projeto.entradas, **(entradas_extra or {})},
        resultados=res, situacao="com_bloqueios" if res.get("bloqueios") else "ok", criado_por=usuario.id,
    )
    db.add(c)
    db.flush()
    return c


def avaliar_seguranca(projeto: Projeto) -> dict:
    return seg.avaliar(projeto.riscos or {}, projeto.checklist_seguranca or {})


def pendencias_aprovacao(db: Session, projeto: Projeto, calc: Calculo | None) -> list[str]:
    p = []
    if projeto.demonstrativo:
        p.append("Projeto demonstrativo (dados fictícios) não pode ser aprovado.")
    if calc is None:
        p.append("Nenhum cálculo executado.")
        return p
    r = calc.resultados
    for b in r.get("bloqueios", []):
        p.append(f"Bloqueio do cálculo: {b}")
    for k in r.get("parametros_nao_aprovados", []):
        p.append(f"Parâmetro técnico sem aprovação: {k}")
    for e in r.get("entradas_usadas", []):
        if e["status"] != "confirmado":
            p.append(f"Dado de entrada não confirmado: {e['rotulo']} ({e['status']})")
    if calc.tipo == "rede":
        sel = (r.get("selecao_exaustor") or {}).get("selecionado")
        if not sel:
            p.append("Nenhum exaustor compatível selecionado.")
        else:
            ex = db.get(Exaustor, sel["id"])
            if ex is None:
                p.append("Exaustor selecionado não existe mais no catálogo.")
            elif ex.demonstrativo:
                p.append("Exaustor selecionado é demonstrativo (fictício).")
            elif ex.status != "aprovado":
                p.append(f"Dados do exaustor {ex.codigo} ainda não aprovados no catálogo.")
        rede = db.get(Rede, calc.rede_id) if calc.rede_id else None
        if rede and rede.versao != calc.rede_versao:
            p.append("A rede foi alterada após este cálculo — recalcule.")
    elif calc.tipo == "renovacao":
        if not r.get("opcoes_equipamento"):
            p.append("Nenhum equipamento de renovação compatível.")
    s = avaliar_seguranca(projeto)
    p += [f"Segurança: {x}" for x in s["pendencias"]]
    p += [f"Segurança: {x}" for x in s["bloqueios"]]
    return p


def ultimo_calculo(db: Session, projeto_id: int) -> Calculo | None:
    return db.scalars(select(Calculo).where(Calculo.projeto_id == projeto_id).order_by(Calculo.id.desc()).limit(1)).first()


def faltantes_visita(dados: dict[str, Any]) -> list[str]:
    """Organiza a visita: indica dados técnicos ainda não levantados (regras explícitas)."""
    falta = []
    req = [
        ("tipo_sistema", "Tipo de sistema necessário"),
        ("descricao_problema", "Descrição do problema"),
        ("atividade", "Tipo de atividade industrial"),
        ("comprimento_m", "Comprimento do ambiente"),
        ("largura_m", "Largura do ambiente"),
        ("pe_direito_m", "Pé-direito"),
        ("temperatura_c", "Temperatura de operação"),
        ("contaminantes", "Materiais/contaminantes envolvidos"),
    ]
    for k, rot in req:
        if dados.get(k) in (None, "", []):
            falta.append(rot)
    ts = dados.get("tipo_sistema")
    if ts in ("poeira", "fumos"):
        if not dados.get("pontos_emissao"):
            falta.append("Pontos de emissão (posição, tipo de captor, dimensões da abertura e distância à fonte)")
        else:
            for i, pe in enumerate(dados["pontos_emissao"], 1):
                for k, rot in (("processo", "nível de dispersão/processo"), ("x", "posição X"), ("y", "posição Y")):
                    if pe.get(k) in (None, ""):
                        falta.append(f"Ponto de emissão {i}: {rot}")
        if not dados.get("maquinas"):
            falta.append("Máquinas instaladas (posição e dimensões)")
    if ts == "renovacao" and dados.get("ocupantes") in (None, ""):
        falta.append("Número de ocupantes")
    if dados.get("altitude_m") in (None, ""):
        falta.append("Altitude do local (pode ser obtida pelo endereço)")
    if not dados.get("pilares_obstaculos"):
        falta.append("Pilares e obstáculos (ou planta com esses elementos)")
    riscos = dados.get("riscos") or {}
    if not riscos:
        falta.append("Avaliação de riscos (poeira combustível, atmosfera explosiva, contaminante perigoso)")
    return falta
