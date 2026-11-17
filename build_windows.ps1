$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if ($env:OS -ne 'Windows_NT') { throw '请在 Windows 10/11 x64 上打包。' }
py -3.11 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw '请先在构建电脑安装 Python 3.11 x64（最终用户不需要）。' }
& .\.venv\Scripts\python.exe -m pip install -r requirements-windows.lock.txt
if ($LASTEXITCODE -ne 0) { throw '依赖安装失败。' }
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw '自动检查失败。' }
& .\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm LiaoShen.spec
if ($LASTEXITCODE -ne 0) { throw '打包失败。' }
Write-Host '输出：dist\LiaoShen.exe。请在 Windows 真机验收后分发。'
Get-FileHash .\dist\LiaoShen.exe -Algorithm SHA256
