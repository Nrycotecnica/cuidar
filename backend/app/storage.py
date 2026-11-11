"""Armazenamento de arquivos.

Implementação atual: sistema de arquivos local (volume persistente).
A interface permite trocar por armazenamento de objetos (S3/MinIO) — ainda não
implementado; ver PROGRESSO.md.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from .config import get_settings


class ArmazenamentoLocal:
    def __init__(self, raiz: str):
        self.raiz = Path(raiz)
        self.raiz.mkdir(parents=True, exist_ok=True)

    def salvar(self, dados: bytes, nome: str) -> tuple[str, str]:
        sha = hashlib.sha256(dados).hexdigest()
        ext = Path(nome).suffix.lower()[:10]
        chave = f"{sha[:2]}/{uuid.uuid4().hex}{ext}"
        p = self.raiz / chave
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(dados)
        return chave, sha

    def caminho(self, chave: str) -> Path:
        p = (self.raiz / chave).resolve()
        if self.raiz.resolve() not in p.parents:
            raise ValueError("Chave inválida")
        return p

    def ler(self, chave: str) -> bytes:
        return self.caminho(chave).read_bytes()


_inst: ArmazenamentoLocal | None = None


def storage() -> ArmazenamentoLocal:
    global _inst
    if _inst is None or str(_inst.raiz) != get_settings().storage_dir:
        _inst = ArmazenamentoLocal(get_settings().storage_dir)
    return _inst
