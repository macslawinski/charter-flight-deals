# Ship curated hotel data: validate, export, checks, build, load into Supabase, commit, push.
# Usage (any cwd): powershell -File .claude/skills/curate-hotel/scripts/ship.ps1 -Branch feat/x -Message "..."
# Stops at the first failing step; prints one line per step. Opening and merging the PR stays a
# separate step (GitHub connector), as does the Vercel preview link.
param(
    [Parameter(Mandatory = $true)][string]$Branch,
    [Parameter(Mandatory = $true)][string]$Message,
    [switch]$NoLoad  # skip the Supabase upsert (e.g. no .env)
)
# Not 'Stop': in Windows PowerShell 5.1 a native command writing to stderr (Python logging) would then
# throw; each step checks $LASTEXITCODE instead.
$ErrorActionPreference = 'Continue'
$repo = (Resolve-Path "$PSScriptRoot\..\..\..\..").Path
Set-Location $repo
$py = "$repo\.venv\Scripts\python.exe"

function Step([string]$name, [scriptblock]$cmd) {
    $out = & $cmd 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) {
        Write-Output "FAIL $name"
        $out | Select-Object -Last 30
        exit 1
    }
    Write-Output ("ok   {0}: {1}" -f $name, ($out | Select-Object -Last 1))
}

Step 'validate' { & $py -m ingest.curated --dry-run }
Step 'export' { & $py scripts/export_family.py }
Step 'ruff' { & "$repo\.venv\Scripts\ruff.exe" check . }
Step 'pyright' { pyright }
Step 'pytest' { & $py -m pytest -q -p no:cacheprovider }
Step 'build' { Push-Location family; try { npm run build } finally { Pop-Location } }
if (-not $NoLoad) { Step 'supabase' { & $py -m ingest.curated } }

$current = git rev-parse --abbrev-ref HEAD
if ($current -ne $Branch) {
    git checkout -q -b $Branch
    if ($LASTEXITCODE -ne 0) { Write-Output "FAIL branch $Branch"; exit 1 }
}
git add ROADMAP.md data/curated family/src/data/family.json
git diff --cached --quiet
if ($LASTEXITCODE -eq 0) { Write-Output 'FAIL commit: nothing staged (no data changes?)'; exit 1 }
git commit -q -m $Message
if ($LASTEXITCODE -ne 0) { Write-Output 'FAIL commit'; exit 1 }
git push -q -u origin $Branch 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Output 'FAIL push'; exit 1 }
Write-Output "ok   pushed $Branch"
