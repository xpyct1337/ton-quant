#!/bin/zsh
# TON Quant — deploy from Mac (equivalent of deploy.bat for Windows).
# Site is GitHub Pages built by .github/workflows/deploy.yml on push to main.
# NOTE: not needed for desk data — /desk reads data/desk/verdicts.json live from
# raw.githubusercontent main; the desk pushes it itself. Use this for app/ + *.html.
cd "$(dirname "$0")" || exit 1
echo "=== TON Quant — Deploy (Mac) ==="

# integrity check: no truncated root HTML (same guard as deploy.bat)
bad=0
for f in *.html; do
  [ -e "$f" ] || continue
  grep -q "</html>" "$f" || { echo "  TRUNCATED: $f (missing </html>) — aborted"; bad=1; }
done
[ "$bad" = 1 ] && exit 1
echo "  HTML OK"

git status --short
git add -A
git commit -m "update" || echo "nothing to commit"
git pull --rebase --autostash origin main || { echo "ERROR: pull failed, resolve conflicts"; exit 1; }

if git push origin main; then
  echo "=== SUCCESS — site rebuilds in ~1min: https://xpyct1337.github.io/ton-quant/ ==="
else
  echo "=== ERROR — check SSH / connection ==="
  exit 1
fi
