#!/usr/bin/env bash
# Restaura o banco de UM ambiente a partir de um arquivo .dump (pg_dump --format=custom).
#   uso: ./scripts/restaurar.sh producao backups/producao/db-20260101-030000.dump
# Pede confirmação digitando o nome do ambiente. Faça antes um backup do estado atual.
set -euo pipefail
cd "$(dirname "$0")/.."
AMB="${1:?ambiente: homologacao|producao}"
ARQ="${2:?arquivo .dump}"
case "$AMB" in
  homologacao) DB=db-homolog;  SVC=app-homolog ;;
  producao)    DB=db-producao; SVC=app-producao ;;
  *) echo "ambiente inválido"; exit 2 ;;
esac
[ -f "$ARQ" ] || { echo "arquivo não encontrado: $ARQ"; exit 2; }
COMPOSE=(docker compose -f docker-compose.servidor.yml --env-file .env)
if [ -z "${CONFIRMAR:-}" ]; then
  read -r -p "Isto SUBSTITUI o banco de $AMB pelo conteúdo de $ARQ. Digite '$AMB' para confirmar: " C
  [ "$C" = "$AMB" ] || { echo "cancelado"; exit 1; }
fi
"${COMPOSE[@]}" stop "$SVC"
"${COMPOSE[@]}" exec -T "$DB" sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' < "$ARQ"
"${COMPOSE[@]}" start "$SVC"
echo "Banco de $AMB restaurado a partir de $ARQ"
