"""Curvas de desempenho de exaustores, ponto de operação e seleção.

Regras:
* interpolação linear entre pontos cadastrados (auditável);
* NUNCA extrapola fora da faixa de vazão cadastrada;
* correção de densidade pelas leis dos ventiladores (pressão e potência ∝ ρ);
* se nenhum equipamento atende, informa explicitamente.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .trace import fmt


class CurvaInvalida(ValueError):
    pass


@dataclass
class Curva:
    q: list[float]  # m³/s, crescente
    p: list[float]  # Pa
    pot: list[float] | None = None  # W
    tipo_pressao: str = "estatica"  # estatica | total

    @classmethod
    def from_pontos(cls, pontos: list[dict], tipo_pressao: str = "estatica") -> "Curva":
        if len(pontos) < 2:
            raise CurvaInvalida("A curva precisa de pelo menos 2 pontos")
        pts = sorted(pontos, key=lambda d: d["vazao_m3h"])
        q = [float(d["vazao_m3h"]) / 3600.0 for d in pts]
        p = [float(d["pressao_pa"]) for d in pts]
        for i in range(1, len(q)):
            if q[i] <= q[i - 1]:
                raise CurvaInvalida("Vazões repetidas na curva")
        pot = None
        if all(d.get("potencia_kw") not in (None, "") for d in pts):
            pot = [float(d["potencia_kw"]) * 1000.0 for d in pts]
        if tipo_pressao not in ("estatica", "total"):
            raise CurvaInvalida("tipo_pressao deve ser 'estatica' ou 'total'")
        return cls(q, p, pot, tipo_pressao)

    @property
    def q_min(self) -> float:
        return self.q[0]

    @property
    def q_max(self) -> float:
        return self.q[-1]

    def _interp(self, ys: list[float], qx: float) -> float | None:
        if qx < self.q[0] - 1e-12 or qx > self.q[-1] + 1e-12:
            return None  # sem extrapolação
        for i in range(1, len(self.q)):
            if qx <= self.q[i] + 1e-12:
                q0, q1 = self.q[i - 1], self.q[i]
                t = (qx - q0) / (q1 - q0)
                return ys[i - 1] + t * (ys[i] - ys[i - 1])
        return ys[-1]

    def pressao(self, qx: float) -> float | None:
        return self._interp(self.p, qx)

    def potencia(self, qx: float) -> float | None:
        return self._interp(self.pot, qx) if self.pot else None


def ponto_operacao(curva: Curva, k_sistema: float, fator_densidade: float = 1.0) -> dict | None:
    """Interseção entre P_vent(Q)·fρ e P_sis = k·Q² (resolução exata por trecho linear).

    Retorna None se não houver interseção dentro da faixa cadastrada.
    Se houver mais de uma (curva com instabilidade), escolhe a de maior vazão
    e sinaliza."""
    sols: list[float] = []
    for i in range(1, len(curva.q)):
        q0, q1 = curva.q[i - 1], curva.q[i]
        p0, p1 = curva.p[i - 1] * fator_densidade, curva.p[i] * fator_densidade
        b = (p1 - p0) / (q1 - q0)
        a = p0 - b * q0
        # k·Q² - b·Q - a = 0
        if k_sistema <= 0:
            continue
        disc = b * b + 4 * k_sistema * a
        if disc < 0:
            continue
        for qs in ((b + math.sqrt(disc)) / (2 * k_sistema), (b - math.sqrt(disc)) / (2 * k_sistema)):
            if q0 - 1e-12 <= qs <= q1 + 1e-12 and qs > 0:
                if not any(abs(qs - s) < 1e-9 for s in sols):
                    sols.append(qs)
    if not sols:
        return None
    q = max(sols)
    p = curva.pressao(q) * fator_densidade
    pot = curva.potencia(q)
    return {
        "vazao_m3s": q,
        "vazao_m3h": q * 3600.0,
        "pressao_pa": p,
        "potencia_w": pot * fator_densidade if pot is not None else None,
        "multiplas_intersecoes": len(sols) > 1,
    }


def selecionar_exaustor(
    exaustores: list[dict],
    q_projeto_m3s: float,
    k_total: float,
    k_estatica: float,
    rho: float,
    temperatura_c: float,
    tolerancia_sup: float,
    requisitos: dict | None = None,
) -> dict:
    """Avalia todos os exaustores do catálogo e retorna os compatíveis ordenados
    por potência no ponto de operação, além dos rejeitados com o motivo."""
    requisitos = requisitos or {}
    compativeis, rejeitados = [], []
    for ex in exaustores:
        nome = f"{ex.get('codigo')} — {ex.get('modelo')}"
        motivo = None
        try:
            curva = Curva.from_pontos(ex.get("curva") or [], ex.get("tipo_pressao_curva", "estatica"))
        except CurvaInvalida as e:
            rejeitados.append({"id": ex.get("id"), "nome": nome, "motivo": f"Curva inválida: {e}"})
            continue
        tmax = ex.get("temperatura_max_c")
        if tmax is not None and temperatura_c > float(tmax):
            motivo = f"Temperatura de operação {fmt(temperatura_c, 0)} °C acima do limite do equipamento ({fmt(float(tmax), 0)} °C)"
        tipos_ok = requisitos.get("tipos_permitidos")
        if not motivo and tipos_ok and ex.get("tipo") not in tipos_ok:
            motivo = f"Tipo '{ex.get('tipo')}' não indicado para esta aplicação (permitidos: {', '.join(tipos_ok)})"
        if motivo:
            rejeitados.append({"id": ex.get("id"), "nome": nome, "motivo": motivo})
            continue
        rho_ref = float(ex.get("densidade_referencia") or 1.2)
        fr = rho / rho_ref
        k = k_estatica if curva.tipo_pressao == "estatica" else k_total
        op = ponto_operacao(curva, k, fr)
        if op is None:
            rejeitados.append({
                "id": ex.get("id"), "nome": nome,
                "motivo": "Sem interseção com a curva do sistema dentro da faixa cadastrada (não extrapolado)",
            })
            continue
        q_op = op["vazao_m3s"]
        if q_op < q_projeto_m3s * (1 - 1e-6):
            rejeitados.append({
                "id": ex.get("id"), "nome": nome,
                "motivo": f"Vazão no ponto de operação ({fmt(q_op*3600, 0)} m³/h) inferior à de projeto ({fmt(q_projeto_m3s*3600, 0)} m³/h)",
            })
            continue
        if q_op > q_projeto_m3s * (1 + tolerancia_sup):
            rejeitados.append({
                "id": ex.get("id"), "nome": nome,
                "motivo": f"Vazão no ponto de operação ({fmt(q_op*3600, 0)} m³/h) excede a de projeto em mais de {fmt(tolerancia_sup*100, 0)}% (superdimensionado)",
            })
            continue
        pot = op["potencia_w"]
        rend = None
        if pot is None and ex.get("rendimento"):
            # P = Q·ΔPt/η — usa pressão total do sistema no ponto
            pt = k_total * q_op * q_op
            rend = float(ex["rendimento"])
            pot = q_op * pt / rend
        elif pot:
            pt = k_total * q_op * q_op
            rend = q_op * pt / pot if pot > 0 else None
        pmotor = ex.get("potencia_motor_kw")
        if pot is not None and pmotor and pot / 1000.0 > float(pmotor):
            rejeitados.append({
                "id": ex.get("id"), "nome": nome,
                "motivo": f"Potência absorvida ({fmt(pot/1000, 2)} kW) acima da potência do motor ({fmt(float(pmotor), 2)} kW)",
            })
            continue
        compativeis.append({
            "id": ex.get("id"),
            "nome": nome,
            "codigo": ex.get("codigo"),
            "modelo": ex.get("modelo"),
            "tipo_pressao_curva": curva.tipo_pressao,
            "fator_densidade": fr,
            "ponto_operacao": op,
            "potencia_absorvida_kw": pot / 1000.0 if pot is not None else None,
            "rendimento_estimado": rend,
            "folga_vazao_pct": (q_op / q_projeto_m3s - 1) * 100 if q_projeto_m3s > 0 else None,
            "custo": ex.get("preco"),
            "curva_m3h_pa": [[round(qq * 3600, 3), round(pp * fr, 3)] for qq, pp in zip(curva.q, curva.p)],
        })
    compativeis.sort(key=lambda c: (c["potencia_absorvida_kw"] if c["potencia_absorvida_kw"] is not None else 1e18, c["custo"] or 1e18))
    return {
        "selecionado": compativeis[0] if compativeis else None,
        "compativeis": compativeis,
        "rejeitados": rejeitados,
        "mensagem": None if compativeis else "Nenhum exaustor do catálogo atende ao ponto de projeto. Não foi selecionado equipamento inadequado.",
    }
