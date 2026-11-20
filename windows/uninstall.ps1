<#
.SYNOPSIS
    Removes mygns3theme: switches GNS3 back to the Classic style, restores the
    original GNS3 files (UAC prompt) and deletes the theme files.

.PARAMETER Gns3Dir
    GNS3 install folder (default: C:\Program Files\GNS3).

.PARAMETER Yes
    Close GNS3 without asking.
#>
param(
    [string]$Gns3Dir,
    [switch]$Yes
)
$ErrorActionPreference = "Stop"

$root = if (Test-Path (Join-Path $PSScriptRoot "mygns3theme.py")) { $PSScriptRoot } else { Split-Path $PSScriptRoot -Parent }
$tool = Join-Path $root "mygns3theme.py"

function Write-Step($message) { Write-Host "==> $message" -ForegroundColor Magenta }

function Invoke-Tool([string[]]$arguments) {
    & $script:python $tool @arguments
    if ($LASTEXITCODE -ne 0) { throw "mygns3theme $($arguments -join ' ') failed" }
}

function Invoke-ToolElevated([string[]]$arguments) {
    $log = Join-Path $env:TEMP "mygns3theme-elevated.log"
    Remove-Item $log -ErrorAction SilentlyContinue
    $quoted = ($arguments | ForEach-Object { "`"$_`"" }) -join " "
    $command = "/s /c `"`"$script:python`" `"$tool`" $quoted > `"$log`" 2>&1`""
    $process = Start-Process cmd.exe -ArgumentList $command -Verb RunAs -Wait -PassThru -WindowStyle Hidden
    if (Test-Path $log) { Get-Content $log | ForEach-Object { Write-Host "    $_" } }
    if ($process.ExitCode -ne 0) { throw "mygns3theme $($arguments -join ' ') failed (exit $($process.ExitCode))" }
}

# restoring files works with any Python 3.10+
$python = $null
foreach ($candidate in @("-3.13", "-3")) {
    try {
        $exe = & py $candidate -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) { $python = $exe.Trim(); break }
    } catch { }
}
if (-not $python) { throw "Python 3 is required (py launcher not found)." }

$gns3Args = @()
if ($Gns3Dir) { $gns3Args = @("--gns3-dir", $Gns3Dir) }

if (Get-Process gns3 -ErrorAction SilentlyContinue) {
    $answer = if ($Yes) { "y" } else { Read-Host "GNS3 is running. Close it now? [Y/n]" }
    if ($answer -ne "" -and $answer -notmatch "^[yYoO]") { throw "Close GNS3 and run this script again." }
    Write-Host "    Answer 'Yes' if GNS3 asks to confirm the exit"
    Get-Process gns3 -ErrorAction SilentlyContinue | ForEach-Object { $null = $_.CloseMainWindow(); $null = $_.WaitForExit(60000) }
    if (Get-Process gns3 -ErrorAction SilentlyContinue) { throw "GNS3 is still running. Close it and run this script again." }
}

Write-Step "Switching GNS3 back to the Classic style"
Invoke-Tool ($gns3Args + "reset-style")

Write-Step "Restoring the original GNS3 files"
$detected = & $python $tool @gns3Args detect --json | ConvertFrom-Json
if ($detected.writable) { Invoke-Tool ($gns3Args + "unpatch") }
else { Invoke-ToolElevated (@("--gns3-dir", $detected.path) + "unpatch") }

Write-Step "Removing the theme files"
Invoke-Tool ($gns3Args + "remove-themes")
Write-Host "    mygns3theme removed." -ForegroundColor Green
