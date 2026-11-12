<# LKI INDUSTRIAL - liberar o acesso pela rede local (atalho "LIBERAR REDE LKI INDUSTRIAL")

   Cria UMA regra no Firewall do Windows: entrada TCP na porta do sistema,
   somente perfis Privado/Dominio e somente da sub-rede local. Nunca abre para
   a internet nem para redes publicas (cafe, hotel). E o unico passo que pede
   administrador: o Windows mostra o "Sim" uma vez.
   Depois passa o sistema a atender a rede (REDE=1) e reinicia o servidor.

   Codigos de saida: 0 liberado | 5 o usuario recusou o pedido do Windows | 1 erro #>
param([switch]$Silencioso, [switch]$Elevado)
$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'lki-comum.ps1')
$Nome = 'LKI INDUSTRIAL (rede local)'
function RegraExiste { return ($null -ne (Get-NetFirewallRule -DisplayName $Nome -ErrorAction SilentlyContinue)) }
function CriarRegra {
    New-NetFirewallRule -DisplayName $Nome -Description 'Acesso ao LKI INDUSTRIAL pelos computadores da rede local' `
        -Direction Inbound -Action Allow -Protocol TCP -LocalPort (Porta) -Profile Private, Domain -RemoteAddress LocalSubnet | Out-Null
}
function Fim($c) { if (-not $Silencioso -and -not $Elevado) { Read-Host '  Enter para fechar' | Out-Null }; exit $c }

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($Elevado) { try { if (-not (RegraExiste)) { CriarRegra }; exit 0 } catch { exit 1 } }

if (-not (RegraExiste)) {
    if ($admin) {
        try { CriarRegra } catch { Diga "Nao foi possivel criar a regra: $($_.Exception.Message)" 'Red'; Fim 1 }
    } else {
        Diga 'O Windows vai pedir permissao para liberar o firewall (clique em Sim)...' 'Cyan'
        try {
            $p = Start-Process -FilePath (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') -Verb RunAs -WindowStyle Hidden -Wait -PassThru `
                -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Elevado"
        } catch { Diga 'Pedido de permissao recusado. Nada foi alterado.' 'Yellow'; Fim 5 }
        if (-not (RegraExiste)) { Diga 'A regra do firewall nao foi criada.' 'Red'; Fim 1 }
    }
}

# Sistema passa a atender a rede local (antes so o proprio computador).
$linhas = @(if (Test-Path $ConfigArq) { Get-Content $ConfigArq -Encoding UTF8 } else { @() })
if ($linhas -match '^REDE=') { $linhas = $linhas -replace '^REDE=.*', 'REDE=1' } else { $linhas += 'REDE=1' }
[IO.File]::WriteAllLines($ConfigArq, $linhas, (New-Object Text.UTF8Encoding $false))
if (SistemaNoAr) { PararServidor; IniciarServidor | Out-Null; EsperarSistema 120 | Out-Null }

Diga 'Rede local liberada. Nos outros computadores da rede, use:' 'Green'
$ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' -and $_.InterfaceAlias -notmatch 'vEthernet|WSL|Loopback' } | Select-Object -ExpandProperty IPAddress
foreach ($ip in $ips) { Diga ("  http://{0}:{1}" -f $ip, (Porta)) 'Green' }
Fim 0
