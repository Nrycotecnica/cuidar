<# =============================================================================
   LKI INDUSTRIAL - funcoes comuns da instalacao para Windows (sem Docker)

   Estrutura em %LOCALAPPDATA%\LkiIndustrial:
     programa\            versao instalada (Python embutido + sistema + telas)
     programa.anterior\   versao anterior, para voltar atras
     ferramentas\         estes scripts (abrir, atualizar, fechar...)
     dados\               banco (app.db), arquivos enviados, backups e registros
     config.env           configuracao local (senhas) - nao compartilhar
   O programa e trocado inteiro a cada atualizacao; os dados nunca ficam dentro
   dele, para que uma atualizacao jamais encoste no que o usuario cadastrou.
============================================================================= #>

$Raiz       = Join-Path $env:LOCALAPPDATA 'LkiIndustrial'
$Programa   = Join-Path $Raiz 'programa'
$Anterior   = Join-Path $Raiz 'programa.anterior'
$Ferramentas = Join-Path $Raiz 'ferramentas'
$Dados      = Join-Path $Raiz 'dados'
$ConfigArq  = Join-Path $Raiz 'config.env'
$Banco      = Join-Path $Dados 'app.db'
$Backups    = Join-Path $Dados 'backups'
$Logs       = Join-Path $Dados 'logs'
$UrlBase    = 'https://github.com/Nrycotecnica/cuidar/releases/download/lki-windows'

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'

function Diga($txt, $cor = 'Gray') { Write-Host ('  ' + $txt) -ForegroundColor $cor }

function Registrar($m) {
    New-Item -ItemType Directory -Force -Path $Logs | Out-Null
    Add-Content -Path (Join-Path $Logs 'atualizacoes.log') -Value ('{0:yyyy-MM-dd HH:mm:ss} {1}' -f (Get-Date), $m) -Encoding UTF8
}

function LerConfig {
    $c = @{}
    if (Test-Path $ConfigArq) {
        foreach ($l in Get-Content $ConfigArq -Encoding UTF8) {
            if ($l -match '^\s*#' -or $l -notmatch '=') { continue }
            $i = $l.IndexOf('=')
            $c[$l.Substring(0, $i).Trim()] = $l.Substring($i + 1).Trim()
        }
    }
    return $c
}

function Porta { $p = (LerConfig)['PORTA']; if ($p) { return [int]$p } else { return 8080 } }
function UrlLocal { return 'http://127.0.0.1:' + (Porta) }

function SistemaNoAr {
    try { return ((Invoke-WebRequest ((UrlLocal) + '/api/saude') -UseBasicParsing -TimeoutSec 4).StatusCode -eq 200) } catch { return $false }
}

function EsperarSistema([int]$segundos = 120) {
    for ($i = 0; $i -lt [math]::Ceiling($segundos / 3); $i++) { if (SistemaNoAr) { return $true }; Start-Sleep -Seconds 3 }
    return $false
}

function LerVersao($pasta) {
    $f = Join-Path $pasta 'versao.json'
    if (Test-Path $f) { try { return (Get-Content $f -Raw -Encoding UTF8 | ConvertFrom-Json) } catch { } }
    return $null
}

function TextoVersao($v) { if ($v) { return "$($v.versao) ($($v.sha.Substring(0,7)))" } else { return 'desconhecida' } }

function PythonExe { return (Join-Path $Programa 'python\python.exe') }

# Variaveis de ambiente lidas pelo sistema (app/config.py). O processo do
# servidor herda estas variaveis de quem o inicia.
function PrepararAmbiente {
    $c = LerConfig
    $v = LerVersao $Programa
    New-Item -ItemType Directory -Force -Path $Dados, (Join-Path $Dados 'arquivos'), $Backups, $Logs | Out-Null
    $env:APP_ENV        = if ($c['APP_ENV']) { $c['APP_ENV'] } else { 'homologacao' }
    $env:DATABASE_URL   = 'sqlite:///' + ($Banco -replace '\\', '/')
    $env:STORAGE_DIR    = Join-Path $Dados 'arquivos'
    $env:FRONTEND_DIST  = Join-Path $Programa 'frontend\dist'
    $env:SECRET_KEY     = $c['SECRET_KEY']
    $env:ADMIN_EMAIL    = $c['ADMIN_EMAIL']
    $env:ADMIN_PASSWORD = $c['ADMIN_PASSWORD']
    $env:ADMIN_NOME     = if ($c['ADMIN_NOME']) { $c['ADMIN_NOME'] } else { 'Administrador' }
    $env:SEED_DEMO      = if ($c['SEED_DEMO']) { $c['SEED_DEMO'] } else { 'true' }
    $env:ANTHROPIC_API_KEY = $c['ANTHROPIC_API_KEY']
    if ($v) { $env:APP_VERSION = $v.versao; $env:GIT_SHA = $v.sha }
    $env:PYTHONUTF8 = '1'
}

