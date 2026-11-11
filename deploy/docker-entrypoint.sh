#!/bin/sh
# Aguarda o banco, aplica migrações (Alembic) e inicia a aplicação.
set -e
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
