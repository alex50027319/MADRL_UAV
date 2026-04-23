param(
    [ValidateSet("COMA", "DeepQ")]
    [string]$Algorithm = "COMA",
    [switch]$Quick,
    [switch]$FastCompare
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if (-not (Test-Path ".venv")) {
    uv venv --python 3.10 .venv
}

uv pip install --python .venv -r "requirements-windows.txt"

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logDir = Join-Path $projectRoot ("marl_framework\logs\{0}\{1}" -f $Algorithm, $timestamp)
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$env:MISSION_TYPE_OVERRIDE = $Algorithm
$env:LOG_DIR = $logDir
$env:PYTHONPATH = $projectRoot

if ($Quick) {
    # Quick mode for validating pipelines and generating comparison plots fast.
    $env:N_EPISODES_OVERRIDE = "4"
    $env:BATCH_SIZE_OVERRIDE = "20"
    $env:BATCH_NUMBER_OVERRIDE = "1"
    $env:DATA_PASSES_OVERRIDE = "1"
} elseif ($FastCompare) {
    # FastCompare mode keeps runtime manageable while producing line-like curves.
    $env:N_EPISODES_OVERRIDE = "80"
    $env:BATCH_SIZE_OVERRIDE = "20"
    $env:BATCH_NUMBER_OVERRIDE = "1"
    $env:DATA_PASSES_OVERRIDE = "1"
} else {
    Remove-Item Env:N_EPISODES_OVERRIDE -ErrorAction SilentlyContinue
    Remove-Item Env:BATCH_SIZE_OVERRIDE -ErrorAction SilentlyContinue
    Remove-Item Env:BATCH_NUMBER_OVERRIDE -ErrorAction SilentlyContinue
    Remove-Item Env:DATA_PASSES_OVERRIDE -ErrorAction SilentlyContinue
}

Write-Host ("[run_windows] Algorithm: {0}" -f $Algorithm)
Write-Host ("[run_windows] Log dir:   {0}" -f $logDir)
Write-Host ("[run_windows] Quick mode: {0}" -f $Quick.IsPresent)
Write-Host ("[run_windows] FastCompare mode: {0}" -f $FastCompare.IsPresent)

Set-Location (Join-Path $projectRoot "marl_framework")

& "..\.venv\Scripts\python" "main.py"
