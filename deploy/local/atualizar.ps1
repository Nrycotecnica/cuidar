<# =============================================================================
   LKI INDUSTRIAL - ATUALIZADOR  (atalho "ATUALIZAR LKI INDUSTRIAL")

   Mesmo esquema do STAGE NRYCO:
   1. So atualiza quando alguem clica. Nada troca sozinho no meio do trabalho.
   2. Antes de trocar, confere se ha versao nova (sem baixar nada).
   3. Backup do banco antes de trocar a versao.
   4. Se a versao nova nao subir saudavel, volta sozinho para a anterior.
   Tambem atualiza os arquivos desta pasta (scripts e configuracao).

   Uso: clique no atalho com ninguem usando o sistema.
   Parametros: -SoVerificar (so diz se ha novidade)  -Silencioso (sem perguntas)
============================================================================= #>
param([switch]$SoVerificar, [switch]$Silencioso)
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot
try { $Host.UI.RawUI.WindowTitle = "LKI INDUSTRIAL - atualizador" } catch { }
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

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

$log = Join-Path $PSScriptRoot "atualizacoes.log"
function Log($m) { Add-Content -Path $log -Value ("{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $m) -Encoding UTF8 }
function Fim($codigo) { if (-not $Silencioso) { Write-Host ""; Read-Host "  Enter para fechar" | Out-Null }; exit $codigo }

if (-not $Silencioso) {
    Write-Host ""
    Write-Host "  ============================================================" -ForegroundColor DarkCyan
    Write-Host "   LKI INDUSTRIAL - ATUALIZADOR" -ForegroundColor Cyan
    Write-Host "  ============================================================" -ForegroundColor DarkCyan
    Write-Host ""
}

if (-not (LigarDocker)) { Diga "O Docker Desktop nao esta aberto. Abra-o e tente de novo. Nada foi alterado." "Yellow"; Fim 1 }

Diga "consultando a versao publicada..."
$novidade = HaNovidade
if ($null -eq $novidade) { Diga "Sem conexao com o GitHub. Nada foi alterado." "Yellow"; Fim 0 }
if ($SoVerificar) {
    if ($novidade) { Diga "Ha uma versao nova disponivel." "Green"; exit 10 } else { Diga "Voce ja esta na versao mais recente."; exit 0 }
}

# ------------------------------------------------ arquivos desta pasta
# Baixa as versoes novas dos scripts/configuracao; so troca o que mudou e
# guarda copia (.anterior). Arquivo vazio ou falha de rede: fica o que esta.
$arquivos = @(
    @{ Remoto = "deploy/local/docker-compose.yml"; Local = "docker-compose.yml" },
    @{ Remoto = "deploy/local/atualizar.ps1";      Local = "atualizar.ps1" },
    @{ Remoto = "deploy/local/abrir.ps1";          Local = "abrir.ps1" },
    @{ Remoto = "deploy/local/desinstalar.ps1";    Local = "desinstalar.ps1" },
    @{ Remoto = "deploy/local/LEIAME.md";          Local = "LEIAME.md" },
    @{ Remoto = "deploy/scripts/backup-loop.sh";   Local = "..\scripts\backup-loop.sh" }
)
$trocados = 0
foreach ($a in $arquivos) {
    $tmp = [IO.Path]::GetTempFileName()
    try {
        Invoke-WebRequest "$Repo/$($a.Remoto)?t=$([DateTime]::UtcNow.Ticks)" -UseBasicParsing -OutFile $tmp -TimeoutSec 20
        if ((Get-Item $tmp).Length -gt 0) {
            $destino = Join-Path $PSScriptRoot $a.Local
            $igual = (Test-Path $destino) -and ((Get-FileHash $tmp).Hash -eq (Get-FileHash $destino).Hash)
            if (-not $igual) {
                if (Test-Path $destino) { Copy-Item $destino "$destino.anterior" -Force }
                New-Item -ItemType Directory -Force -Path (Split-Path $destino) | Out-Null
                Copy-Item $tmp $destino -Force
                $trocados++
            }
        }
    } catch { } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}
if ($trocados -gt 0) { Diga "$trocados arquivo(s) da instalacao atualizado(s)." "Green"; Log "$trocados arquivo(s) da pasta atualizados" }

if (-not $novidade) {
    if ($trocados -gt 0) { docker compose up -d 2>&1 | Out-Null }
    Diga "Voce ja esta na versao mais recente: $(VersaoInstalada)" "Green"
    Fim 0
}

$antes = VersaoInstalada
Diga "Versao instalada: $antes"
Diga "Ha uma versao nova. Ninguem deve estar usando o sistema durante a atualizacao (1 a 3 minutos)." "Yellow"
if (-not $Silencioso) {
    $r = Read-Host "  Atualizar agora? (s/n)"
    if ($r -notmatch "^[sS]") { Diga "Cancelado. Nada foi alterado."; Fim 0 }
}

# ------------------------------------------------ backup e troca
New-Item -ItemType Directory -Force -Path "backups" | Out-Null
$anterior = docker image inspect $Imagem --format "{{.Id}}" 2>$null
if ($anterior) { docker tag $anterior "lki-industrial:anterior" 2>&1 | Out-Null }
$arq = "backups\pre-atualizacao-{0:yyyyMMdd-HHmmss}.dump" -f (Get-Date)
Diga "Fazendo backup do banco..."
docker compose exec -T db sh -c "pg_dump -U lki -d lki --no-owner --format=custom -f /tmp/pre.dump" 2>&1 | Out-Null
docker compose cp db:/tmp/pre.dump $arq 2>&1 | Out-Null
if (Test-Path $arq) { Diga "Backup: $arq" "Green" } else { Diga "Nao foi possivel fazer o backup; atualizacao cancelada." "Red"; Log "backup falhou; cancelado"; Fim 1 }

Diga "Baixando a versao nova..."
docker compose pull app 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Diga "Falha ao baixar. Nada foi alterado." "Red"; Log "falha no download"; Fim 1 }
Diga "Reiniciando o sistema..."
docker compose up -d 2>&1 | Out-Null

if (EsperarSistema 180) {
    $depois = VersaoInstalada
    Diga "Atualizado: $antes  ->  $depois" "Green"
    Log "Atualizado: $antes -> $depois (backup $arq)"
    Fim 0
}

# ------------------------------------------------ volta atras
Diga "A versao nova nao respondeu. Voltando para a anterior..." "Red"
if ($anterior) {
    docker tag "lki-industrial:anterior" $Imagem 2>&1 | Out-Null
    docker compose up -d app 2>&1 | Out-Null
}
if (EsperarSistema 120) {
    Diga "Sistema de volta na versao anterior ($(VersaoInstalada))." "Yellow"
    Diga "Se algo estiver estranho nos dados, restaure o backup: $arq (veja LEIAME.md)." "Yellow"
    Log "FALHA na versao nova; voltou para $antes. Backup: $arq"
    Fim 1
}
Diga "O sistema nao respondeu nem na versao anterior. Veja: docker compose logs app" "Red"
Log "FALHA grave: sistema fora do ar apos tentar voltar. Backup: $arq"
Fim 2
