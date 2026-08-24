<#
.SYNOPSIS
    Build the PlanBench desktop installer for Windows.

.DESCRIPTION
    Assembles build\stage\ — an embedded interpreter, its site-packages,
    the source tree with its directories intact, and the exported web UI
    — proves the result actually works, and only then builds setup.exe.

    The order matters in one place above all: the smoke gate runs
    *between* assembling the stage and packaging it. Every mechanism the
    packaging introduces (a path file instead of PYTHONPATH, an
    interpreter that is not the one the tests ran on, a source tree
    copied rather than checked out) is invisible to the test suite, and
    the gate is the only thing that looks at them. A stage that fails it
    is not packaged.

    Requirements on the build machine:
      * CPython 3.12 on PATH as `py -3.12` — the SAME minor version as
        the shipped interpreter, because pip installs C extensions for
        the version it is running.
      * Node 20+ for the web export.
      * Inno Setup 6 (`iscc`) for the installer, unless -SkipInstaller.

.PARAMETER SkipWeb
    Reuse an existing build\stage\web instead of running next build.

.PARAMETER SkipInstaller
    Stop after the smoke gate. Leaves a runnable stage behind.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\build_desktop.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipWeb,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BuildDir = Join-Path $RepoRoot 'build'
$Stage    = Join-Path $BuildDir 'stage'
$Cache    = Join-Path $BuildDir 'cache'
$DistDir  = Join-Path $RepoRoot 'dist'

