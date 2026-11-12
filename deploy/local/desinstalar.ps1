# Lki Industrial — parar/desinstalar a instalação local
Set-Location -Path $PSScriptRoot
$r = Read-Host "Parar o sistema e remover a atualização automática? Os DADOS são mantidos. (s/n)"
if ($r -notmatch "^[sS]") { exit 0 }
docker compose down
Unregister-ScheduledTask -TaskName "LkiIndustrial-Atualizar" -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Sistema parado. Para APAGAR também os dados (banco e arquivos), rode: docker compose down -v" -ForegroundColor Yellow
Read-Host "Pressione Enter para fechar"
