<#
.SYNOPSIS
Wrapper to run LocalScript CLI on Windows PowerShell
#>
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
try {
    python -c "import httpx" 2>$null
} catch {
    Write-Host "Installing required package 'httpx'..."
    pip install httpx
}
python chat.py
