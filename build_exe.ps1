param([string]$Python = "python")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path "static/index.html")) { throw "Run this script from the Mahjong project folder." }
& $Python -m venv .venv-build
if ($LASTEXITCODE -ne 0) { throw "Cannot create build environment. Use Python 3.12 on Windows." }
$BuildPython = Join-Path $PSScriptRoot ".venv-build/Scripts/python.exe"
& $BuildPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $BuildPython -m pip install -r requirements-exe.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
& $BuildPython -m PyInstaller --noconfirm --clean --onefile --console --noupx --name RiichiMahjong --add-data "static:static" --collect-all uvicorn desktop_launcher.py
if ($LASTEXITCODE -ne 0) { throw "EXE build failed." }
Write-Host "Build complete: $PSScriptRoot\dist\RiichiMahjong.exe"
Write-Host "Double-click the EXE, keep its console open, and play in your browser."
