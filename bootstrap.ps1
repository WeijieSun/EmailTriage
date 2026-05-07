# bootstrap.ps1 — set up email-triage on a fresh Windows machine
#
# Run from PowerShell (no admin needed):
#   .\bootstrap.ps1
#
# What this does:
#   1. Verify / install Python 3.11+ via winget
#   2. Install uv (fast Python package manager)
#   3. Install Python dependencies (streamlit, fastapi, deep-translator, etc.)
#   4. Install Git for Windows (required by Claude Code CLI)
#   5. Install Node.js + Claude Code CLI (@anthropic-ai/claude-code)
#   6. Symlink the email-triage skill into ~/.claude/skills/
#   7. Initialize the SQLite DB (with schema migrations)
#   8. Set up .env for Outlook credentials (if not already present)
#   9. Optionally seed demo data
#  10. Print next-step commands

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-OK($msg) { Write-Host "    OK: $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    WARN: $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "    ERROR: $msg" -ForegroundColor Red }

# -----------------------------------------------------------------------------
# 1. Python
# -----------------------------------------------------------------------------
Write-Step "Checking Python 3.11+"
$pythonOk = $false
try {
    $ver = & python --version 2>&1
    if ($ver -match "Python 3\.(\d+)") {
        $minor = [int]$matches[1]
        if ($minor -ge 11) {
            Write-OK "$ver"
            $pythonOk = $true
        } else {
            Write-Warn "Found $ver, need 3.11+"
        }
    }
} catch {
    Write-Warn "Python not on PATH"
}

if (-not $pythonOk) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Step "Installing Python 3.12 via winget (silent)"
        winget install --id Python.Python.3.12 --silent --accept-source-agreements --accept-package-agreements
        Write-Warn "Python installed. Close & reopen this PowerShell window, then re-run bootstrap.ps1"
        exit 0
    } else {
        Write-Err "winget not available. Install Python 3.11+ manually from https://www.python.org/downloads/"
        exit 1
    }
}

# -----------------------------------------------------------------------------
# 2. uv (preferred) — falls back to pip if uv install fails
# -----------------------------------------------------------------------------
Write-Step "Checking uv"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    try {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
        # uv installs into %USERPROFILE%\.local\bin; add to current session PATH
        $uvBin = Join-Path $env:USERPROFILE ".local\bin"
        if (Test-Path $uvBin) { $env:PATH = "$uvBin;$env:PATH" }
        Write-OK "uv installed"
    } catch {
        Write-Warn "uv install failed; will use pip"
    }
} else {
    Write-OK (& uv --version)
}

# -----------------------------------------------------------------------------
# 3. Dependencies
# -----------------------------------------------------------------------------
Write-Step "Installing Python dependencies"
$useUv = (Get-Command uv -ErrorAction SilentlyContinue) -ne $null
if ($useUv) {
    uv sync
} else {
    if (-not (Test-Path ".venv")) {
        python -m venv .venv
    }
    & ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
    & ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
}
Write-OK "Dependencies installed"

# -----------------------------------------------------------------------------
# 4. Git for Windows (required by Claude Code CLI)
# -----------------------------------------------------------------------------
Write-Step "Checking Git"
$gitOk = $false
try {
    $gitVer = cmd /c "git --version 2>&1"
    if ($gitVer -match "git version") { Write-OK $gitVer; $gitOk = $true }
} catch {}

if (-not $gitOk) {
    Write-Step "Installing Git for Windows via winget"
    winget install Git.Git --accept-source-agreements --accept-package-agreements
    $env:PATH = "C:\Program Files\Git\bin;C:\Program Files\Git\usr\bin;$env:PATH"
    Write-OK "Git installed — restart terminal to pick up PATH"
} else {
    $env:PATH = "C:\Program Files\Git\bin;C:\Program Files\Git\usr\bin;$env:PATH"
}

# -----------------------------------------------------------------------------
# 5. Node.js + Claude Code CLI
# -----------------------------------------------------------------------------
Write-Step "Checking Node.js"
$nodeOk = $false
try {
    $nodeVer = cmd /c "node --version 2>&1"
    if ($nodeVer -match "v\d+") { Write-OK "Node.js $nodeVer"; $nodeOk = $true }
} catch {}

if (-not $nodeOk) {
    Write-Step "Installing Node.js LTS via winget"
    winget install OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
    $env:PATH = "C:\Program Files\nodejs;$env:PATH"
    Write-OK "Node.js installed"
}

