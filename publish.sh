#!/usr/bin/env bash
# publish.sh — create the public GitHub repo, push, and turn on GitHub Pages from /docs.
# Run from this folder:   ./publish.sh
# Needs: git, GitHub CLI (`gh auth login` once). Safe to re-run.
set -euo pipefail

# Guard: refuse to run anywhere but the wiki-dispatcher folder. C:\Users\chad_ is itself a
# git repo, so a stray run from a parent dir would `git add -A` the entire home directory
# and `gh repo create --public` would publish it.
grep -q '^name = "wiki-dispatcher"' pyproject.toml 2>/dev/null || {
  echo "Refusing: not the wiki-dispatcher folder (no pyproject.toml naming wiki-dispatcher)."; exit 1; }
OWNER="chad-luke-fischer"; REPO="wiki-dispatcher"; FULL="$OWNER/$REPO"
step() { printf '\033[33m▸ %s\033[0m\n' "$*"; }

command -v git >/dev/null || { echo "git not installed"; exit 1; }
command -v gh  >/dev/null || { echo "gh (GitHub CLI) not installed"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "GitHub CLI is not signed in. Run: gh auth login"; exit 1; }

[ -d .git ] || { step "git init"; git init -b main >/dev/null; }
git add -A
if ! git diff --cached --quiet; then
  step "commit"
  git commit -q -m "Scaffold wiki-dispatcher: vault traversal, skill garden, evolve loop, announcement page

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Me18vyKHAUgSCq2Kj71k8e"
else step "nothing new to commit"; fi

if ! gh repo view "$FULL" >/dev/null 2>&1; then
  step "create public repo $FULL"
  gh repo create "$FULL" --public --source . --remote origin \
    --description "A CLI agent mounted to an llm-wiki style Obsidian vault: traverses, tends a garden of self-evolving skills, dispatches deliverables." >/dev/null
elif ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin "https://github.com/$FULL.git"
fi

step "push main"; git push -u origin main

if gh api "repos/$FULL/pages" >/dev/null 2>&1; then
  step "Pages already enabled; pointing at main:/docs"
  gh api -X PUT "repos/$FULL/pages" -f 'source[branch]=main' -f 'source[path]=/docs' >/dev/null
else
  step "enable GitHub Pages (main, /docs)"
  gh api -X POST "repos/$FULL/pages" -f 'source[branch]=main' -f 'source[path]=/docs' >/dev/null
fi

printf '\n\033[32mPublished. First build takes a minute or two:\033[0m\n  https://%s.github.io/%s/\n  https://github.com/%s\n' "$OWNER" "$REPO" "$FULL"
