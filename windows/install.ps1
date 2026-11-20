<#
.SYNOPSIS
    Installs mygns3theme into GNS3 for Windows, end to end.

.DESCRIPTION
    Finds GNS3, installs the Python version GNS3 was built with if it is missing
    (winget), closes GNS3 if needed, patches it (UAC prompt), installs every theme
    and selects the one you pick.

.PARAMETER Theme
    Theme id or name, e.g. deeppurple-amber or "Azure & Blue". Asked when omitted.

.PARAMETER Gns3Dir
    GNS3 install folder (default: C:\Program Files\GNS3).

.PARAMETER Yes
    Answer yes to every question (close GNS3, install Python, start GNS3).

.EXAMPLE
    .\install.ps1
    .\install.ps1 -Theme "Azure & Blue" -Yes
#>
param(
    [string]$Theme,
    [string]$Gns3Dir,
    [switch]$Yes
)
$ErrorActionPreference = "Stop"

# the scripts sit next to mygns3theme.py in a release, in windows\ in the repository
$root = if (Test-Path (Join-Path $PSScriptRoot "mygns3theme.py")) { $PSScriptRoot } else { Split-Path $PSScriptRoot -Parent }
$tool = Join-Path $root "mygns3theme.py"

function Write-Step($message) { Write-Host "==> $message" -ForegroundColor Magenta }
function Write-Done($message) { Write-Host "    $message" -ForegroundColor Green }

function Confirm-Action($question) {
    if ($Yes) { return $true }
    $answer = Read-Host "$question [Y/n]"
    return ($answer -eq "" -or $answer -match "^[yYoO]")
}

function Get-LibraryZip {
    $folders = @()
    if ($Gns3Dir) { $folders += $Gns3Dir }
    $folders += "$env:ProgramW6432\GNS3", "$env:ProgramFiles\GNS3"
    foreach ($folder in $folders) {
        foreach ($candidate in @((Join-Path $folder "lib\library.zip"), (Join-Path $folder "library.zip"), $folder)) {
            if ((Test-Path $candidate -PathType Leaf) -and $candidate -like "*.zip") { return $candidate }
        }
    }
    throw "GNS3 was not found. Install GNS3 or pass -Gns3Dir."
}

function Get-Gns3PythonVersion($libraryZip) {
    # the .pyc magic number tells which Python built GNS3
    $magics = @{ 3413 = "3.8"; 3425 = "3.9"; 3439 = "3.10"; 3495 = "3.11"; 3531 = "3.12"; 3571 = "3.13" }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($libraryZip)
    try {
        $stream = $zip.GetEntry("gns3/settings.pyc").Open()
        $bytes = New-Object byte[] 2
        $null = $stream.Read($bytes, 0, 2)
        $stream.Close()
    } finally { $zip.Dispose() }
    $magic = [BitConverter]::ToUInt16($bytes, 0)
    if (-not $magics.ContainsKey([int]$magic)) { throw "Unsupported GNS3 build (Python magic $magic)." }
    return $magics[[int]$magic]
}

function Get-Python($version) {
    try {
        $exe = & py "-$version" -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
    } catch { }
    return $null
}

function Invoke-Tool([string[]]$arguments) {
    & $script:python $tool @arguments
    if ($LASTEXITCODE -ne 0) { throw "mygns3theme $($arguments -join ' ') failed" }
}

function Invoke-ToolElevated([string[]]$arguments) {
    # UAC-elevated run, output captured in a log file and shown here
    $log = Join-Path $env:TEMP "mygns3theme-elevated.log"
    Remove-Item $log -ErrorAction SilentlyContinue
    $quoted = ($arguments | ForEach-Object { "`"$_`"" }) -join " "
    $command = "/s /c `"`"$script:python`" `"$tool`" $quoted > `"$log`" 2>&1`""
    $process = Start-Process cmd.exe -ArgumentList $command -Verb RunAs -Wait -PassThru -WindowStyle Hidden
    if (Test-Path $log) { Get-Content $log | ForEach-Object { Write-Host "    $_" } }
    if ($process.ExitCode -ne 0) { throw "mygns3theme $($arguments -join ' ') failed (exit $($process.ExitCode))" }
}

Write-Host ""
Write-Host "  mygns3theme - Material 3 themes for GNS3" -ForegroundColor Magenta
Write-Host ""

# 1. GNS3 and the matching Python
Write-Step "Looking for GNS3"
$libraryZip = Get-LibraryZip
$pythonVersion = Get-Gns3PythonVersion $libraryZip
Write-Done "$libraryZip (built with Python $pythonVersion)"

Write-Step "Looking for Python $pythonVersion"
$python = Get-Python $pythonVersion
if (-not $python) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Python $pythonVersion is required: install it from https://www.python.org/downloads/ and run this script again."
    }
    if (-not (Confirm-Action "Python $pythonVersion is required. Install it now with winget?")) { throw "Python $pythonVersion is required." }
    winget install --id "Python.Python.$pythonVersion" --scope user --silent --accept-package-agreements --accept-source-agreements
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    $python = Get-Python $pythonVersion
    if (-not $python) { throw "Python $pythonVersion was installed but cannot be found. Open a new terminal and run this script again." }
}
Write-Done $python

$gns3Args = @()
if ($Gns3Dir) { $gns3Args = @("--gns3-dir", $libraryZip) }
$detected = & $python $tool @gns3Args detect --json | ConvertFrom-Json
if (-not $detected) { throw "GNS3 detection failed." }

# 2. GNS3 must be closed
if ($detected.running) {
    Write-Step "GNS3 is running"
    if (-not (Confirm-Action "Close GNS3 now? (projects are saved on the server)")) { throw "Close GNS3 and run this script again." }
    Write-Done "Answer 'Yes' if GNS3 asks to confirm the exit"
    Get-Process gns3 -ErrorAction SilentlyContinue | ForEach-Object { $null = $_.CloseMainWindow(); $null = $_.WaitForExit(60000) }
    if (Get-Process gns3 -ErrorAction SilentlyContinue) { throw "GNS3 is still running (a dialog may be waiting). Close it and run this script again." }
    Write-Done "GNS3 closed"
}

# 3. Theme choice
$themes = & $python $tool list --json | ConvertFrom-Json
if (-not $Theme) {
    Write-Step "Choose a theme"
    for ($i = 0; $i -lt $themes.Count; $i++) {
        Write-Host ("    {0,2}. {1,-22} {2}" -f ($i + 1), $themes[$i].name, $themes[$i].mode)
    }
    $choice = Read-Host "    Theme number [1]"
    if ($choice -eq "") { $choice = 1 }
    $index = [int]$choice - 1
    if ($index -lt 0 -or $index -ge $themes.Count) { throw "Invalid choice: $choice" }
    $Theme = $themes[$index].id
}

# 4. Patch GNS3 (Program Files needs an elevated prompt)
Write-Step "Adding theme support to GNS3"
if ($detected.writable) { Invoke-Tool ($gns3Args + "patch") }
else {
    Write-Done "Administrator rights are needed: accept the UAC prompt"
    Invoke-ToolElevated (@("--gns3-dir", $detected.path) + "patch")
}

# 5. Themes
Write-Step "Installing the themes"
Invoke-Tool ($gns3Args + @("apply", "--theme", $Theme))

Write-Step "Done"
Invoke-Tool ($gns3Args + "status")
Write-Host ""
Write-Host "    Switch theme any time: Edit > Preferences > General > Interface style" -ForegroundColor Green
Write-Host ""

if ($detected.launcher -and (Confirm-Action "Start GNS3 now?")) { Start-Process $detected.launcher }
