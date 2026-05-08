# Cross-platform setup for Windows. Mac/Linux users: use setup.sh.
#
# Usage from the repo root:
#     powershell -ExecutionPolicy Bypass -File setup\setup.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RepoRoot

Write-Host "=== zero-to-llm local setup ==="
Write-Host "Repo root: $RepoRoot"

# 1. Find a Python >= 3.10
$Python = $null
$candidates = @("py -3.13", "py -3.12", "py -3.11", "py -3.10", "py -3", "python", "python3")
foreach ($cand in $candidates) {
    try {
        $argList = $cand -split ' '
        $exe = $argList[0]
        $opts = if ($argList.Count -gt 1) { $argList[1..($argList.Count-1)] } else { @() }
        $version = & $exe @opts -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $version) {
            $parts = $version.Split('.')
            $major = [int]$parts[0]; $minor = [int]$parts[1]
            if ($major -ge 3 -and $minor -ge 10) {
                $Python = $cand
                Write-Host "Found Python: $cand (version $version)"
                break
            }
        }
    } catch { }
}
if (-not $Python) {
    Write-Error "No Python >= 3.10 found. Install from https://www.python.org/downloads/"
    exit 1
}

# 2. Create venv
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtualenv at .venv\ ..."
    $argList = $Python -split ' '
    & $argList[0] @($argList[1..($argList.Count-1)] + @("-m", "venv", ".venv"))
} else {
    Write-Host "Reusing existing .venv\"
}

$venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$venvPip    = Join-Path $RepoRoot ".venv\Scripts\pip.exe"

# 3. Install local deps
Write-Host "Installing local deps ..."
& $venvPython -m pip install --quiet --upgrade pip
& $venvPip install --quiet -r "attendee\requirements_local.txt"

# 4. Copy config template if needed
$attendeeConfig = "attendee\config.py"
if (-not (Test-Path $attendeeConfig)) {
    Copy-Item "attendee\config.example.py" $attendeeConfig
    Write-Host "Created $attendeeConfig from the template."
}

# 5. Reminder
Write-Host ""
Write-Host "==============================================================="
Write-Host "  Setup complete."
Write-Host "==============================================================="
Write-Host ""
Write-Host "  Next steps:"
Write-Host "  1. Edit attendee\config.py and set:"
Write-Host "       - RUNPOD_API_KEY  (from https://www.runpod.io/console/user/settings)"
Write-Host "       - STORAGE_POD_URL (your workshop host gives you this)"
Write-Host "  2. Activate the venv:    .venv\Scripts\Activate.ps1"
Write-Host "  3. Verify your config:   python setup\verify.py"
Write-Host "  4. Launch the GPU pod:   python attendee\launch_pod.py"
Write-Host "                           (or open attendee\launch_pod.ipynb)"
Write-Host ""
