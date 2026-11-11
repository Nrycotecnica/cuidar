#!/bin/sh
# Backup diário do banco (pg_dump formato custom) e dos arquivos enviados, com retenção em dias.
set -u
RET="${RETENCAO_DIAS:-14}"
mkdir -p /backups
while true; do
  D=$(date +%Y%m%d-%H%M%S)
  if pg_dump --no-owner --format=custom -f "/backups/db-$D.dump"; then
    echo "[backup] banco OK: db-$D.dump"
  else
    echo "[backup] FALHA no pg_dump" >&2
  fi
  if tar -czf "/backups/arquivos-$D.tar.gz" -C /dados arquivos; then
    echo "[backup] arquivos OK: arquivos-$D.tar.gz"
  fi
  # Retenção: remove somente arquivos de backup antigos desta pasta
  find /backups -maxdepth 1 -type f \( -name 'db-*.dump' -o -name 'arquivos-*.tar.gz' \) -mtime +"$RET" -exec rm -f {} \;
  sleep 86400
done