function IniciarServidor {
    PrepararAmbiente
    $py = PythonExe
    $backend = Join-Path $Programa 'backend'
    $hostRede = if ((LerConfig)['REDE'] -eq '1') { '0.0.0.0' } else { '127.0.0.1' }
    # Migracoes do banco antes de subir (seguras: o Alembic so aplica o que falta).
    $p = Start-Process -FilePath $py -ArgumentList '-m', 'app.manage', 'migrar' -WorkingDirectory $backend -WindowStyle Hidden -Wait -PassThru `
        -RedirectStandardOutput (Join-Path $Logs 'migracao.log') -RedirectStandardError (Join-Path $Logs 'migracao-erros.log')
    if ($p.ExitCode -ne 0) { return $false }
    Start-Process -FilePath $py -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', $hostRede, '--port', (Porta) `
        -WorkingDirectory $backend -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $Logs 'servidor.log') -RedirectStandardError (Join-Path $Logs 'servidor-erros.log') | Out-Null
    return $true
}

function PararServidor {
    $porta = Porta
    $pids = @(Get-NetTCPConnection -LocalPort $porta -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
    foreach ($id in $pids) { if ($id -gt 0) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue } }
    for ($i = 0; $i -lt 20; $i++) { if (-not (SistemaNoAr)) { break }; Start-Sleep -Milliseconds 500 }
    Start-Sleep -Milliseconds 500
}

# Copia consistente do SQLite mesmo com o sistema no ar (API de backup do SQLite).
function CopiarBanco($destino) {
    if (-not (Test-Path $Banco)) { return $true }
    $py = PythonExe
    $cod = 'import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()'
    $p = Start-Process -FilePath $py -ArgumentList '-c', ('"' + $cod + '"'), ('"' + $Banco + '"'), ('"' + $destino + '"') -WindowStyle Hidden -Wait -PassThru
    return ($p.ExitCode -eq 0 -and (Test-Path $destino))
}

function BackupDiario {
    New-Item -ItemType Directory -Force -Path $Backups | Out-Null
    $hoje = Get-Date -Format 'yyyyMMdd'
    if (-not (Get-ChildItem $Backups -Filter "db-$hoje-*.sqlite" -ErrorAction SilentlyContinue)) {
        CopiarBanco (Join-Path $Backups ("db-{0:yyyyMMdd-HHmmss}.sqlite" -f (Get-Date))) | Out-Null
    }
    Get-ChildItem $Backups -Filter 'db-*.sqlite' -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item -Force -ErrorAction SilentlyContinue
}

function ManifestoRemoto {
    try { return Invoke-RestMethod ($UrlBase + '/versao.json?t=' + [DateTime]::UtcNow.Ticks) -TimeoutSec 15 } catch { return $null }
}

function CriarAtalho($nome, $script, $descricao, [switch]$Minimizado) {
    $ps = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $shell = New-Object -ComObject WScript.Shell
    $estilo = if ($Minimizado) { '-WindowStyle Minimized ' } else { '' }
    foreach ($pasta in @([Environment]::GetFolderPath('Desktop'), (Join-Path ([Environment]::GetFolderPath('Programs')) 'LKI INDUSTRIAL'))) {
        New-Item -ItemType Directory -Force -Path $pasta | Out-Null
        $a = $shell.CreateShortcut((Join-Path $pasta ($nome + '.lnk')))
        $a.TargetPath = $ps
        $a.Arguments = "-NoProfile -ExecutionPolicy Bypass $estilo-File `"$(Join-Path $Ferramentas $script)`""
        $a.WorkingDirectory = $Ferramentas
        $a.Description = $descricao
        $a.Save()
    }
}

function BaixarPacote($man, $destinoZip) {
    Invoke-WebRequest ($UrlBase + '/' + $man.arquivo) -OutFile $destinoZip -UseBasicParsing -TimeoutSec 900
    $h = (Get-FileHash $destinoZip -Algorithm SHA256).Hash.ToLower()
    return ($h -eq $man.sha256.ToLower())
}
