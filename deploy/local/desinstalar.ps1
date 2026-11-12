<# LKI INDUSTRIAL - parar/desinstalar a instalacao local (os DADOS sao mantidos) #>
Set-Location -Path $PSScriptRoot
$r = Read-Host "Parar o sistema e remover os atalhos? Os DADOS sao mantidos. (s/n)"
if ($r -notmatch "^[sS]") { exit 0 }
docker compose down
Unregister-ScheduledTask -TaskName "LkiIndustrial-Atualizar" -Confirm:$false -ErrorAction SilentlyContinue
$mesa = [Environment]::GetFolderPath("Desktop")
Remove-Item (Join-Path $mesa "LKI INDUSTRIAL.lnk"), (Join-Path $mesa "ATUALIZAR LKI INDUSTRIAL.lnk") -ErrorAction SilentlyContinue
Write-Host "Sistema parado e atalhos removidos. Para APAGAR tambem os dados (banco e arquivos): docker compose down -v" -ForegroundColor Yellow
Read-Host "Pressione Enter para fechar"
