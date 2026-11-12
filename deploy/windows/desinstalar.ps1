<# LKI INDUSTRIAL - desinstalar. Por padrao MANTEM os dados (banco e arquivos). #>
. (Join-Path $PSScriptRoot 'lki-comum.ps1')
$r = Read-Host 'Remover o LKI INDUSTRIAL deste computador? Os DADOS ficam guardados em dados\ (s/n)'
if ($r -notmatch '^[sS]') { exit 0 }
PararServidor
foreach ($pasta in @([Environment]::GetFolderPath('Desktop'))) {
    foreach ($n in 'LKI INDUSTRIAL', 'ATUALIZAR LKI INDUSTRIAL', 'FECHAR LKI INDUSTRIAL') { Remove-Item (Join-Path $pasta "$n.lnk") -ErrorAction SilentlyContinue }
}
Remove-Item (Join-Path ([Environment]::GetFolderPath('Programs')) 'LKI INDUSTRIAL') -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $Programa, $Anterior, (Join-Path $Raiz 'programa.falhou') -Recurse -Force -ErrorAction SilentlyContinue
Diga "Programa removido. Seus dados continuam em: $Dados" 'Yellow'
Diga 'Para apagar tudo, apague a pasta inteira depois de copiar o que quiser guardar.' 'Yellow'
Read-Host 'Enter para fechar' | Out-Null
