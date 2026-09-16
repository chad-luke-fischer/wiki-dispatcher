# publish.ps1 — create the public GitHub repo, push, and turn on GitHub Pages from /docs.
# Run from this folder in PowerShell:   .\publish.ps1
# Needs: git, GitHub CLI (`gh auth login` once). Safe to re-run: every step skips what already exists.

$ErrorActionPreference = "Stop"

# Guard: refuse to run anywhere but the wiki-dispatcher folder. C:\Users\chad_ is itself a
# git repo, so a stray run from a parent dir would `git add -A` the entire home directory
# and `gh repo create --public` would publish it.
if (-not (Test-Path "pyproject.toml") -or -not (Select-String -Path "pyproject.toml" -Pattern '^name = "wiki-dispatcher"' -Quiet)) {
  throw "Refusing: not the wiki-dispatcher folder (no pyproject.toml naming wiki-dispatcher)."
}
$Owner = "chad-luke-fischer"
$Repo  = "wiki-dispatcher"
$Full  = "$Owner/$Repo"

function Step($msg) { Write-Host "▸ $msg" -ForegroundColor DarkYellow }

# 0. preflight
foreach ($tool in @("git", "gh")) {
  if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool is not installed or not on PATH" }
}
gh auth status *> $null
if ($LASTEXITCODE -ne 0) { throw "GitHub CLI is not signed in. Run: gh auth login" }

# 1. local repo
if (-not (Test-Path ".git")) {
  Step "git init"
  git init -b main | Out-Null
}
git add -A
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
  Step "commit"
  $msg = @"
Scaffold wiki-dispatcher: vault traversal, skill garden, evolve loop, announcement page

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Me18vyKHAUgSCq2Kj71k8e
"@
  git commit -q -m $msg
} else { Step "nothing new to commit" }

# 2. remote repo
gh repo view $Full *> $null
if ($LASTEXITCODE -ne 0) {
  Step "create public repo $Full"
  gh repo create $Full --public --source . --remote origin --description "A CLI agent mounted to an llm-wiki style Obsidian vault: traverses, tends a garden of self-evolving skills, dispatches deliverables." | Out-Null
} elseif (-not (git remote get-url origin 2>$null)) {
  git remote add origin "https://github.com/$Full.git"
}

Step "push main"
git push -u origin main

# 3. GitHub Pages from main:/docs
$pages = gh api "repos/$Full/pages" 2>$null
if ($LASTEXITCODE -ne 0) {
  Step "enable GitHub Pages (main, /docs)"
  gh api -X POST "repos/$Full/pages" -f "source[branch]=main" -f "source[path]=/docs" | Out-Null
} else {
  Step "Pages already enabled; pointing at main:/docs"
  gh api -X PUT "repos/$Full/pages" -f "source[branch]=main" -f "source[path]=/docs" | Out-Null
}

Write-Host ""
Write-Host "Published. First build takes a minute or two:" -ForegroundColor Green
Write-Host "  https://$Owner.github.io/$Repo/"
Write-Host "  https://github.com/$Full"
