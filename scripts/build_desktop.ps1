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

function Get-BuildPython {
    <#
      A CPython 3.12 to run pip with — the SAME minor version the
      installer ships, because pip builds C extensions for the
      interpreter it runs on and a 3.13 here produces a numpy the
      shipped 3.12 cannot import.

      `py -3.12` is tried first and is not enough on its own: an
      interpreter installed by `uv` is not registered with the py
      launcher, so a machine that plainly has 3.12 answers "No suitable
      Python runtime found". Hence the two fallbacks — the launcher's
      own inventory, then uv's standard location.
    #>
    $probe = 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'

    # `$ErrorActionPreference = 'Stop'` at the top of this script turns
    # anything a native command writes to stderr into a terminating
    # error — and probing for an interpreter that may not exist is
    # exactly the case where writing to stderr is the correct answer.
    # So the probes run with it relaxed, and it is put back either way.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & py -3.12 -c $probe 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { return @('py', '-3.12') }

        $listed = (& py -0p 2>&1) -join "`n"
        foreach ($line in $listed -split "`n") {
            # `py -0p` prints "<tag><spaces><full path to python.exe>".
            # Anchored on a drive letter rather than on "the last word":
            # the active entry is marked with a leading `*`, which a
            # looser pattern swallows into the path and then executes.
            if ($line -match '(?<path>[A-Za-z]:\\S.*python\.exe)\s*$') {
                $candidate = $Matches['path'].Trim()
                if (-not (Test-Path -LiteralPath $candidate)) { continue }
                & $candidate -c $probe 2>&1 | Out-Null
                if ($LASTEXITCODE -eq 0) { return @($candidate) }
            }
        }

        # uv installs interpreters the py launcher never learns about,
        # so a machine that plainly has 3.12 can still answer "no
        # suitable Python runtime found" to everything above.
        $uv = Join-Path $env:APPDATA 'uv\python'
        if (Test-Path $uv) {
            foreach ($dir in Get-ChildItem $uv -Filter 'cpython-3.12.*' -Directory -ErrorAction SilentlyContinue) {
                $candidate = Join-Path $dir.FullName 'python.exe'
                if (-not (Test-Path -LiteralPath $candidate)) { continue }
                & $candidate -c $probe 2>&1 | Out-Null
                if ($LASTEXITCODE -eq 0) { return @($candidate) }
            }
        }
    } finally {
        $ErrorActionPreference = $previous
    }

    throw 'no CPython 3.12 found. Install one (python.org, winget, or `uv python install 3.12`) — it must be 3.12 exactly, not 3.11 or 3.13.'
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
# `@(...)` because PowerShell unwraps a one-element array into a scalar
# on return, and under StrictMode a scalar has no .Count. Splitting the
# executable from its arguments here also avoids `1..0`, which is a
# *descending* range rather than an empty one.
$BuildPython = @(Get-BuildPython)
$PyExe = $BuildPython[0]
$PyArgs = @()
if ($BuildPython.Count -gt 1) { $PyArgs = $BuildPython[1..($BuildPython.Count - 1)] }
Write-Host "   version $Version"
Write-Host "   build python: $($BuildPython -join ' ')"

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
# The commit this build was made from, stamped beside VERSION.
# An installation has no `.git`, and the decision layer refuses to write
# a card whose manifest cannot name the code that produced it — rightly.
# Stamping keeps that guarantee instead of weakening it.
$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $commit = ((& git -C $RepoRoot rev-parse HEAD 2>&1) -join "`n").Trim()
} finally {
    $ErrorActionPreference = $previous
}
# The value is the whole test. `$LASTEXITCODE` was in this condition and
# was wrong twice over: it still held robocopy's result from the block
# above — robocopy answers 1 for "files were copied" — and piping git
# through `Select-Object -First 1` ends the pipeline before the exit
# code lands. Forty hex characters is proof the command worked; an exit
# code that can be somebody else's is not.
if ($commit -notmatch '^[0-9a-f]{40}$') {
    throw "cannot read the commit to stamp into the build (got '$commit')"
}
Set-Content -Path (Join-Path $App 'apps\desktop\planbench_desktop\COMMIT') `
    -Value $commit -NoNewline -Encoding ascii
Write-Host "   commit: $commit"

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
& $PyExe @PyArgs -m pip install --disable-pip-version-check --no-compile `
    --target $SitePackages -r (Join-Path $RepoRoot 'requirements.txt') pywebview
if ($LASTEXITCODE -ne 0) { throw 'pip install failed' }

Write-Step 'Writing the interpreter path files'
# Generated from pyproject rather than written here: a fourth
# hand-maintained copy of the source-root list is a fourth chance at the
# drift that already cost this project a green suite over an API that
# could not boot.
& $PyExe @PyArgs (Join-Path $RepoRoot 'scripts\desktop\make_runtime_paths.py') `
    $Runtime --python-tag $EmbedSpec.python_tag
if ($LASTEXITCODE -ne 0) { throw 'failed to write the runtime path files' }

# ------------------------------------------------------------ smoke gate
Write-Step 'Smoke testing the stage (release gate)'
$StagePython = Join-Path $Runtime 'python.exe'
# Judged by exit code, not by whether anything reached stderr. Alembic
# logs its migrations there at INFO, and with $ErrorActionPreference
# set to Stop a *successful* run would abort the build on its own
# progress output.
$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    & $StagePython (Join-Path $App 'scripts\desktop\smoke_stage.py') 2>&1 |
        ForEach-Object { Write-Host "   $_" }
    $smoke = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previous
}
if ($smoke -ne 0) {
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
$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    & $Iscc "/DAppVersion=$Version" "/DStageDir=$Stage" "/DOutputDir=$DistDir" `
        (Join-Path $RepoRoot 'installer\planbench.iss') 2>&1 | Out-Null
    $compiled = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previous
}
if ($compiled -ne 0) { throw 'Inno Setup failed' }

Write-Step 'Done'
Get-ChildItem $DistDir -Filter '*.exe' | ForEach-Object {
    Write-Host ("   {0}  ({1:N0} MB)" -f $_.Name, ($_.Length / 1MB))
}
