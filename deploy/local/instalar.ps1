# Lki Industrial — instalação local no Windows
# Uso: clique com o botão direito em instalar.ps1 → "Executar com o PowerShell"
#      (ou, no PowerShell: powershell -ExecutionPolicy Bypass -File .\instalar.ps1)
# Requisito: Docker Desktop instalado e aberto (https://www.docker.com/products/docker-desktop/)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$Url = "http://localhost:8080"

function Escrever($texto, $cor = "White") { Write-Host $texto -ForegroundColor $cor }
function Segredo([int]$bytes = 32) {
    $b = New-Object byte[] $bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    return ([System.BitConverter]::ToString($b) -replace "-", "").ToLower()
}

Escrever "=== Lki Industrial — instalação local ===" Cyan

# 1. Docker
try { docker version --format "{{.Server.Version}}" | Out-Null }
catch {
    Escrever "O Docker não está disponível. Instale e ABRA o Docker Desktop e rode este script de novo:" Red
    Escrever "https://www.docker.com/products/docker-desktop/" Yellow
    Read-Host "Pressione Enter para sair"; exit 1
}

# 2. Configuração (.env) — criada uma única vez, com senhas aleatórias
if (-not (Test-Path ".env")) {
    $email = Read-Host "E-mail do administrador"
    do {
        $s1 = Read-Host "Senha do administrador (mínimo 8 caracteres)" -AsSecureString
        $s2 = Read-Host "Repita a senha" -AsSecureString
        $p1 = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s1))
        $p2 = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s2))
        if ($p1 -ne $p2) { Escrever "As senhas não conferem." Yellow }
        elseif ($p1.Length -lt 8) { Escrever "Senha muito curta." Yellow }
    } until ($p1 -eq $p2 -and $p1.Length -ge 8)
    $conteudo = @(
        "# Gerado por instalar.ps1 — NÃO compartilhe este arquivo",
        "TAG=main",
        "PORTA=8080",
        "APP_ENV=homologacao",
        "SEED_DEMO=true",
        "POSTGRES_PASSWORD=$(Segredo 24)",
        "SECRET_KEY=$(Segredo 32)",
        "ADMIN_EMAIL=$email",
        "ADMIN_PASSWORD=$p1",
        "ADMIN_NOME=Administrador",
        "ANTHROPIC_API_KEY="
    )
    # UTF-8 sem BOM (o Docker não aceita BOM no .env)
    [System.IO.File]::WriteAllLines((Join-Path $PSScriptRoot ".env"), $conteudo, (New-Object System.Text.UTF8Encoding $false))
    Escrever "Configuração criada (.env)." Green
} else {
    Escrever "Configuração existente mantida (.env)." Green
}
New-Item -ItemType Directory -Force -Path "backups" | Out-Null

# 3. Baixar e iniciar
Escrever "Baixando a versão mais recente (pode levar alguns minutos na primeira vez)..." Cyan
docker compose pull
docker compose up -d
if ($LASTEXITCODE -ne 0) { Escrever "Falha ao iniciar os contêineres." Red; Read-Host "Enter para sair"; exit 1 }

Escrever "Aguardando o sistema ficar pronto..." Cyan
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    try { if ((Invoke-WebRequest "$Url/api/saude" -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200) { $ok = $true; break } } catch {}
    Start-Sleep -Seconds 5
}
if (-not $ok) { Escrever "O sistema não respondeu. Veja os registros com: docker compose logs app" Red; Read-Host "Enter para sair"; exit 1 }

# 4. Atualização automática a cada 30 minutos (Agendador de Tarefas do Windows)
$acao = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSScriptRoot\atualizar.ps1`""
$gatilho = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName "LkiIndustrial-Atualizar" -Action $acao -Trigger $gatilho -Description "Baixa e aplica novas versões do Lki Industrial" -Force | Out-Null
Escrever "Atualização automática agendada (a cada 30 minutos)." Green

# 5. Acesso pelos outros computadores da rede (opcional, requer administrador)
$resp = Read-Host "Liberar o acesso pelos outros computadores da rede local? (s/n)"
if ($resp -match "^[sS]") {
    try {
        Start-Process powershell -Verb RunAs -Wait -ArgumentList "-NoProfile -Command `"New-NetFirewallRule -DisplayName 'Lki Industrial (8080)' -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Private,Domain`""
        Escrever "Porta 8080 liberada no firewall (redes privadas/domínio)." Green
    } catch { Escrever "Não foi possível liberar o firewall: $_" Yellow }
}

$ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notmatch "^(127\.|169\.254\.)" -and $_.InterfaceAlias -notmatch "vEthernet|WSL|Loopback" } | Select-Object -ExpandProperty IPAddress
Escrever ""
Escrever "=== Pronto! ===" Green
Escrever "Neste computador:  $Url"
foreach ($ip in $ips) { Escrever "Na rede local:     http://${ip}:8080" }
Escrever "Login: o e-mail e a senha informados acima."
Escrever "Importante: este computador e o Docker Desktop precisam estar ligados para o sistema funcionar." Yellow
Start-Process $Url
Read-Host "Pressione Enter para fechar"
