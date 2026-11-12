<# =============================================================================
   LKI INDUSTRIAL - instalador para Windows (sem Docker, sem administrador)

   Chamado pelo INSTALAR-LKI-INDUSTRIAL.cmd. Baixa o pacote oficial do GitHub,
   confere a impressao digital, instala em %LOCALAPPDATA%\LkiIndustrial, cria a
   configuracao com senhas aleatorias, cria os atalhos e abre o sistema.

   Parametros de teste: -Pacote <zip> -Manifesto <json> -Silencioso
   (no modo silencioso, e-mail e senha vem de LKI_ADMIN_EMAIL / LKI_ADMIN_SENHA)
============================================================================= #>
param([string]$Pacote, [string]$Manifesto, [switch]$Silencioso)
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'
$Raiz = Join-Path $env:LOCALAPPDATA 'LkiIndustrial'
$UrlBase = 'https://github.com/Nrycotecnica/cuidar/releases/download/lki-windows'
function Diga($txt, $cor = 'Gray') { Write-Host ('  ' + $txt) -ForegroundColor $cor }
function Falhar($txt) { Diga $txt 'Red'; if (-not $Silencioso) { Read-Host '  Enter para fechar' | Out-Null }; exit 1 }
function Segredo([int]$n) { $b = New-Object byte[] $n; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); return ([BitConverter]::ToString($b) -replace '-', '').ToLower() }
try { $Host.UI.RawUI.WindowTitle = 'LKI INDUSTRIAL - instalador' } catch { }

Write-Host ''
Write-Host '  ============================================================' -ForegroundColor DarkCyan
Write-Host '   LKI INDUSTRIAL - instalacao' -ForegroundColor Cyan
Write-Host '   Desenvolvido por Diego Pereira' -ForegroundColor DarkGray
Write-Host '  ============================================================' -ForegroundColor DarkCyan
Write-Host ''

if (Test-Path (Join-Path $Raiz 'programa\python\python.exe')) {
    Diga 'O LKI INDUSTRIAL ja esta instalado neste computador.' 'Yellow'
    Diga 'Para buscar a versao nova, use o atalho ATUALIZAR LKI INDUSTRIAL.' 'Yellow'
    if (-not $Silencioso) { Read-Host '  Enter para fechar' | Out-Null }
    exit 0
}

# ------------------------------------------------ 1. baixar e conferir
try {
    if ($Manifesto) { $man = Get-Content $Manifesto -Raw -Encoding UTF8 | ConvertFrom-Json }
    else { Diga 'Consultando a versao publicada...'; $man = Invoke-RestMethod ($UrlBase + '/versao.json?t=' + [DateTime]::UtcNow.Ticks) -TimeoutSec 20 }
} catch { Falhar 'Sem conexao com a internet (GitHub). Tente novamente.' }
Diga "Versao: $($man.versao)  ($([math]::Round($man.tamanho / 1MB)) MB)"
$tmp = Join-Path $env:TEMP ('lki-instalacao-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$zip = Join-Path $tmp 'pacote.zip'
try {
    if ($Pacote) { Copy-Item $Pacote $zip } else { Diga 'Baixando (pode levar alguns minutos)...'; Invoke-WebRequest ($UrlBase + '/' + $man.arquivo) -OutFile $zip -UseBasicParsing -TimeoutSec 1800 }
} catch { Falhar "Falha no download: $($_.Exception.Message)" }
if ((Get-FileHash $zip -Algorithm SHA256).Hash.ToLower() -ne $man.sha256.ToLower()) { Falhar 'O arquivo baixado nao conferiu (download incompleto). Tente novamente.' }

Diga 'Instalando...'
New-Item -ItemType Directory -Force -Path $Raiz | Out-Null
$prog = Join-Path $Raiz 'programa'
Remove-Item $prog -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -Path $zip -DestinationPath $prog -Force
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
$ferr = Join-Path $Raiz 'ferramentas'
New-Item -ItemType Directory -Force -Path $ferr | Out-Null
Copy-Item (Join-Path $prog 'ferramentas\*') $ferr -Force
. (Join-Path $ferr 'lki-comum.ps1')

# ------------------------------------------------ 2. configuracao
if (-not (Test-Path $ConfigArq)) {
    if ($Silencioso) { $email = $env:LKI_ADMIN_EMAIL; $senha = $env:LKI_ADMIN_SENHA }
    else {
        Write-Host ''
        Diga 'Crie o acesso do administrador do sistema:' 'Cyan'
        $email = Read-Host '  E-mail'
        do {
            $s1 = Read-Host '  Senha (minimo 8 caracteres)' -AsSecureString
            $s2 = Read-Host '  Repita a senha' -AsSecureString
            $senha = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s1))
            $senha2 = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s2))
            if ($senha -ne $senha2) { Diga 'As senhas nao conferem.' 'Yellow' } elseif ($senha.Length -lt 8) { Diga 'Senha muito curta.' 'Yellow' }
        } until ($senha -eq $senha2 -and $senha.Length -ge 8)
    }
    $linhas = @(
        '# LKI INDUSTRIAL - configuracao local. NAO compartilhe este arquivo.',
        'APP_ENV=homologacao',
        'PORTA=8080',
        'REDE=0',
        'SEED_DEMO=true',
        "SECRET_KEY=$(Segredo 32)",
        "ADMIN_EMAIL=$email",
        "ADMIN_PASSWORD=$senha",
        'ADMIN_NOME=Administrador',
        'ANTHROPIC_API_KEY='
    )
    [IO.File]::WriteAllLines($ConfigArq, $linhas, (New-Object Text.UTF8Encoding $false))
}

# ------------------------------------------------ 3. atalhos e primeira execucao
CriarAtalho 'LKI INDUSTRIAL' 'abrir.ps1' 'Abre o LKI INDUSTRIAL' -Minimizado
CriarAtalho 'ATUALIZAR LKI INDUSTRIAL' 'atualizar.ps1' 'Busca a versao mais nova do LKI INDUSTRIAL. Use com ninguem usando o sistema.'
CriarAtalho 'FECHAR LKI INDUSTRIAL' 'fechar.ps1' 'Fecha o LKI INDUSTRIAL' -Minimizado

Diga 'Iniciando o sistema pela primeira vez (pode levar um minuto)...'
if (-not (IniciarServidor)) { Falhar "Falha ao preparar o banco de dados. Veja: $Logs\migracao-erros.log" }
if (-not (EsperarSistema 180)) { Falhar "O sistema nao respondeu. Veja: $Logs\servidor-erros.log" }

Write-Host ''
Diga '=== Pronto! ===' 'Green'
Diga "Endereco: $(UrlLocal)"
Diga 'Atalhos criados na Area de Trabalho: LKI INDUSTRIAL, ATUALIZAR LKI INDUSTRIAL e FECHAR LKI INDUSTRIAL.'
Diga 'Entre com o e-mail e a senha que voce acabou de criar.'
if (-not $Silencioso) { Start-Process (UrlLocal); Read-Host '  Enter para fechar' | Out-Null }
exit 0
