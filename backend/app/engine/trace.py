"""Registro auditável de cálculos: cada passo guarda fórmula, valores e unidade."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Passo:
    descricao: str
    formula: str
    substituicao: str
    resultado: float | str | None
    unidade: str = ""
    referencia: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "descricao": self.descricao,
            "formula": self.formula,
            "substituicao": self.substituicao,
            "resultado": self.resultado,
            "unidade": self.unidade,
            "referencia": self.referencia,
        }


@dataclass
class Trace:
    passos: list[Passo] = field(default_factory=list)
    hipoteses: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    bloqueios: list[str] = field(default_factory=list)

    def add(self, descricao, formula, substituicao, resultado, unidade="", referencia=""):
        self.passos.append(Passo(descricao, formula, substituicao, resultado, unidade, referencia))
        return resultado

    def hipotese(self, texto: str):
        if texto not in self.hipoteses:
            self.hipoteses.append(texto)

    def aviso(self, texto: str):
        if texto not in self.avisos:
            self.avisos.append(texto)

    def bloqueio(self, texto: str):
        if texto not in self.bloqueios:
            self.bloqueios.append(texto)

    def as_dict(self) -> dict[str, Any]:
        return {
            "passos": [p.as_dict() for p in self.passos],
            "hipoteses": list(self.hipoteses),
            "avisos": list(self.avisos),
            "bloqueios": list(self.bloqueios),
        }


def hash_entradas(obj: Any) -> str:
    """Hash SHA-256 canônico das entradas, para rastrear reprodutibilidade."""
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def fmt(x: float, nd: int = 3) -> str:
    """Formatação numérica em pt-BR (vírgula decimal)."""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")
