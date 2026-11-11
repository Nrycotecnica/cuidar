"""Vazão de captação por tipo de captor.

As equações são clássicas da literatura de ventilação industrial (por exemplo,
o manual da ACGIH, "Industrial Ventilation: A Manual of Recommended Practice
for Design"). Os FATORES numéricos (velocidade de captura, fator de flange,
fator da coifa) vêm do ``ParameterSet`` e precisam de aprovação técnica.
"""

from __future__ import annotations

from .params import ParameterSet
from .trace import Trace, fmt

TIPOS_CAPTOR = {
    "abertura_livre": "Abertura simples (sem flange)",
    "abertura_flangeada": "Abertura com flange",
    "enclausuramento": "Enclausuramento / cabine",
    "coifa_baixa": "Coifa sobre fonte (fria)",
    "vazao_informada": "Vazão informada manualmente",
}


def vazao_captor(captor: dict, params: ParameterSet, trace: Trace, rotulo: str) -> float:
    """Retorna a vazão de captação em m³/s e registra o cálculo no trace."""
    tipo = captor.get("tipo", "vazao_informada")
    if tipo == "vazao_informada":
        q_h = captor.get("vazao_m3h")
        if q_h is None or q_h <= 0:
            trace.bloqueio(f"{rotulo}: vazão não informada")
            return 0.0
        q = q_h / 3600.0
        trace.add(f"{rotulo}: vazão informada", "Q = Q_inf/3600", f"Q = {fmt(q_h, 1)}/3600", round(q, 6), "m³/s")
        trace.hipotese("Vazões informadas manualmente devem ter justificativa técnica registrada.")
        return q

    processo = captor.get("processo")
    if not processo:
        trace.bloqueio(f"{rotulo}: processo/condição de dispersão não informado para obter a velocidade de captura")
        return 0.0
    chave_vc = f"vel_captura.{processo}"
    if not params.tem(chave_vc):
        trace.bloqueio(f"{rotulo}: parâmetro {chave_vc} não cadastrado")
        return 0.0
    vc = float(params.get(chave_vc))

    if tipo in ("abertura_livre", "abertura_flangeada"):
        x = captor.get("distancia_m")
        a = captor.get("area_face_m2")
        if not x or not a:
            trace.bloqueio(f"{rotulo}: distância à fonte (X) e área de face (A) são obrigatórias")
            return 0.0
        q = vc * (10.0 * x * x + a)
        trace.add(
            f"{rotulo}: vazão de captação (Dalla Valle)",
            "Q = Vc·(10·X² + A)",
            f"Q = {fmt(vc, 2)}·(10·{fmt(x, 3)}² + {fmt(a, 4)})",
            round(q, 6),
            "m³/s",
            "Equação de Dalla Valle para aberturas (literatura de ventilação industrial)",
        )
        if tipo == "abertura_flangeada":
            ff = float(params.get("fator_flange"))
            q *= ff
            trace.add(f"{rotulo}: correção de flange", "Q_f = k_f·Q", f"k_f = {fmt(ff, 2)}", round(q, 6), "m³/s")
        d_eq = (4.0 * a / 3.141592653589793) ** 0.5
        if x > 1.5 * d_eq:
            trace.aviso(
                f"{rotulo}: X = {fmt(x, 2)} m maior que 1,5 vez o diâmetro equivalente da abertura ({fmt(d_eq, 2)} m). "
                "A equação de Dalla Valle costuma ser indicada apenas para distâncias menores — verificar o método e aproximar o captor se possível."
            )
        return q

    if tipo == "enclausuramento":
        a = captor.get("area_aberta_m2")
        if not a:
            trace.bloqueio(f"{rotulo}: área aberta do enclausuramento é obrigatória")
            return 0.0
        q = vc * a
        trace.add(f"{rotulo}: vazão do enclausuramento", "Q = Vf·A_aberta", f"Q = {fmt(vc, 2)}·{fmt(a, 4)}", round(q, 6), "m³/s")
        return q

    if tipo == "coifa_baixa":
        p = captor.get("perimetro_m")
        h = captor.get("altura_m")
        if not p or not h:
            trace.bloqueio(f"{rotulo}: perímetro e altura da coifa acima da fonte são obrigatórios")
            return 0.0
        k = float(params.get("fator_coifa"))
        q = k * p * h * vc
        trace.add(
            f"{rotulo}: vazão da coifa",
            "Q = k·P·H·V",
            f"Q = {fmt(k, 2)}·{fmt(p, 3)}·{fmt(h, 3)}·{fmt(vc, 2)}",
            round(q, 6),
            "m³/s",
            "Coifa sobre fonte fria (literatura de ventilação industrial)",
        )
        if captor.get("fonte_quente"):
            trace.bloqueio(
                f"{rotulo}: fonte quente — o método de coifa fria não se aplica; o cálculo por pluma térmica ainda não está implementado. Informe a vazão justificada."
            )
        return q

    trace.bloqueio(f"{rotulo}: tipo de captor desconhecido: {tipo}")
    return 0.0
