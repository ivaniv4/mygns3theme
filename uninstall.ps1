# Removes the mygns3theme "Violet" style and restores the original GNS3 files.
# Usage: powershell -ExecutionPolicy Bypass -File uninstall.ps1
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
if ($LASTEXITCODE -ne 0) { throw "Python 3.13 is required: winget install Python.Python.3.13" }
if (Get-Process gns3 -ErrorAction SilentlyContinue) { throw "Close GNS3 before uninstalling the theme." }

# switch the style first so GNS3 never starts on a style it no longer knows
& $python $tool reset-style
Invoke-Elevated $python "`"$tool`" unpatch"
& $python $tool status
