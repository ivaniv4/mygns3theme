# Installs the mygns3theme "Violet" style into GNS3 (Windows).
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1
$ErrorActionPreference = "Stop"

function Invoke-Elevated($python, $arguments) {
    # UAC-elevated run of mygns3theme.py, output captured in a log file
    $log = Join-Path $env:TEMP "mygns3theme-elevated.log"
    Remove-Item $log -ErrorAction SilentlyContinue
    $cmd = "/s /c `"`"$python`" $arguments > `"$log`" 2>&1`""
    $proc = Start-Process cmd.exe -ArgumentList $cmd -Verb RunAs -Wait -PassThru -WindowStyle Hidden
    if (Test-Path $log) { Get-Content $log }
    if ($proc.ExitCode -ne 0) { throw "mygns3theme $arguments failed (exit $($proc.ExitCode))" }
}

$tool = Join-Path $PSScriptRoot "mygns3theme.py"
$python = & py -3.13 -c "import sys; print(sys.executable)"
if ($LASTEXITCODE -ne 0) { throw "Python 3.13 is required (same version as GNS3 3.1): winget install Python.Python.3.13" }
if (Get-Process gns3 -ErrorAction SilentlyContinue) { throw "Close GNS3 before installing the theme." }

Invoke-Elevated $python "`"$tool`" patch"
& $python $tool apply
if ($LASTEXITCODE -ne 0) { throw "mygns3theme apply failed" }
& $python $tool status
