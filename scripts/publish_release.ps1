<#
.SYNOPSIS
    Automated script to initialize GitHub repo, push code, and publish Release v1.0.0 for Musicat.
.DESCRIPTION
    Checks GitHub CLI authentication, creates remote repo IlRed89/Musicat if not present,
    pushes main branch and v1.0.0 tag, and triggers the CI/CD release workflow.
#>

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   🐱🎧 MUSICAT - GITHUB REPO & RELEASE INITIALIZER       " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Locate GitHub CLI
$ghPath = "gh"
if (-not (Get-Command "gh" -ErrorAction SilentlyContinue)) {
    if (Test-Path "C:\Program Files\GitHub CLI\gh.exe") {
        $ghPath = "C:\Program Files\GitHub CLI\gh.exe"
    } else {
        Write-Host "[ERROR] GitHub CLI ('gh') not found in PATH or standard directory." -ForegroundColor Red
        Write-Host "Please install gh using: winget install --id GitHub.cli" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "[OK] Found GitHub CLI at: $ghPath" -ForegroundColor Green

# 2. Check Authentication
Write-Host ""
Write-Host "[1/5] Checking GitHub authentication status..." -ForegroundColor Cyan
& $ghPath auth status 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] Not logged into GitHub CLI. Initiating interactive login..." -ForegroundColor Yellow
    Write-Host "    (Choose 'GitHub.com', 'HTTPS', and authenticate via web browser)" -ForegroundColor Gray
    & $ghPath auth login
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] GitHub authentication was not completed." -ForegroundColor Red
        exit 1
    }
}
Write-Host "[OK] Authenticated successfully with GitHub." -ForegroundColor Green

# 3. Check or Create Remote Repository
Write-Host ""
Write-Host "[2/5] Checking if remote repository 'IlRed89/Musicat' exists..." -ForegroundColor Cyan
$repoExists = $false
try {
    & $ghPath repo view "IlRed89/Musicat" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $repoExists = $true
        Write-Host "[OK] Remote repository IlRed89/Musicat already exists." -ForegroundColor Green
    }
} catch {
    $repoExists = $false
}

if (-not $repoExists) {
    Write-Host "Creating remote repository: IlRed89/Musicat ..." -ForegroundColor Yellow
    & $ghPath repo create "IlRed89/Musicat" --public --description "Universal DJ Music Cataloger, Mp3tag-like Metadata Engine & Multi-Source Reconciliation Tool" --homepage "https://github.com/IlRed89/Musicat"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARN] Repo creation command finished with code $LASTEXITCODE. Proceeding with git push..." -ForegroundColor Yellow
    } else {
        Write-Host "[OK] Remote repository IlRed89/Musicat created successfully!" -ForegroundColor Green
    }
}

# 4. Configure Git Remote
Write-Host ""
Write-Host "[3/5] Verifying git remote configuration..." -ForegroundColor Cyan
$remotes = git remote -v
if ($remotes -notmatch "origin") {
    Write-Host "Adding remote origin: https://github.com/IlRed89/Musicat.git" -ForegroundColor Yellow
    git remote add origin "https://github.com/IlRed89/Musicat.git"
} else {
    git remote set-url origin "https://github.com/IlRed89/Musicat.git"
    Write-Host "[OK] Remote origin configured to https://github.com/IlRed89/Musicat.git" -ForegroundColor Green
}

# 5. Push Commits
Write-Host ""
Write-Host "[4/5] Pushing 'main' branch to GitHub..." -ForegroundColor Cyan
git branch -M main
git push -u origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to push main branch to origin." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] 'main' branch pushed successfully!" -ForegroundColor Green

# 6. Push Tags (Triggering GitHub Actions Release Workflow)
Write-Host ""
Write-Host "[5/5] Pushing release tag 'v1.0.0'..." -ForegroundColor Cyan
$tags = git tag -l "v1.0.0"
if (-not $tags) {
    git tag -a "v1.0.0" -m "Musicat v1.0.0 - Initial Public Release"
}
git push origin v1.0.0 --tags
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] Tag push reported warning/exit code $LASTEXITCODE." -ForegroundColor Yellow
} else {
    Write-Host "[OK] Tag 'v1.0.0' pushed successfully!" -ForegroundColor Green
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "   🎉 MUSICAT v1.0.0 SUCCESSFULLY PUBLISHED TO GITHUB!    " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Repository URL:  https://github.com/IlRed89/Musicat" -ForegroundColor Cyan
Write-Host "CI/CD Actions:   https://github.com/IlRed89/Musicat/actions" -ForegroundColor Cyan
Write-Host "Release Tracker: https://github.com/IlRed89/Musicat/releases" -ForegroundColor Cyan
Write-Host ""
Write-Host "The GitHub Actions workflow (.github/workflows/release.yml) is now automatically building:" -ForegroundColor Yellow
Write-Host "  - Windows Portable Standalone Executable (.zip)" -ForegroundColor Gray
Write-Host "  - Inno Setup Dual-Mode Installer (Musicat-Setup.exe)" -ForegroundColor Gray
Write-Host "  - SHA256 Checksums" -ForegroundColor Gray
Write-Host ""