function Write-Step([string]$Message) {
    Write-Host ''
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-AppVersion {
    $stamp = Join-Path $RepoRoot 'apps\desktop\planbench_desktop\VERSION'
    if (-not (Test-Path $stamp)) { throw "missing version stamp: $stamp" }
    (Get-Content $stamp -Raw).Trim()
}

# ---------------------------------------------------------------- stage
Write-Step 'Preparing the stage'
if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Stage, $Cache, $DistDir | Out-Null
$Version = Get-AppVersion
Write-Host "   version $Version"

# ------------------------------------------------------------------ web
$StageWeb = Join-Path $Stage 'web'
if ($SkipWeb) {
    Write-Step 'Skipping the web export (-SkipWeb)'
} else {
    Write-Step 'Exporting the web UI'
    Push-Location (Join-Path $RepoRoot 'apps\web')
    try {
        if (-not (Test-Path 'node_modules')) { npm ci }
        # `export`, not `standalone`: the desktop build has no Node
        # runtime to serve from, and the API serves the files instead.
        $env:PLANBENCH_DESKTOP = '1'
        npx next build
        if ($LASTEXITCODE -ne 0) { throw 'next build failed' }
        if (-not (Test-Path 'out\index.html')) { throw 'next build produced no out\index.html' }
        Copy-Item 'out' $StageWeb -Recurse
    } finally {
        Remove-Item Env:\PLANBENCH_DESKTOP -ErrorAction SilentlyContinue
        Pop-Location
    }
    foreach ($shell in 'decisions\_.html', 'maps\_.html', 'scenarios\_.html') {
        if (-not (Test-Path (Join-Path $StageWeb $shell))) {
            throw "the export is missing $shell; a deep link into that route would 404 on reload"
        }
    }
}

# -------------------------------------------------------------- runtime
Write-Step 'Fetching the embedded interpreter'
$EmbedSpec = Get-Content (Join-Path $RepoRoot 'installer\python-embed.json') -Raw | ConvertFrom-Json
$Archive = Join-Path $Cache ("python-{0}-embed-amd64.zip" -f $EmbedSpec.version)
if (-not (Test-Path $Archive)) {
    Write-Host "   downloading $($EmbedSpec.url)"
    Invoke-WebRequest -Uri $EmbedSpec.url -OutFile $Archive
}
$Actual = (Get-FileHash $Archive -Algorithm SHA256).Hash.ToLower()
if ([string]::IsNullOrWhiteSpace($EmbedSpec.sha256)) {
    Write-Host ''
    Write-Host "The interpreter is not pinned yet. This archive hashes to:" -ForegroundColor Yellow
    Write-Host "  $Actual" -ForegroundColor Yellow
    Write-Host "Check it against the sha256 published beside the file at"
    Write-Host "  https://www.python.org/downloads/windows/"
    Write-Host "and put it in installer\python-embed.json before building a release."
    throw 'installer\python-embed.json has no sha256; refusing to ship an unpinned interpreter'
}
if ($Actual -ne $EmbedSpec.sha256.ToLower()) {
    throw "interpreter hash mismatch: expected $($EmbedSpec.sha256), got $Actual"
}
$Runtime = Join-Path $Stage 'runtime'
Expand-Archive -Path $Archive -DestinationPath $Runtime

# ---------------------------------------------------------------- source
Write-Step 'Copying the source tree'
$App = Join-Path $Stage 'app'
New-Item -ItemType Directory -Force -Path $App | Out-Null

# Directories, copied with their structure intact. `contracts/` has to
# stay exactly three levels above `packages/decision/planbench_decision/`
# — `anchors.py` resolves the metric anchors by walking up from its own
# file, and flattening the tree would break it at the first decision run.
$SourceDirs = @(
    'packages', 'services', 'ml',
    'apps\api', 'apps\desktop',
    'alembic', 'contracts', 'configs', 'maps', 'profiles',
    'scripts\desktop',
    # Sample bundles, so the algorithm import feature has something to
    # try on a machine that has never seen a plugin. Also what the smoke
    # gate drives the subprocess lane with.
    'examples\plugins'
)
$Excluded = @('__pycache__', '.pytest_cache', 'node_modules', '.git')
foreach ($dir in $SourceDirs) {
    $source = Join-Path $RepoRoot $dir
    if (-not (Test-Path $source)) { throw "missing source directory: $dir" }
    $target = Join-Path $App $dir
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
    # /XD excludes directories, /XF files. Robocopy exit codes below 8
    # mean success; PowerShell would otherwise read 1 ("files copied")
    # as a failure.
    robocopy $source $target /E /NFL /NDL /NJH /NJS /NP `
        /XD $Excluded /XF '*.pyc' '*.pyo' | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed for $dir (exit $LASTEXITCODE)" }
}
# `pyproject.toml` is not documentation here: the launcher and the path
# generator both read the source-root list out of it at runtime.
Copy-Item (Join-Path $RepoRoot 'pyproject.toml') $App
Copy-Item (Join-Path $RepoRoot 'alembic.ini') $App
# At the stage root, not under app\: the shortcut points at it as
# {app}\planbench.ico, and [InstallDelete] wipes app\ on every upgrade.
Copy-Item (Join-Path $RepoRoot 'installer\planbench.ico') $Stage
$global:LASTEXITCODE = 0

# --------------------------------------------------------- dependencies
Write-Step 'Installing dependencies into the runtime'
$SitePackages = Join-Path $Runtime 'Lib\site-packages'
# --target rather than a virtualenv: the embedded interpreter reads its
# path from the ._pth written below, and a venv's pyvenv.cfg would be
# ignored entirely.
py -3.12 -m pip install --disable-pip-version-check --no-compile `
    --target $SitePackages -r (Join-Path $RepoRoot 'requirements.txt') pywebview
if ($LASTEXITCODE -ne 0) { throw 'pip install failed' }

Write-Step 'Writing the interpreter path files'
# Generated from pyproject rather than written here: a fourth
# hand-maintained copy of the source-root list is a fourth chance at the
# drift that already cost this project a green suite over an API that
# could not boot.
py -3.12 (Join-Path $RepoRoot 'scripts\desktop\make_runtime_paths.py') `
    $Runtime --python-tag $EmbedSpec.python_tag
if ($LASTEXITCODE -ne 0) { throw 'failed to write the runtime path files' }

# ------------------------------------------------------------ smoke gate
Write-Step 'Smoke testing the stage (release gate)'
$StagePython = Join-Path $Runtime 'python.exe'
& $StagePython (Join-Path $App 'scripts\desktop\smoke_stage.py')
if ($LASTEXITCODE -ne 0) {
    throw 'the staged build failed its smoke test; refusing to package it'
}

# ------------------------------------------------------------- installer
if ($SkipInstaller) {
    Write-Step 'Stopping before the installer (-SkipInstaller)'
    Write-Host "   stage ready at $Stage"
    exit 0
}

Write-Step 'Building the installer'
$Iscc = Get-Command 'iscc' -ErrorAction SilentlyContinue
if (-not $Iscc) {
    $fallback = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
    if (Test-Path $fallback) {
        $Iscc = $fallback
    } else {
        throw 'Inno Setup 6 (iscc) is not on PATH; install it or pass -SkipInstaller'
    }
}
& $Iscc "/DAppVersion=$Version" "/DStageDir=$Stage" "/DOutputDir=$DistDir" `
    (Join-Path $RepoRoot 'installer\planbench.iss')
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed' }

Write-Step 'Done'
Get-ChildItem $DistDir -Filter '*.exe' | ForEach-Object {
    Write-Host ("   {0}  ({1:N0} MB)" -f $_.Name, ($_.Length / 1MB))
}
