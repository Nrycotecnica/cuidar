"""Conjunto de parâmetros técnicos cadastráveis.

O motor nunca define coeficientes por conta própria: ele consulta o
``ParameterSet``. Cada consulta é registrada para que a aprovação técnica
possa verificar se todos os parâmetros usados estão aprovados.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ParametroAusente(KeyError):
    def __init__(self, chave: str):
        super().__init__(chave)
        self.chave = chave

    def __str__(self) -> str:  # pragma: no cover - mensagem
        return f"Parâmetro técnico não cadastrado: {self.chave}"


@dataclass
class Parametro:
    chave: str
    valor: Any
    unidade: str = ""
    status: str = "proposto"  # proposto | aprovado
    referencia: str = ""
    demonstrativo: bool = False


@dataclass
class ParameterSet:
    itens: dict[str, Parametro] = field(default_factory=dict)
    usados: dict[str, Parametro] = field(default_factory=dict)

    @classmethod
    def from_list(cls, lista: list[dict[str, Any]]) -> "ParameterSet":
        ps = cls()
        for d in lista:
            p = Parametro(
                chave=d["chave"],
                valor=d["valor"],
                unidade=d.get("unidade", ""),
                status=d.get("status", "proposto"),
                referencia=d.get("referencia", ""),
                demonstrativo=bool(d.get("demonstrativo", False)),
            )
            ps.itens[p.chave] = p
        return ps

    def tem(self, chave: str) -> bool:
        return chave in self.itens

    def get(self, chave: str) -> Any:
        if chave not in self.itens:
            raise ParametroAusente(chave)
        p = self.itens[chave]
        self.usados[chave] = p
        return p.valor

    def get_opcional(self, chave: str, padrao: Any = None) -> Any:
        if chave not in self.itens:
            return padrao
        return self.get(chave)

    def relatorio_usados(self) -> list[dict[str, Any]]:
        return [
            {
                "chave": p.chave,
                "valor": p.valor,
                "unidade": p.unidade,
                "status": p.status,
                "referencia": p.referencia,
                "demonstrativo": p.demonstrativo,
            }
            for p in sorted(self.usados.values(), key=lambda x: x.chave)
        ]

    def nao_aprovados(self) -> list[str]:
        return sorted(k for k, p in self.usados.items() if p.status != "aprovado")
