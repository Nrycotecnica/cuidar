"""Suporte a DWG via conversão externa.

Bibliotecas DXF (como o ezdxf) NÃO leem DWG. A conversão depende de uma
ferramenta externa instalada no servidor, por exemplo o ODA File Converter
(gratuito, distribuído pela Open Design Alliance, sujeito à licença dela).
Configure ODA_CONVERTER_PATH com o executável. Sem ele, o usuário deve
exportar o arquivo como DXF no AutoCAD (comando SALVARCOMO/SAVEAS → DXF).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from ..config import get_settings


class DWGIndisponivel(RuntimeError):
    pass


def disponivel() -> bool:
    p = get_settings().oda_converter_path
    return bool(p) and (Path(p).exists() or shutil.which(p) is not None)


def converter_dwg_para_dxf(dados: bytes) -> bytes:
    if not disponivel():
        raise DWGIndisponivel(
            "Conversão de DWG não configurada neste servidor. Exporte o desenho como DXF no AutoCAD "
            "(Salvar como → DXF) ou configure o ODA File Converter (ODA_CONVERTER_PATH)."
        )
    exe = get_settings().oda_converter_path
    with tempfile.TemporaryDirectory() as td:
        ent, sai = Path(td) / "in", Path(td) / "out"
        ent.mkdir()
        sai.mkdir()
        (ent / "desenho.dwg").write_bytes(dados)
        # Sintaxe documentada do ODA File Converter: entrada saída versão tipo recursivo auditoria [filtro]
        cmd = [exe, str(ent), str(sai), "ACAD2018", "DXF", "0", "1", "*.DWG"]
        r = subprocess.run(cmd, capture_output=True, timeout=300)
        out = list(sai.glob("*.dxf"))
        if r.returncode != 0 or not out:
            raise DWGIndisponivel(f"Falha na conversão DWG→DXF: {r.stderr.decode(errors='ignore')[:500]}")
        return out[0].read_bytes()
