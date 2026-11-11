"""Assistente técnico.

Princípios:
* a IA só consulta dados autorizados do projeto, resultados do motor de cálculo e o catálogo
  por meio de ferramentas SOMENTE LEITURA;
* a IA não calcula valores de engenharia por conta própria, não inventa parâmetros e não
  aprova nem libera projetos (não há ferramenta para isso);
* sem credencial da API, funciona em modo de regras (sem IA), com respostas determinísticas.
"""

from __future__ import annotations

import json
import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..engine.fans import Curva, CurvaInvalida, ponto_operacao
from ..engine.trace import fmt
from ..models import Calculo, Exaustor, Projeto, Rede, Usuario
from .. import services as sv

SISTEMA = """Você é o assistente técnico de um software de engenharia de exaustão e ventilação industrial de uma \
fabricante brasileira de exaustores e dutos. Responda sempre em português do Brasil, de forma objetiva.

Regras obrigatórias:
1. Nunca invente parâmetros, coeficientes, curvas, medidas, vazões, pressões ou resultados. Use apenas o que as \
ferramentas retornarem. Se faltar um dado, diga exatamente qual é e como obtê-lo.
2. Todos os números de engenharia vêm do motor de cálculo determinístico (ferramentas). Você pode explicá-los, \
compará-los e sugerir caminhos, mas não pode produzir novos valores de cálculo por estimativa própria.
3. Você não aprova projetos, não libera fabricação e não ignora verificações técnicas ou de segurança. A aprovação é \
sempre de um engenheiro responsável legalmente habilitado.
4. Para poeiras combustíveis, atmosferas explosivas, contaminantes perigosos ou controle de fumaça de incêndio, \
lembre das análises de segurança obrigatórias.
5. Deixe claro quando um dado ou parâmetro está "não confirmado", "estimado", "proposto" ou é demonstrativo (fictício).
6. Quando sugerir alterações (ex.: reduzir comprimento, outra alternativa), explique o que o usuário deve fazer na \
interface e recomende recalcular."""

