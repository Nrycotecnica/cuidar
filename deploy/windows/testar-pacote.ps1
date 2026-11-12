<# Teste ponta a ponta do pacote Windows (GitHub Actions, windows-latest):
   instalacao, login, calculo, DXF, atualizacao e volta atras automatica. #>
param([string]$Saida = 'saida')
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$out = Join-Path $repo $Saida
$Url = 'http://127.0.0.1:8080'
$ferr = Join-Path $env:LOCALAPPDATA 'LkiIndustrial\ferramentas'
function Confere($cond, $msg) { if (-not $cond) { throw "FALHOU: $msg" } else { Write-Host "OK: $msg" -ForegroundColor Green } }
function Login { (Invoke-RestMethod -Method Post "$Url/api/auth/login" -ContentType 'application/json' -Body (@{ email = 'teste@lki.local'; senha = 'SenhaTeste123' } | ConvertTo-Json)).token }
function Mostrar-Logs { Get-ChildItem (Join-Path $env:LOCALAPPDATA 'LkiIndustrial\dados\logs') -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "--- $($_.Name)"; Get-Content $_.FullName -Tail 40 } }

try {
    # 1. instalacao
    $env:LKI_ADMIN_EMAIL = 'teste@lki.local'; $env:LKI_ADMIN_SENHA = 'SenhaTeste123'
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $out 'instalar.ps1') -Pacote (Join-Path $out 'LKI-INDUSTRIAL-windows.zip') -Manifesto (Join-Path $out 'versao.json') -Silencioso
    Confere ($LASTEXITCODE -eq 0) 'instalador terminou sem erro'
    $saude = Invoke-RestMethod "$Url/api/saude"
    Confere ($saude.status -eq 'ok') "sistema no ar ($($saude.versao))"
    Confere ((Invoke-WebRequest "$Url/" -UseBasicParsing).Content -match 'Lki Industrial') 'tela inicial servida'
    Confere (Test-Path (Join-Path ([Environment]::GetFolderPath('Desktop')) 'ATUALIZAR LKI INDUSTRIAL.lnk')) 'atalho ATUALIZAR criado'

    # 2. uso real: login, roteamento, calculo e DXF
    $h = @{ Authorization = 'Bearer ' + (Login) }
    $proj = (Invoke-RestMethod "$Url/api/projetos" -Headers $h) | Where-Object { $_.codigo -eq 'DEMO-0001' }
    Confere ($proj) 'projeto demonstrativo presente'
    Invoke-RestMethod -Method Post "$Url/api/projetos/$($proj.id)/rede/rotear" -Headers $h -ContentType 'application/json' -Body '{}' | Out-Null
    $calc = Invoke-RestMethod -Method Post "$Url/api/projetos/$($proj.id)/calcular" -Headers $h -ContentType 'application/json' -Body '{}'
    Confere ($calc.resultados.vazao_total_m3h -gt 0) "calculo executado ($([math]::Round($calc.resultados.vazao_total_m3h)) m3/h)"
    $dxf = Invoke-WebRequest "$Url/api/calculos/$($calc.id)/dxf" -Headers $h -UseBasicParsing
    Confere ($dxf.RawContentLength -gt 1000) 'DXF exportado'
    Invoke-RestMethod -Method Post "$Url/api/clientes" -Headers $h -ContentType 'application/json' -Body '{"nome":"Cliente criado antes da atualizacao"}' | Out-Null

    # 3. atualizacao para uma "versao nova" (mesmo pacote com outra identificacao)
    $t = Join-Path $out 'v2'; Expand-Archive (Join-Path $out 'LKI-INDUSTRIAL-windows.zip') $t -Force
    $vj = Get-Content (Join-Path $t 'versao.json') -Raw | ConvertFrom-Json; $vj.sha = 'b' * 40; ($vj | ConvertTo-Json) | Set-Content (Join-Path $t 'versao.json') -Encoding utf8
    $z2 = Join-Path $out 'v2.zip'; Compress-Archive (Join-Path $t '*') $z2 -Force
    $m2 = [ordered]@{ versao = $vj.versao; sha = $vj.sha; arquivo = 'v2.zip'; sha256 = (Get-FileHash $z2).Hash.ToLower(); tamanho = (Get-Item $z2).Length }
    ($m2 | ConvertTo-Json) | Set-Content (Join-Path $out 'm2.json') -Encoding utf8
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ferr 'atualizar.ps1') -Silencioso -Pacote $z2 -Manifesto (Join-Path $out 'm2.json')
    Confere ($LASTEXITCODE -eq 0) 'atualizacao concluida'
    Confere ((Invoke-RestMethod "$Url/api/versao").git_sha -eq ('b' * 12)) 'versao nova em uso'
    $h = @{ Authorization = 'Bearer ' + (Login) }
    Confere (((Invoke-RestMethod "$Url/api/clientes" -Headers $h) | Where-Object { $_.nome -eq 'Cliente criado antes da atualizacao' })) 'dados preservados na atualizacao'

    # 4. versao defeituosa: deve voltar sozinho para a anterior
    $t3 = Join-Path $out 'v3'; Expand-Archive $z2 $t3 -Force
    Remove-Item (Join-Path $t3 'backend\app\main.py')
    $vj.sha = 'c' * 40; ($vj | ConvertTo-Json) | Set-Content (Join-Path $t3 'versao.json') -Encoding utf8
    $z3 = Join-Path $out 'v3.zip'; Compress-Archive (Join-Path $t3 '*') $z3 -Force
    $m3 = [ordered]@{ versao = $vj.versao; sha = $vj.sha; arquivo = 'v3.zip'; sha256 = (Get-FileHash $z3).Hash.ToLower(); tamanho = (Get-Item $z3).Length }
    ($m3 | ConvertTo-Json) | Set-Content (Join-Path $out 'm3.json') -Encoding utf8
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ferr 'atualizar.ps1') -Silencioso -Pacote $z3 -Manifesto (Join-Path $out 'm3.json')
    Confere ($LASTEXITCODE -eq 2) 'versao defeituosa detectada e revertida'
    Confere ((Invoke-RestMethod "$Url/api/versao").git_sha -eq ('b' * 12)) 'sistema de volta na versao anterior'

    # 5. pacote adulterado: nada pode ser trocado
    ($m3 | ForEach-Object { $_.sha256 = '0' * 64; $_ } | ConvertTo-Json) | Set-Content (Join-Path $out 'm4.json') -Encoding utf8
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ferr 'atualizar.ps1') -Silencioso -Pacote $z3 -Manifesto (Join-Path $out 'm4.json')
    Confere ($LASTEXITCODE -eq 1) 'pacote com impressao digital errada recusado'
    Confere ((Invoke-RestMethod "$Url/api/saude").status -eq 'ok') 'sistema intacto apos recusa'

    # 6. fechar e abrir pelos atalhos
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ferr 'fechar.ps1')
    $fora = $false; try { Invoke-RestMethod "$Url/api/saude" -TimeoutSec 3 | Out-Null } catch { $fora = $true }
    Confere $fora 'FECHAR desligou o sistema'
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ferr 'abrir.ps1') -SemNavegador
    Confere ((Invoke-RestMethod "$Url/api/saude").status -eq 'ok') 'LKI INDUSTRIAL abriu de novo'
    Confere (@(Get-ChildItem (Join-Path $env:LOCALAPPDATA 'LkiIndustrial\dados\backups') -Filter '*.sqlite').Count -ge 1) 'backups do banco gerados'
    Write-Host 'TODOS OS TESTES DO PACOTE WINDOWS PASSARAM' -ForegroundColor Green
} catch {
    Write-Host $_ -ForegroundColor Red
    Mostrar-Logs
    exit 1
}
