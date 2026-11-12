# 用 PyInstaller 生成 dist\SteamBoardClip\SteamBoardClip.exe
# 用法：.\build.ps1                          使用 PATH 里的 python
#       .\build.ps1 -Python C:\path\python.exe
param([string]$Python = "python")

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

& $Python tools\make_icon.py
if ($LASTEXITCODE -ne 0) { throw "图标生成失败" }

& $Python -m PyInstaller --noconfirm --clean --windowed `
    --name SteamBoardClip `
    --icon assets\icon.ico `
    --add-data "assets;assets" `
    --collect-all imgui_bundle `
    --collect-all imageio_ffmpeg `
    --collect-data selenium `
    --copy-metadata imageio `
    --copy-metadata moviepy `
    --exclude-module PyQt5 `
    --exclude-module tkinter `
    --exclude-module matplotlib `
    --exclude-module pytest `
    SteamBoardClip.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 失败" }

Write-Output "已生成: $PSScriptRoot\dist\SteamBoardClip\SteamBoardClip.exe"
