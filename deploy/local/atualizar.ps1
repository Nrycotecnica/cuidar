# Lki Industrial — atualização automática (chamada pelo Agendador de Tarefas a cada 30 min)
# Baixa a versão mais recente; se houver mudança, faz backup do banco e reinicia o sistema.
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot
$log = Join-Path $PSScriptRoot "atualizacoes.log"
function Log($m) { Add-Content -Path $log -Value ("{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $m) -Encoding UTF8 }

docker version --format "{{.Server.Version}}" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Log "Docker não está aberto; atualização adiada."; exit 0 }

$tag = ((Get-Content .env | Where-Object { $_ -match "^TAG=" }) -replace "^TAG=", "").Trim()
if (-not $tag) { $tag = "main" }
$imagem = "ghcr.io/nrycotecnica/cuidar:$tag"
$antes = docker image inspect $imagem --format "{{.Id}}" 2>$null
docker compose pull app 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Log "Falha ao baixar $imagem (sem internet?)."; exit 0 }
$depois = docker image inspect $imagem --format "{{.Id}}" 2>$null
if ($antes -eq $depois) { exit 0 }

New-Item -ItemType Directory -Force -Path "backups" | Out-Null
$arq = "backups\pre-atualizacao-{0:yyyyMMdd-HHmmss}.dump" -f (Get-Date)
docker compose exec -T db sh -c "pg_dump -U lki -d lki --no-owner --format=custom -f /tmp/pre.dump" 2>&1 | Out-Null
docker compose cp db:/tmp/pre.dump $arq 2>&1 | Out-Null
Log "Nova versão encontrada. Backup: $arq"

docker compose up -d app 2>&1 | Out-Null
$ok = $false
for ($i = 0; $i -lt 36; $i++) {
    try { if ((Invoke-WebRequest "http://localhost:8080/api/saude" -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200) { $ok = $true; break } } catch {}
    Start-Sleep -Seconds 5
}
if ($ok) { Log "Atualizado com sucesso ($depois)." }
else { Log "ATENÇÃO: o sistema não respondeu após a atualização. Veja: docker compose logs app. Backup do banco: $arq" }
