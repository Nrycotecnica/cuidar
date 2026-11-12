<# Monta o pacote do LKI INDUSTRIAL para Windows (roda no GitHub Actions, windows-latest).
   Requer: Python 3.13 no PATH (mesma versao do Python embutido) e frontend\dist ja compilado.
   Saida em .\saida: LKI-INDUSTRIAL-windows.zip, versao.json (manifesto), instalar.ps1 e o .cmd #>
param([string]$Saida = 'saida')
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$out = Join-Path $repo $Saida
Remove-Item $out -Recurse -Force -ErrorAction SilentlyContinue
$pk = Join-Path $out 'pacote'
New-Item -ItemType Directory -Force -Path $pk | Out-Null

# Python embutido da MESMA versao do Python usado para instalar as bibliotecas
$pyv = (python -c "import platform; print(platform.python_version())").Trim()
Write-Host "Python $pyv"
Invoke-WebRequest "https://www.python.org/ftp/python/$pyv/python-$pyv-embed-amd64.zip" -OutFile (Join-Path $out 'py.zip') -UseBasicParsing
Expand-Archive (Join-Path $out 'py.zip') (Join-Path $pk 'python')
$pth = Get-ChildItem (Join-Path $pk 'python') -Filter 'python*._pth' | Select-Object -First 1
$zipStd = (Get-ChildItem (Join-Path $pk 'python') -Filter 'python*.zip' | Select-Object -First 1).Name
# O ._pth define o sys.path do Python embutido: biblioteca padrao, bibliotecas
# instaladas e o codigo do sistema (..\backend).
Set-Content -Path $pth.FullName -Value @($zipStd, '.', 'Lib\site-packages', '..\backend', 'import site') -Encoding ascii
python -m pip install --disable-pip-version-check --no-cache-dir --target (Join-Path $pk 'python\Lib\site-packages') -r (Join-Path $repo 'backend\requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'pip falhou' }

# Sistema
New-Item -ItemType Directory -Force -Path (Join-Path $pk 'backend'), (Join-Path $pk 'frontend'), (Join-Path $pk 'ferramentas') | Out-Null
Copy-Item (Join-Path $repo 'backend\app') (Join-Path $pk 'backend\app') -Recurse
Copy-Item (Join-Path $repo 'backend\alembic') (Join-Path $pk 'backend\alembic') -Recurse
Copy-Item (Join-Path $repo 'backend\alembic.ini') (Join-Path $pk 'backend')
Copy-Item (Join-Path $repo 'VERSION') $pk
Copy-Item (Join-Path $repo 'frontend\dist') (Join-Path $pk 'frontend\dist') -Recurse
Get-ChildItem $pk -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
Copy-Item (Join-Path $PSScriptRoot 'lki.ico') $pk
foreach ($f in 'lki-comum.ps1', 'abrir.ps1', 'atualizar.ps1', 'fechar.ps1', 'desinstalar.ps1', 'liberar-rede.ps1') {
    Copy-Item (Join-Path $PSScriptRoot $f) (Join-Path $pk 'ferramentas')
}
$ver = (Get-Content (Join-Path $repo 'VERSION')).Trim()
$sha = if ($env:GITHUB_SHA) { $env:GITHUB_SHA } else { (git -C $repo rev-parse HEAD).Trim() }
$info = [ordered]@{ versao = $ver; sha = $sha; data = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') }
($info | ConvertTo-Json) | Set-Content (Join-Path $pk 'versao.json') -Encoding utf8

$zip = Join-Path $out 'LKI-INDUSTRIAL-windows.zip'
Compress-Archive -Path (Join-Path $pk '*') -DestinationPath $zip -CompressionLevel Optimal
$man = [ordered]@{ versao = $ver; sha = $sha; data = $info.data; arquivo = 'LKI-INDUSTRIAL-windows.zip'
                   sha256 = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower(); tamanho = (Get-Item $zip).Length }
($man | ConvertTo-Json) | Set-Content (Join-Path $out 'versao.json') -Encoding utf8
Copy-Item (Join-Path $PSScriptRoot 'instalar.ps1'), (Join-Path $PSScriptRoot 'INSTALAR-LKI-INDUSTRIAL.cmd') $out
Remove-Item (Join-Path $out 'py.zip')

# Instalador .exe (C# compilado pelo csc do .NET Framework 4 que ja vem no
# Windows), com o pacote, o manifesto e o instalar.ps1 embutidos.
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) { $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe' }
$exe = Join-Path $out 'LKI-INDUSTRIAL-Instalador.exe'
& $csc /nologo /target:winexe /optimize+ "/out:$exe" "/win32icon:$(Join-Path $PSScriptRoot 'lki.ico')" "/win32manifest:$(Join-Path $PSScriptRoot 'lki.manifest')" `
    /r:System.Windows.Forms.dll /r:System.Drawing.dll `
    "/resource:$zip,LKI-INDUSTRIAL-windows.zip" "/resource:$(Join-Path $out 'versao.json'),versao.json" "/resource:$(Join-Path $PSScriptRoot 'instalar.ps1'),instalar.ps1" `
    (Join-Path $PSScriptRoot 'LkiInstalador.cs')
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $exe)) { throw 'falha ao compilar o instalador .exe' }
Write-Host "Instalador: $exe ($([math]::Round((Get-Item $exe).Length / 1MB)) MB)"
Write-Host "Pacote: $zip ($([math]::Round($man.tamanho / 1MB)) MB)"