FERRAMENTAS = [
    {"name": "obter_projeto", "description": "Dados do projeto atual: módulo, status, entradas (com status de confirmação), riscos, resumo do ambiente e da rede.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "pendencias", "description": "Lista o que impede a aprovação técnica do projeto e os dados de entrada ausentes ou não confirmados.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "ultimo_calculo", "description": "Resumo do último cálculo do motor: vazões, pressões, trechos, equilíbrio, seleção de exaustor (selecionado, compatíveis e rejeitados com motivos), avisos e bloqueios.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "listar_exaustores", "description": "Catálogo de exaustores da empresa (código, modelo, tipo, faixa da curva, limites, status).",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "comparar_exaustores", "description": "Calcula, com o motor, o ponto de operação de exaustores do catálogo contra a curva do sistema do último cálculo.",
     "input_schema": {"type": "object", "properties": {"codigos": {"type": "array", "items": {"type": "string"}, "description": "Códigos dos exaustores"}},
                      "required": ["codigos"], "additionalProperties": False}},
    {"name": "simular_alternativas", "description": "Executa o motor com três critérios de dimensionamento (menor perda, intermediário, menor diâmetro) e compara pressão, potência, energia, material e custo. Não salva nada.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
]


class Contexto:
    def __init__(self, db: Session, projeto: Projeto, usuario: Usuario):
        self.db, self.p, self.u = db, projeto, usuario

    def calc(self) -> Calculo | None:
        return sv.ultimo_calculo(self.db, self.p.id)

    def executar(self, nome: str, args: dict) -> Any:
        f = getattr(self, f"t_{nome}", None)
        if not f:
            return {"erro": f"ferramenta desconhecida: {nome}"}
        return f(**args)

    def t_obter_projeto(self):
        p = self.p
        rede = self.db.scalars(select(Rede).where(Rede.projeto_id == p.id)).first()
        dados = (rede.dados if rede else {}) or {}
        amb = p.ambiente or {}
        return {
            "codigo": p.codigo, "nome": p.nome, "modulo": sv.MODULOS.get(p.modulo), "status": p.status,
            "demonstrativo": p.demonstrativo, "cliente": p.cliente.nome if p.cliente else None,
            "entradas": p.entradas, "riscos": p.riscos,
            "ambiente": {"tem_contorno": bool(amb.get("contorno")), "pilares": len(amb.get("pilares", [])), "obstaculos": len(amb.get("obstaculos", []))},
            "rede": {"nos": [{k: n.get(k) for k in ("id", "type", "label", "x", "y", "captor")} for n in dados.get("nodes", [])][:60],
                     "trechos": [{k: s.get(k) for k in ("id", "from", "to", "diametro_mm", "travado")} for s in dados.get("segments", [])][:80]},
        }

    def t_pendencias(self):
        faltando = []
        for c in sv.campos_modulo(self.p.modulo):
            v = (self.p.entradas or {}).get(c[0])
            if not v or v.get("valor") in (None, ""):
                faltando.append({"campo": c[1], "obrigatorio_para_calculo": c[3]})
        return {"pendencias_aprovacao": sv.pendencias_aprovacao(self.db, self.p, self.calc()), "entradas_ausentes": faltando}

    def t_ultimo_calculo(self):
        c = self.calc()
        if not c:
            return {"mensagem": "Nenhum cálculo executado ainda."}
        r = c.resultados
        sel = r.get("selecao_exaustor") or {}
        out = {
            "calculo_id": c.id, "tipo": c.tipo, "versao_motor": c.versao_motor, "situacao": c.situacao,
            "bloqueios": r.get("bloqueios"), "avisos": r.get("avisos"), "hipoteses": r.get("hipoteses"),
            "parametros_nao_aprovados": r.get("parametros_nao_aprovados"),
        }
        if c.tipo == "rede":
            out.update({
                "vazao_total_m3h": r["vazao_total_m3h"], "pressao_total_pa": r["pressao_total_ventilador_pa"],
                "pressao_estatica_pa": r["pressao_estatica_ventilador_pa"], "densidade_ar": r["ar"]["densidade"],
                "captores": [{k: x[k] for k in ("label", "vazao_m3h", "perda_ate_exaustor_pa", "governante")} for x in r["captores"]],
                "trechos": [{"id": t["id"], "lado": t["lado"], "diametro_mm": t["diametro_mm"], "vazao_m3h": round(t["vazao_m3h"], 1),
                             "velocidade_ms": round(t["velocidade_ms"], 2), "comprimento_m": round(t["comprimento_m"], 2),
                             "perda_pa": round(t["perda_total_pa"], 1), "curvas": t["curvas"]} for t in r["trechos"]],
                "equilibrio": r.get("equilibrio"),
                "exaustor_selecionado": sel.get("selecionado") and {k: sel["selecionado"][k] for k in ("nome", "ponto_operacao", "potencia_absorvida_kw", "folga_vazao_pct", "tipo_pressao_curva")},
                "criterio_selecao": "Entre os compatíveis (ponto de operação com vazão ≥ projeto e dentro da tolerância de superdimensionamento, limites de temperatura e potência do motor), escolhe-se o de menor potência absorvida; empate pelo custo.",
                "compativeis": [{"nome": x["nome"], "vazao_op_m3h": round(x["ponto_operacao"]["vazao_m3h"]), "potencia_kw": x["potencia_absorvida_kw"]} for x in sel.get("compativeis", [])],
                "rejeitados": sel.get("rejeitados"), "mensagem_selecao": sel.get("mensagem"),
            })
        else:
            out.update({k: r.get(k) for k in ("volume_m3", "criterios_m3h", "vazao_exaustao_m3h", "vazao_insuflamento_m3h", "opcoes_equipamento", "sugestao_posicionamento")})
        return out

    def t_listar_exaustores(self):
        out = []
        for e in self.db.scalars(select(Exaustor).where(Exaustor.ativo.is_(True))).all():
            qs = [pt["vazao_m3h"] for pt in e.curva or []]
            out.append({"codigo": e.codigo, "modelo": e.modelo, "tipo": e.tipo, "rotacao_rpm": e.rotacao_rpm,
                        "potencia_motor_kw": e.potencia_motor_kw, "temperatura_max_c": e.temperatura_max_c,
                        "faixa_vazao_m3h": [min(qs), max(qs)] if qs else None, "tipo_pressao_curva": e.tipo_pressao_curva,
                        "status": e.status, "demonstrativo": e.demonstrativo})
        return out

    def t_comparar_exaustores(self, codigos: list[str]):
        c = self.calc()
        if not c or c.tipo != "rede":
            return {"erro": "É necessário um cálculo de rede para obter a curva do sistema."}
        r = c.resultados
        out = []
        for cod in codigos[:6]:
            e = self.db.scalars(select(Exaustor).where(Exaustor.codigo == cod)).first()
            if not e:
                out.append({"codigo": cod, "erro": "não encontrado no catálogo"})
                continue
            try:
                curva = Curva.from_pontos(e.curva, e.tipo_pressao_curva)
            except CurvaInvalida as ex:
                out.append({"codigo": cod, "erro": f"curva inválida: {ex}"})
                continue
            k = r["k_sistema_estatica"] if e.tipo_pressao_curva == "estatica" else r["k_sistema_total"]
            fr = r["ar"]["densidade"] / (e.densidade_referencia or 1.2)
            op = ponto_operacao(curva, k, fr)
            out.append({"codigo": cod, "modelo": e.modelo, "ponto_operacao": op,
                        "atende_vazao_projeto": bool(op and op["vazao_m3h"] >= r["vazao_total_m3h"] - 1e-6),
                        "vazao_projeto_m3h": r["vazao_total_m3h"],
                        "observacao": None if op else "sem interseção dentro da curva cadastrada (não extrapolado)"})
        return out

    def t_simular_alternativas(self):
        if self.p.modulo == "renovacao":
            return {"erro": "Não se aplica a renovação de ar sem rede de dutos."}
        rede = self.db.scalars(select(Rede).where(Rede.projeto_id == self.p.id)).first()
        try:
            return sv.alternativas(self.db, self.p, rede)
        except Exception as e:  # erros de validação viram mensagem para o modelo
            return {"erro": str(getattr(e, "detail", e))}


def credencial_disponivel() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def status() -> dict:
    s = get_settings()
    ativo = s.assistente_habilitado and credencial_disponivel()
    return {"modo": "ia" if ativo else "regras", "modelo": s.anthropic_model if ativo else None,
            "mensagem": None if ativo else "Assistente em modo de regras (sem IA): configure ANTHROPIC_API_KEY no servidor para habilitar a IA."}


def responder(db: Session, projeto: Projeto, usuario: Usuario, historico: list[dict]) -> dict:
    ctx = Contexto(db, projeto, usuario)
    if not status()["modo"] == "ia":
        return responder_regras(ctx, historico[-1]["content"] if historico else "")
    return responder_ia(ctx, historico)


def responder_ia(ctx: Contexto, historico: list[dict]) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    msgs: list[dict] = [{"role": m["role"], "content": str(m["content"])} for m in historico if m.get("role") in ("user", "assistant") and m.get("content")]
    if not msgs or msgs[-1]["role"] != "user":
        return {"resposta": "Envie uma pergunta.", "ferramentas": [], "modo": "ia"}
    usadas = []
    sistema = SISTEMA + f"\n\nProjeto em contexto: {ctx.p.codigo} — {ctx.p.nome}. Usuário: {ctx.u.nome} (perfil {ctx.u.perfil})."
    try:
        for _ in range(8):
            resp = client.beta.messages.create(
                model=get_settings().anthropic_model,
                max_tokens=16000,
                system=sistema,
                tools=FERRAMENTAS,
                messages=msgs,
                output_config={"effort": "medium"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            if resp.stop_reason == "refusal":
                return {"resposta": "O modelo recusou esta solicitação. Reformule a pergunta.", "ferramentas": usadas, "modo": "ia"}
            if resp.stop_reason == "pause_turn":
                msgs.append({"role": "assistant", "content": resp.content})
                continue
            if resp.stop_reason != "tool_use":
                texto = "\n".join(b.text for b in resp.content if b.type == "text")
                return {"resposta": texto or "(sem resposta)", "ferramentas": usadas, "modo": "ia"}
            msgs.append({"role": "assistant", "content": resp.content})
            resultados = []
            for b in resp.content:
                if b.type != "tool_use":
                    continue
                usadas.append(b.name)
                try:
                    saida = ctx.executar(b.name, dict(b.input or {}))
                    resultados.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(saida, ensure_ascii=False, default=str)[:60000]})
                except Exception as e:
                    resultados.append({"type": "tool_result", "tool_use_id": b.id, "content": f"Erro: {e}", "is_error": True})
            msgs.append({"role": "user", "content": resultados})
        return {"resposta": "Limite de etapas atingido. Refine a pergunta.", "ferramentas": usadas, "modo": "ia"}
    except anthropic.AuthenticationError:
        r = responder_regras(ctx, msgs[-1]["content"] if isinstance(msgs[-1]["content"], str) else "")
        r["resposta"] = "(Credencial da IA inválida — respondendo em modo de regras.)\n\n" + r["resposta"]
        return r
    except anthropic.RateLimitError:
        return {"resposta": "Limite de uso da IA atingido no momento. Tente novamente em instantes.", "ferramentas": usadas, "modo": "ia"}
    except anthropic.APIConnectionError:
        r = responder_regras(ctx, historico[-1]["content"])
        r["resposta"] = "(Sem conexão com o serviço de IA — respondendo em modo de regras.)\n\n" + r["resposta"]
        return r
    except anthropic.APIStatusError as e:
        return {"resposta": f"Erro do serviço de IA ({e.status_code}). Tente novamente.", "ferramentas": usadas, "modo": "ia"}


def responder_regras(ctx: Contexto, pergunta: str) -> dict:
    q = (pergunta or "").lower()
    linhas: list[str] = []
    usadas: list[str] = []
    if any(k in q for k in ("falt", "pend", "aprova", "bloque")):
        usadas.append("pendencias")
        pend = ctx.t_pendencias()
        if pend["entradas_ausentes"]:
            linhas.append("Dados de entrada ausentes:")
            linhas += [f"• {x['campo']}{' (obrigatório para o cálculo)' if x['obrigatorio_para_calculo'] else ''}" for x in pend["entradas_ausentes"]]
        if pend["pendencias_aprovacao"]:
            linhas.append("Pendências para a aprovação técnica:")
            linhas += [f"• {x}" for x in pend["pendencias_aprovacao"]]
        if len(linhas) == 0:
            linhas.append("Não há pendências registradas.")
    elif any(k in q for k in ("por que", "porque", "explique", "selecion")):
        usadas.append("ultimo_calculo")
        r = ctx.t_ultimo_calculo()
        if r.get("mensagem"):
            linhas.append(r["mensagem"])
        elif r.get("exaustor_selecionado"):
            s = r["exaustor_selecionado"]
            op = s["ponto_operacao"]
            linhas.append(f"Exaustor selecionado: {s['nome']}.")
            linhas.append(f"Ponto de operação calculado pelo motor: {fmt(op['vazao_m3h'],0)} m³/h a {fmt(op['pressao_pa'],0)} Pa "
                          f"(vazão de projeto {fmt(r['vazao_total_m3h'],0)} m³/h; folga {fmt(s['folga_vazao_pct'] or 0,1)}%).")
            linhas.append("Critério: " + r["criterio_selecao"])
            if r.get("rejeitados"):
                linhas.append("Rejeitados:")
                linhas += [f"• {x['nome']}: {x['motivo']}" for x in r["rejeitados"]]
        else:
            linhas.append(r.get("mensagem_selecao") or "Nenhum exaustor selecionado no último cálculo.")
    elif any(k in q for k in ("alternativ", "custo", "barat", "econom", "reduz")):
        usadas.append("simular_alternativas")
        alts = ctx.t_simular_alternativas()
        if isinstance(alts, dict) and alts.get("erro"):
            linhas.append(alts["erro"])
        else:
            linhas.append("Alternativas calculadas pelo motor (nada foi salvo):")
            for a in alts:
                if a.get("erro"):
                    linhas.append(f"• {a['nome']}: {a['erro']}")
                    continue
                linhas.append(f"• {a['nome']}: pressão total {fmt(a['pressao_total_pa'],0)} Pa; exaustor {a['exaustor'] or 'nenhum compatível'}; "
                              f"potência {fmt(a['potencia_kw'],2) + ' kW' if a['potencia_kw'] is not None else 'n/d'}; "
                              f"custo de materiais cadastrado R$ {fmt(a['custo_materiais'],2)} ({a['itens_sem_custo']} itens sem custo).")
            linhas.append("Para reduzir comprimento de tubulação, aproxime o exaustor/filtro do centro de massa dos captores e use o roteamento automático; depois recalcule.")
    elif any(k in q for k in ("compar", "exaustor")):
        usadas.append("listar_exaustores")
        lst = ctx.t_listar_exaustores()
        linhas.append("Exaustores do catálogo:")
        linhas += [f"• {e['codigo']} — {e['modelo']} ({e['tipo']}), faixa {fmt(e['faixa_vazao_m3h'][0],0)}–{fmt(e['faixa_vazao_m3h'][1],0)} m³/h"
                   f"{' — DEMONSTRATIVO' if e['demonstrativo'] else ''}" for e in lst if e["faixa_vazao_m3h"]]
        linhas.append("Para comparar no ponto de operação, execute o cálculo e veja a tabela de compatíveis/rejeitados.")
    else:
        linhas.append("Modo de regras (sem IA). Posso: listar pendências e dados faltantes ('o que falta?'), explicar a seleção do exaustor "
                      "('por que este exaustor?'), simular alternativas ('gere alternativa mais barata') e listar exaustores ('compare exaustores').")
    return {"resposta": "\n".join(linhas), "ferramentas": usadas, "modo": "regras"}
