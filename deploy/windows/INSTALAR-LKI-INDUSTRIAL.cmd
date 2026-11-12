@echo off
chcp 65001 >nul
title LKI INDUSTRIAL - instalador
echo.
echo   LKI INDUSTRIAL - baixando o instalador...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; $ProgressPreference='SilentlyContinue'; $f=Join-Path $env:TEMP 'lki-instalar.ps1'; try { Invoke-WebRequest 'https://github.com/Nrycotecnica/cuidar/releases/download/lki-windows/instalar.ps1' -OutFile $f -UseBasicParsing } catch { Write-Host '  Sem conexao com a internet. Tente novamente.' -ForegroundColor Red; Read-Host '  Enter para fechar'; exit 1 }; & powershell -NoProfile -ExecutionPolicy Bypass -File $f"
