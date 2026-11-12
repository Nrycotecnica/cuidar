<# LKI INDUSTRIAL - abrir (atalho "LKI INDUSTRIAL")
   Liga o sistema se estiver parado (com backup diario do banco antes),
   avisa se ha versao nova (sem instalar) e abre o navegador. #>
param([switch]$SemNavegador)
$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'lki-comum.ps1')
try { $Host.UI.RawUI.WindowTitle = 'LKI INDUSTRIAL' } catch { }

Write-Host ''
Diga 'LKI INDUSTRIAL - iniciando...' 'Cyan'
if (-not (SistemaNoAr)) {
    BackupDiario
    if (-not (IniciarServidor)) {
        Diga "Falha ao preparar o banco de dados. Veja: $Logs\migracao-erros.log" 'Red'
        if (-not $SemNavegador) { Read-Host '  Enter para fechar' | Out-Null }
        exit 1
    }
    if (-not (EsperarSistema 120)) {
        Diga "O sistema nao respondeu. Veja: $Logs\servidor-erros.log" 'Red'
        if (-not $SemNavegador) { Read-Host '  Enter para fechar' | Out-Null }
        exit 1
    }
}
$man = ManifestoRemoto
$local = LerVersao $Programa
if ($man -and $local -and $man.sha -ne $local.sha) {
    Diga "Ha uma versao nova do LKI INDUSTRIAL ($($man.versao))." 'Green'
    Diga 'Quando ninguem estiver usando, clique no atalho ATUALIZAR LKI INDUSTRIAL.' 'Green'
    Start-Sleep -Seconds 4
}
if (-not $SemNavegador) { Start-Process (UrlLocal) }
exit 0
