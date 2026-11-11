"""Módulo C — Renovação de ar (ventilação geral diluidora)."""

from __future__ import annotations

import math

from . import ENGINE_VERSION
from .air import densidade
from .fans import Curva, CurvaInvalida
from .params import ParameterSet, ParametroAusente
from .trace import Trace, fmt, hash_entradas


def _vazao_na_pressao(curva: Curva, p_req: float, fr: float) -> float | None:
    """Vazão em que a curva (corrigida) fornece p_req — sem extrapolação."""
    for i in range(1, len(curva.q)):
        p0, p1 = curva.p[i - 1] * fr, curva.p[i] * fr
        if (p0 - p_req) * (p1 - p_req) <= 0 and p0 != p1:
            t = (p_req - p0) / (p1 - p0)
            return curva.q[i - 1] + t * (curva.q[i] - curva.q[i - 1])
    return None


def dimensionar_renovacao(amb: dict, params: ParameterSet, exaustores: list[dict]) -> dict:
    trace = Trace()
    entradas = {"ambiente": amb, "parametros": {k: (p.valor, p.status) for k, p in params.itens.items()}}
    L, W, H = (float(amb.get(k) or 0) for k in ("comprimento_m", "largura_m", "pe_direito_m"))
    if min(L, W, H) <= 0:
        trace.bloqueio("Dimensões do ambiente (comprimento, largura e pé-direito) são obrigatórias")
        return {"versao_motor": ENGINE_VERSION, **trace.as_dict()}
    vol = L * W * H
    trace.add("Volume do ambiente", "V = C·L·H", f"{fmt(L,2)}·{fmt(W,2)}·{fmt(H,2)}", round(vol, 2), "m³")
    uso = amb.get("uso") or "industrial_geral"
    q_cands = {}
    try:
        n = float(params.get(f"renov_trocas_h.{uso}"))
        q_cands["trocas_hora"] = n * vol
        trace.add("Vazão por taxa de renovação", "Q = n·V", f"n = {fmt(n,1)} trocas/h", round(n * vol, 1), "m³/h")
    except ParametroAusente:
        trace.bloqueio(f"Parâmetro renov_trocas_h.{uso} não cadastrado")
    ocup = int(amb.get("ocupantes") or 0)
    if ocup > 0:
        try:
            qp = float(params.get(f"vazao_pessoa.{uso}"))
            q_cands["ocupacao"] = ocup * qp
            trace.add("Vazão por ocupação", "Q = N·q_p", f"{ocup}·{fmt(qp,1)} m³/h", round(ocup * qp, 1), "m³/h")
        except ParametroAusente:
            trace.aviso(f"Parâmetro vazao_pessoa.{uso} não cadastrado — critério por ocupação não avaliado")
    if amb.get("vazao_termica_m3h"):
        q_cands["carga_termica"] = float(amb["vazao_termica_m3h"])
        trace.add("Vazão por carga térmica (informada)", "Q = valor informado", "cálculo térmico externo", q_cands["carga_termica"], "m³/h")
        trace.hipotese("Vazão para remoção de carga térmica informada pelo usuário — anexar memória do balanço térmico.")
    if not q_cands:
        return {"versao_motor": ENGINE_VERSION, "hash_entradas": hash_entradas(entradas), **trace.as_dict()}
    criterio = max(q_cands, key=q_cands.get)
    q_req = q_cands[criterio]
    trace.add("Vazão de renovação requerida", "Q = max(critérios)", f"critério governante: {criterio}", round(q_req, 1), "m³/h")

    modo = amb.get("modo_pressao", "negativa")
    pct = float(params.get("desbalanco_pressao_pct")) / 100.0
    if modo == "negativa":
        q_ins, q_exa = q_req, q_req * (1 + pct)
        txt = "exaustão maior que insuflamento (ambiente em pressão negativa)"
    elif modo == "positiva":
        q_exa, q_ins = q_req, q_req * (1 + pct)
        txt = "insuflamento maior que exaustão (ambiente em pressão positiva)"
    else:
        q_exa = q_ins = q_req
        txt = "insuflamento igual à exaustão (pressão neutra)"
    trace.add("Equilíbrio de pressão", "Q_exa / Q_ins", f"{txt}; desbalanço {fmt(pct*100,0)}%", f"{fmt(q_exa,0)} / {fmt(q_ins,0)}", "m³/h")

    t_c = float(amb.get("temperatura_c") or 25.0)
    rho = densidade(t_c, float(amb.get("altitude_m") or 0.0))
    p_req = float(params.get("dp_sistema_renovacao"))
    trace.hipotese(f"Cada equipamento de renovação vence uma pressão estática fixa de {fmt(p_req,0)} Pa (venezianas, telas e grelhas) — sistema sem rede de dutos.")
    opcoes, rejeitados = [], []
    for ex in exaustores:
        nome = f"{ex.get('codigo')} — {ex.get('modelo')}"
        try:
            curva = Curva.from_pontos(ex.get("curva") or [], ex.get("tipo_pressao_curva", "estatica"))
        except CurvaInvalida as e:
            rejeitados.append({"id": ex.get("id"), "nome": nome, "motivo": f"Curva inválida: {e}"})
            continue
        fr = rho / float(ex.get("densidade_referencia") or 1.2)
        q_op = _vazao_na_pressao(curva, p_req, fr)
        if q_op is None:
            rejeitados.append({"id": ex.get("id"), "nome": nome, "motivo": "Pressão requerida fora da faixa da curva cadastrada"})
            continue
        n_un = math.ceil((q_exa / 3600.0) / q_op - 1e-9)
        pot = curva.potencia(q_op)
        opcoes.append({
            "id": ex.get("id"), "nome": nome, "vazao_unitaria_m3h": q_op * 3600, "quantidade": n_un,
            "vazao_total_m3h": n_un * q_op * 3600,
            "potencia_total_kw": (pot * fr * n_un / 1000.0) if pot is not None else None,
            "custo_total": (float(ex["preco"]) * n_un) if ex.get("preco") else None,
        })
    opcoes.sort(key=lambda o: (o["potencia_total_kw"] if o["potencia_total_kw"] is not None else 1e18, o["quantidade"]))

    v_face = float(params.get("vel_face_veneziana"))
    a_ent = (q_ins / 3600.0) / v_face
    trace.add("Área livre de entrada de ar", "A = Q_ins/v_face", f"{fmt(q_ins/3600,3)}/{fmt(v_face,2)}", round(a_ent, 3), "m²")

    sugestao = None
    if opcoes:
        n_un = opcoes[0]["quantidade"]
        # Exaustores distribuídos na parede ao longo do comprimento (y = W), entradas na parede oposta (y = 0)
        pos_ex = [[round(L * (i + 0.5) / n_un, 3), W] for i in range(n_un)]
        n_ent = max(1, n_un)
        pos_in = [[round(L * (i + 0.5) / n_ent, 3), 0.0] for i in range(n_ent)]
        sugestao = {
            "exaustores": pos_ex, "entradas": pos_in,
            "observacao": "Exaustores na parte alta de uma parede longitudinal e entradas de ar na parte baixa da parede oposta, promovendo varredura do ambiente. Ajustar conforme obstáculos, ventos dominantes e fontes de calor.",
        }
    else:
        trace.aviso("Nenhum equipamento do catálogo atende à pressão requerida para renovação.")

    return {
        "versao_motor": ENGINE_VERSION,
        "hash_entradas": hash_entradas(entradas),
        "volume_m3": vol,
        "criterios_m3h": q_cands,
        "criterio_governante": criterio,
        "vazao_requerida_m3h": q_req,
        "vazao_exaustao_m3h": q_exa,
        "vazao_insuflamento_m3h": q_ins,
        "trocas_hora_resultantes": q_exa / vol,
        "modo_pressao": modo,
        "area_entrada_m2": a_ent,
        "opcoes_equipamento": opcoes,
        "rejeitados": rejeitados,
        "sugestao_posicionamento": sugestao,
        "parametros_usados": params.relatorio_usados(),
        "parametros_nao_aprovados": params.nao_aprovados(),
        **trace.as_dict(),
    }
