#!/usr/bin/env bash
# Atualiza UM ambiente para uma nova versão de imagem, com backup prévio do banco,
# verificação de saúde e retorno automático à versão anterior em caso de falha.
#   uso: ./scripts/atualizar.sh homologacao sha-abc1234
#        ./scripts/atualizar.sh producao v0.2.0
# Variável opcional SEM_PULL=1: usa imagem já presente localmente (testes).
set -euo pipefail
cd "$(dirname "$0")/.."
AMB="${1:?ambiente: homologacao|producao}"
TAG="${2:?tag da imagem}"
case "$AMB" in
  homologacao) SVC=app-homolog;  DB=db-homolog;  VAR=TAG_HOMOLOG ;;
  producao)    SVC=app-producao; DB=db-producao; VAR=TAG_PRODUCAO ;;
  *) echo "ambiente inválido: $AMB"; exit 2 ;;
esac
COMPOSE=(docker compose -f docker-compose.servidor.yml --env-file .env)
ANTERIOR=$(grep "^$VAR=" .env | cut -d= -f2-)
echo ">> $AMB: $ANTERIOR -> $TAG"

mkdir -p "backups/$AMB"
ARQ="backups/$AMB/pre-atualizacao-$(date +%Y%m%d-%H%M%S)-de-${ANTERIOR}.dump"
if [ -n "$("${COMPOSE[@]}" ps -q --status running "$DB")" ]; then
  "${COMPOSE[@]}" exec -T "$DB" sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --format=custom' > "$ARQ"
  echo ">> backup pré-atualização: $ARQ"
fi

reverter() {
  echo "!! $1. Revertendo $SVC para $ANTERIOR" >&2
  sed -i "s|^$VAR=.*|$VAR=$ANTERIOR|" .env
  "${COMPOSE[@]}" up -d --no-deps "$SVC" || true
  echo "$(date -Is) $AMB $ANTERIOR -> $TAG FALHOU ($1; revertido)" >> historico-implantacoes.log
  echo "!! Se a nova versão aplicou migrações de banco, restaure com: ./scripts/restaurar.sh $AMB $ARQ" >&2
  exit 1
}

sed -i "s|^$VAR=.*|$VAR=$TAG|" .env
if [ -z "${SEM_PULL:-}" ]; then
  "${COMPOSE[@]}" pull "$SVC" || reverter "falha ao baixar a imagem $TAG"
fi
"${COMPOSE[@]}" up -d --no-deps "$SVC" || reverter "falha ao iniciar o contêiner"

echo ">> aguardando verificação de saúde de $SVC..."
for _ in $(seq 1 ${TENTATIVAS_SAUDE:-40}); do
  CID=$("${COMPOSE[@]}" ps -q "$SVC")
  ST=$(docker inspect -f '{{.State.Health.Status}}' "$CID" 2>/dev/null || echo "?")
  if [ "$ST" = "healthy" ]; then
    echo "$(date -Is) $AMB $ANTERIOR -> $TAG OK" >> historico-implantacoes.log
    echo ">> $AMB atualizado para $TAG"
    exit 0
  fi
  sleep 5
done
reverter "o contêiner não ficou saudável"
