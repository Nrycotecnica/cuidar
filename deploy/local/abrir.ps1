<# LKI INDUSTRIAL - abrir (atalho "LKI INDUSTRIAL")
   Garante que o Docker e o sistema estao ligados, avisa se ha versao nova
   (sem atualizar) e abre o navegador. #>
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot
try { $Host.UI.RawUI.WindowTitle = "LKI INDUSTRIAL" } catch { }

$Imagem = "ghcr.io/nrycotecnica/cuidar:main"
$Url = "http://localhost:8080"
$Repo = "https://raw.githubusercontent.com/Nrycotecnica/cuidar/main"
function Diga($txt, $cor = "Gray") { Write-Host ("  " + $txt) -ForegroundColor $cor }
function DockerNoAr { docker version --format "{{.Server.Version}}" 2>$null | Out-Null; return ($LASTEXITCODE -eq 0) }
function LigarDocker {
    if (DockerNoAr) { return $true }
    $exe = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (Test-Path $exe) { Diga "Abrindo o Docker Desktop..." "Cyan"; Start-Process $exe | Out-Null }
    for ($i = 0; $i -lt 60; $i++) { Start-Sleep -Seconds 3; if (DockerNoAr) { return $true } }
    return $false
}
function SistemaNoAr {
    try { return ((Invoke-WebRequest "$Url/api/saude" -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200) } catch { return $false }
}
function EsperarSistema([int]$segundos = 180) {
    for ($i = 0; $i -lt ($segundos / 5); $i++) { if (SistemaNoAr) { return $true }; Start-Sleep -Seconds 5 }
    return $false
}
function VersaoInstalada {
    try { $v = Invoke-RestMethod "$Url/api/versao" -TimeoutSec 5; return "$($v.versao) ($($v.git_sha))" } catch { return "desconhecida" }
}
# Impressao digital da versao publicada x da versao que esta nesta maquina.
# A consulta nao baixa a imagem: so le o indice no GitHub.
function DigestRemoto {
    $saida = docker buildx imagetools inspect $Imagem 2>$null | Select-String -Pattern "^Digest:\s+(sha256:[0-9a-f]+)" | Select-Object -First 1
    if ($saida) { return $saida.Matches[0].Groups[1].Value } else { return $null }
}
function DigestLocal {
    $d = docker image inspect $Imagem --format "{{range .RepoDigests}}{{.}} {{end}}" 2>$null
    if (-not $d) { return @() }
    return @($d.Trim().Split(" ") | ForEach-Object { ($_ -split "@")[-1] })
}
function HaNovidade {
    $r = DigestRemoto
    if (-not $r) { return $null }          # sem internet: nao sabemos
    return -not ((DigestLocal) -contains $r)
}

Write-Host ""
Diga "LKI INDUSTRIAL - iniciando..." "Cyan"
if (-not (LigarDocker)) { Diga "Nao foi possivel abrir o Docker Desktop. Abra-o manualmente e tente de novo." "Red"; Read-Host "  Enter para fechar"; exit 1 }
if (-not (SistemaNoAr)) {
    docker compose up -d 2>&1 | Out-Null
    if (-not (EsperarSistema 180)) { Diga "O sistema nao respondeu. Veja: docker compose logs app" "Red"; Read-Host "  Enter para fechar"; exit 1 }
}
$nov = HaNovidade
if ($nov -eq $true) {
    Diga "Ha uma versao nova do LKI INDUSTRIAL." "Green"
    Diga "Quando ninguem estiver usando, clique no atalho ATUALIZAR LKI INDUSTRIAL." "Green"
    Start-Sleep -Seconds 4
}
Start-Process $Url
