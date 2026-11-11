#!/bin/sh
# Backup diário do banco (pg_dump formato custom) e dos arquivos enviados, com retenção em dias.
# Aguarda o banco aceitar conexões e tenta novamente em caso de falha (nunca deixa arquivo vazio).
set -u
RET="${RETENCAO_DIAS:-14}"
mkdir -p /backups

fazer_backup() {
  D=$(date +%Y%m%d-%H%M%S)
  for tentativa in 1 2 3 4 5 6 7 8 9 10; do
    if pg_isready -q && pg_dump --no-owner --format=custom -f "/backups/.db-$D.parcial"; then
      mv "/backups/.db-$D.parcial" "/backups/db-$D.dump"
      echo "[backup] banco OK: db-$D.dump"
      break
    fi
    rm -f "/backups/.db-$D.parcial"
    echo "[backup] banco indisponível (tentativa $tentativa), nova tentativa em 30 s" >&2
    sleep 30
  done
  if tar -czf "/backups/arquivos-$D.tar.gz" -C /dados arquivos; then
    echo "[backup] arquivos OK: arquivos-$D.tar.gz"
  fi
  # Retenção: remove somente arquivos de backup antigos desta pasta
  find /backups -maxdepth 1 -type f \( -name 'db-*.dump' -o -name 'arquivos-*.tar.gz' \) -mtime +"$RET" -exec rm -f {} \;
}

while true; do
  fazer_backup
  sleep 86400
done
