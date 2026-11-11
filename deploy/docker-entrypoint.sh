#!/bin/sh
# Ajusta a permissão do volume de arquivos, aguarda o banco, aplica migrações (Alembic)
# e inicia a aplicação sem privilégios de root.
set -e
if [ "$(id -u)" = "0" ]; then
  mkdir -p "${STORAGE_DIR:-/dados/arquivos}"
  chown -R app:app "$(dirname "${STORAGE_DIR:-/dados/arquivos}")"
  exec env HOME=/home/app setpriv --reuid=app --regid=app --init-groups "$0" "$@"
fi
python - <<'PY'
import time, sys
from sqlalchemy import create_engine, text
from app.config import get_settings
url = get_settings().database_url
for i in range(60):
    try:
        with create_engine(url).connect() as c:
            c.execute(text("SELECT 1"))
        break
    except Exception as e:
        print(f"Aguardando banco de dados ({i+1}/60): {e.__class__.__name__}", flush=True)
        time.sleep(2)
else:
    sys.exit("Banco de dados indisponível")
PY
python -m app.manage migrar
exec "$@"