Write-Step "Checking Claude Code CLI"
$npmBin = Join-Path $env:APPDATA "npm"
$env:PATH = "$npmBin;C:\Program Files\nodejs;$env:PATH"
$claudeVer = cmd /c "claude --version 2>&1"
if ($claudeVer -match "Claude Code") {
    Write-OK "Claude Code CLI $claudeVer"
} else {
    Write-Step "Installing Claude Code CLI via npm"
    cmd /c "npm install -g @anthropic-ai/claude-code"
    $claudeVer2 = cmd /c "claude --version 2>&1"
    if ($claudeVer2 -match "Claude Code") {
        Write-OK "Claude Code CLI installed: $claudeVer2"
    } else {
        Write-Warn "Claude Code CLI install may need a new terminal to take effect"
    }
}

# -----------------------------------------------------------------------------
# 6. Link skill into ~/.claude/skills/
# -----------------------------------------------------------------------------
Write-Step "Linking skill into Claude Code skills directory"
$claudeSkillsDir = Join-Path $env:USERPROFILE ".claude\skills"
if (-not (Test-Path $claudeSkillsDir)) {
    New-Item -ItemType Directory -Path $claudeSkillsDir -Force | Out-Null
}

$skillTarget = Join-Path $claudeSkillsDir "email-triage"
$skillSource = Join-Path $ProjectRoot "skill"

if (Test-Path $skillTarget) {
    Write-OK "Skill already linked at $skillTarget"
} else {
    # Use a directory junction (no admin required, works across drives on NTFS)
    cmd /c "mklink /J `"$skillTarget`" `"$skillSource`"" | Out-Null
    if (Test-Path $skillTarget) {
        Write-OK "Linked $skillTarget -> $skillSource"
    } else {
        Write-Err "Failed to link skill. Try copying manually: Copy-Item -Recurse `"$skillSource`" `"$skillTarget`""
    }
}

# -----------------------------------------------------------------------------
# 7. Init DB
# -----------------------------------------------------------------------------
Write-Step "Initializing SQLite DB (and running schema migrations)"
if ($useUv) {
    uv run python -m core.db init
} else {
    & ".\.venv\Scripts\python.exe" -m core.db init
}

# -----------------------------------------------------------------------------
# 8. Set up .env for Outlook credentials
# -----------------------------------------------------------------------------
Write-Step "Checking .env for Outlook credentials"
$envFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $ProjectRoot ".env.example") $envFile
    Write-Warn ".env created from .env.example — fill in OUTLOOK_CLIENT_ID before connecting Outlook"
    Write-Host "    See docs/outlook-setup.md for Azure App registration steps." -ForegroundColor Yellow
} else {
    Write-OK ".env already exists"
}

# -----------------------------------------------------------------------------
# 9. Seed demo data (optional, prompt)
# -----------------------------------------------------------------------------
Write-Step "Seed demo data?"
$seed = Read-Host "Type 'y' to seed demo emails for testing [y/N]"
if ($seed -eq "y" -or $seed -eq "Y") {
    if ($useUv) {
        uv run python -m core.seed_demo
    } else {
        & ".\.venv\Scripts\python.exe" -m core.seed_demo
    }
    Write-OK "Demo data seeded (wipe later with: uv run python -m core.db wipe-demo)"
}

# -----------------------------------------------------------------------------
# Done
# -----------------------------------------------------------------------------
Write-Host "`n==> Setup complete." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host ""
Write-Host "  1. Fill in .env with your Azure App credentials:" -ForegroundColor Yellow
Write-Host "       OUTLOOK_CLIENT_ID=<your-client-id>" -ForegroundColor Gray
Write-Host "       OUTLOOK_TENANT_ID=consumers" -ForegroundColor Gray
Write-Host "     (see docs/outlook-setup.md for setup guide)"
Write-Host ""
Write-Host "  2. Login to Outlook:" -ForegroundColor Yellow
Write-Host "       " -NoNewline; Write-Host "uv run python -m core.outlook login" -ForegroundColor Cyan
Write-Host ""
Write-Host "  3. Start dashboard:" -ForegroundColor Yellow
Write-Host "       " -NoNewline; Write-Host "uv run streamlit run dashboard/app.py" -ForegroundColor Cyan
Write-Host "     Then open http://localhost:8501"
Write-Host ""
Write-Host "  4. (Optional) Login Claude Code CLI for AI features:" -ForegroundColor Yellow
Write-Host "       " -NoNewline; Write-Host "claude" -ForegroundColor Cyan
Write-Host "     Follow the login prompts the first time."
Write-Host ""
