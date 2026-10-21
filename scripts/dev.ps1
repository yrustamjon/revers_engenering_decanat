[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
$viteScript = Join-Path $repoRoot 'frontend\node_modules\vite\bin\vite.js'
$services = @()

function Assert-PortAvailable {
    param([int]$Port)
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, $Port)
    $listener.ExclusiveAddressUse = $true
    try {
        $listener.Start()
    } catch {
        throw "Port $Port is unavailable. Stop the process using it before starting UniFlow."
    } finally {
        $listener.Stop()
    }
}

if (!(Test-Path $venvPython) -or !(Test-Path $viteScript)) {
    throw 'Install dependencies first: .\scripts\setup.ps1 -Demo'
}
$node = (Get-Command node.exe -ErrorAction Stop).Source
# Check both ports before starting either service. Vite also refuses port fallback.
Assert-PortAvailable 8000
Assert-PortAvailable 5173

Push-Location $repoRoot
try {
    $services += Start-Process -FilePath $venvPython -ArgumentList @('backend/manage.py', 'runserver', '127.0.0.1:8000', '--noreload') -WorkingDirectory $repoRoot -NoNewWindow -PassThru
    # Starting Node directly lets cleanup own the Vite process, without npm/cmd wrappers.
    $services += Start-Process -FilePath $node -ArgumentList @('frontend/node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5173', '--strictPort') -WorkingDirectory $repoRoot -NoNewWindow -PassThru
    Write-Host 'UniFlow frontend: http://127.0.0.1:5173. Backend: http://127.0.0.1:8000.'
    Write-Host 'Keep this terminal open. Ctrl+C stops both services.'
    while ($true) {
        foreach ($service in $services) {
            $service.Refresh()
            if ($service.HasExited) {
                throw "A development service stopped (exit $($service.ExitCode)). See its output above."
            }
        }
        Start-Sleep -Milliseconds 250
    }
} finally {
    foreach ($service in $services) {
        try {
            $service.Refresh()
            if (!$service.HasExited) {
                # Scope termination to the process started here and its descendants.
                & taskkill.exe /PID $service.Id /T /F 2>$null | Out-Null
            }
        } catch {
            Write-Warning "Could not confirm cleanup of development process $($service.Id)."
        } finally {
            $service.Dispose()
        }
    }
    Pop-Location
}
