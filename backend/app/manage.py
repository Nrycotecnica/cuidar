"""Comandos de manutenção: python -m app.manage <migrar|criar-admin|versao>"""

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from .config import get_settings

BASE = Path(__file__).resolve().parent.parent


def migrar():
    cfg = Config(str(BASE / "alembic.ini"))
    cfg.set_main_option("script_location", str(BASE / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
    command.upgrade(cfg, "head")
    print("Banco de dados atualizado (alembic head).")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "migrar":
        migrar()
    elif cmd == "versao":
        s = get_settings()
        print(s.app_version, s.git_sha, s.app_env)
    else:
        print(__doc__)
        sys.exit(1)
