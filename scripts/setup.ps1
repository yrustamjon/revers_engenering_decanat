[CmdletBinding()]
param([switch]$Demo)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Program failed (exit $LASTEXITCODE)."
    }
}

Push-Location $repoRoot
try {
    # Use the Windows launcher when available; never depend on activating a venv.
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        $python = $launcher.Source
        $pythonArgs = @('-3')
    } else {
        $python = (Get-Command python.exe -ErrorAction Stop).Source
        $pythonArgs = @()
    }
    $npm = (Get-Command npm.cmd -ErrorAction Stop).Source
    $node = (Get-Command node.exe -ErrorAction Stop).Source
    # Avoid embedded quotes in native arguments: Windows PowerShell 5.1 uses
    # legacy argument passing. These calls work without activation or policy changes.
    Invoke-Checked $python ($pythonArgs + @('-c', 'import sys; assert sys.version_info >= (3, 12), sys.version'))
    $nodeVersion = & $node --version
    if ($LASTEXITCODE -ne 0 -or $nodeVersion -notmatch '^v(\d+)\.' -or [int]$Matches[1] -lt 22) {
        throw 'Node.js 22+ is required.'
    }

    Invoke-Checked $python ($pythonArgs + @('-m', 'venv', '.venv'))
    $venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
    Invoke-Checked $venvPython @('-m', 'pip', 'install', '--disable-pip-version-check', '--cache-dir', '.local/pip-cache', '-r', 'backend/requirements.txt')
    Invoke-Checked $npm @('ci', '--prefix', 'frontend', '--cache', '.local/npm-cache', '--no-audit', '--no-fund')
    Invoke-Checked $venvPython @('backend/manage.py', 'migrate', '--noinput')
    if ($Demo) {
        Invoke-Checked $venvPython @('backend/manage.py', 'seed_demo')
    }
    Invoke-Checked $npm @('run', 'build', '--prefix', 'frontend')
    Invoke-Checked $venvPython @('backend/manage.py', 'check')
    Write-Host 'UniFlow setup complete. Start with: .\scripts\dev.ps1'
} finally {
    Pop-Location
}
