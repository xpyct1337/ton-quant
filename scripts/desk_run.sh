#!/bin/zsh
# TON Quant v3.0 — AI Smart-Money Desk nightly runner (launchd, spec §11.5/E1).
# pull -> ensure Ollama -> run desk -> commit & push verdicts. Never wedges:
# every step tolerates failure so a bad night doesn't block the next.
# Log: ~/Library/Logs/tonquant-desk.log
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_KV_CACHE_TYPE=q8_0
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

REPO="$HOME/Projects/ton-quant"
LOG="$HOME/Library/Logs/tonquant-desk.log"
cd "$REPO" || exit 0
exec >> "$LOG" 2>&1
echo "=== desk run $(date) ==="

# ensure local Ollama server is up
if ! curl -sf http://localhost:11434/api/version >/dev/null 2>&1; then
  echo "starting ollama serve"
  nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
  for i in {1..30}; do
    curl -sf http://localhost:11434/api/version >/dev/null 2>&1 && break
    sleep 1
  done
fi

git pull --rebase --autostash origin main || echo "pull failed, continuing with local data"
python3 scripts/desk.py || echo "desk.py errored (tolerated)"

if ! git diff --quiet data/desk/ 2>/dev/null || [ -n "$(git status --porcelain data/desk/)" ]; then
  git add data/desk/
  git commit -m "desk: nightly verdicts $(date +%F)" || echo "nothing to commit"
  git push origin main || echo "push failed — verdicts committed locally, sync later"
else
  echo "no verdict changes"
fi
echo "=== done $(date) ==="
