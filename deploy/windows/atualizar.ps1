<# =============================================================================
   LKI INDUSTRIAL - ATUALIZADOR (atalho "ATUALIZAR LKI INDUSTRIAL")

   Mesmo esquema do STAGE NRYCO:
   1. So atualiza quando alguem clica - nunca no meio do trabalho de alguem.
   2. Confere a impressao digital (sha256) do pacote baixado com a anunciada.
      Download cortado ou adulterado e descartado; nada e trocado.
   3. Backup do banco antes de trocar.
   4. Se a versao nova nao subir saudavel, volta sozinho: programa anterior e
      banco de antes da atualizacao (a nova versao pode ter migrado o banco).

   Parametros: -SoVerificar  -Silencioso  -Pacote <zip> -Manifesto <json> (testes)
============================================================================= #>
param([switch]$SoVerificar, [switch]$Silencioso, [string]$Pacote, [string]$Manifesto)
$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'lki-comum.ps1')
try { $Host.UI.RawUI.WindowTitle = 'LKI INDUSTRIAL - atualizador' } catch { }
function Fim($codigo) { if (-not $Silencioso) { Write-Host ''; Read-Host '  Enter para fechar' | Out-Null }; exit $codigo }

if (-not $Silencioso) {
    Write-Host ''
    Write-Host '  ============================================================' -ForegroundColor DarkCyan
    Write-Host '   LKI INDUSTRIAL - ATUALIZADOR' -ForegroundColor Cyan
    Write-Host '  ============================================================' -ForegroundColor DarkCyan
    Write-Host ''
}

$local = LerVersao $Programa
if ($Manifesto) { $man = Get-Content $Manifesto -Raw -Encoding UTF8 | ConvertFrom-Json } else { Diga 'consultando a versao publicada...'; $man = ManifestoRemoto }
if (-not $man) { Diga 'Sem conexao com a internet. Nada foi alterado.' 'Yellow'; Fim 0 }
Diga "Versao instalada: $(TextoVersao $local)"
if ($local -and $man.sha -eq $local.sha) { Diga 'Voce ja esta na versao mais recente.' 'Green'; Fim 0 }
Diga "Versao nova: $($man.versao) ($($man.sha.Substring(0,7)))" 'Green'
if ($SoVerificar) { exit 10 }

if (-not $Silencioso) {
    Diga 'Ninguem deve estar usando o sistema durante a atualizacao (1 a 3 minutos).' 'Yellow'
    $r = Read-Host '  Atualizar agora? (s/n)'
    if ($r -notmatch '^[sS]') { Diga 'Cancelado. Nada foi alterado.'; Fim 0 }
}

# ------------------------------------------------ baixar e conferir
$tmp = Join-Path $env:TEMP ('lki-atualizacao-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$zip = Join-Path $tmp 'pacote.zip'
if ($Pacote) {
    Copy-Item $Pacote $zip
    $ok = ((Get-FileHash $zip -Algorithm SHA256).Hash.ToLower() -eq $man.sha256.ToLower())
} else {
    Diga 'Baixando a versao nova...'
    try { $ok = BaixarPacote $man $zip } catch { $ok = $false }
}
if (-not $ok) { Diga 'O download nao conferiu (impressao digital diferente). Nada foi alterado.' 'Red'; Registrar 'download nao conferiu; nada alterado'; Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue; Fim 1 }
$nova = Join-Path $Raiz 'programa.nova'
Remove-Item $nova -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -Path $zip -DestinationPath $nova -Force
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
if (-not (Test-Path (Join-Path $nova 'python\python.exe'))) { Diga 'Pacote incompleto. Nada foi alterado.' 'Red'; Remove-Item $nova -Recurse -Force; Fim 1 }

# ------------------------------------------------ backup e troca
Diga 'Fechando o sistema e fazendo backup do banco...'
PararServidor
$bk = Join-Path $Backups ('pre-atualizacao-{0:yyyyMMdd-HHmmss}.sqlite' -f (Get-Date))
New-Item -ItemType Directory -Force -Path $Backups | Out-Null
if (-not (CopiarBanco $bk)) { Diga 'Nao foi possivel fazer o backup; atualizacao cancelada.' 'Red'; Remove-Item $nova -Recurse -Force; IniciarServidor | Out-Null; Fim 1 }
Remove-Item $Anterior -Recurse -Force -ErrorAction SilentlyContinue
Rename-Item $Programa $Anterior
Rename-Item $nova $Programa

Diga 'Iniciando a versao nova...'
if ((IniciarServidor) -and (EsperarSistema 150)) {
    Copy-Item (Join-Path $Programa 'ferramentas\*') $Ferramentas -Force
    $agora = LerVersao $Programa
    Diga "Atualizado: $(TextoVersao $local)  ->  $(TextoVersao $agora)" 'Green'
    Registrar "Atualizado: $(TextoVersao $local) -> $(TextoVersao $agora) (backup $bk)"
    Fim 0
}

# ------------------------------------------------ volta atras
Diga 'A versao nova nao respondeu. Voltando para a anterior...' 'Red'
PararServidor
$falhou = Join-Path $Raiz 'programa.falhou'
Remove-Item $falhou -Recurse -Force -ErrorAction SilentlyContinue
Rename-Item $Programa $falhou
Rename-Item $Anterior $Programa
if (Test-Path $bk) { Copy-Item $bk $Banco -Force }
if ((IniciarServidor) -and (EsperarSistema 120)) {
    Diga "Sistema de volta na versao anterior ($(TextoVersao (LerVersao $Programa))), com o banco de antes da atualizacao." 'Yellow'
    Registrar "FALHA na versao $($man.versao); voltou para $(TextoVersao $local). Backup: $bk"
    Fim 2
}
Diga "O sistema nao respondeu nem na versao anterior. Veja: $Logs" 'Red'
Registrar "FALHA grave apos voltar. Backup: $bk"
Fim 3
