<# LKI INDUSTRIAL - fechar (atalho "FECHAR LKI INDUSTRIAL") #>
. (Join-Path $PSScriptRoot 'lki-comum.ps1')
PararServidor
Diga 'LKI INDUSTRIAL fechado.' 'Green'
Start-Sleep -Seconds 2
