# v2 deploy — one-time setup, then normal flow

## One-time (GitHub web UI)
1. Repo Settings -> Pages -> Build and deployment -> Source: **GitHub Actions**
   (switches off the old branch-based serving; the Deploy workflow now publishes the site).

## Every deploy (unchanged for you)
- Run `deploy.bat` (git add / commit / pull --rebase / push).
- Push to main triggers `.github/workflows/deploy.yml`:
  builds app/ -> copies legacy *.html (except index.html) + styles.css into the build -> publishes.
- Live in ~1-2 min: https://xpyct1337.github.io/ton-quant/

## What changed
- New main page = SvelteKit app in `app/` (the old root index.html is kept but NOT published;
  the Svelte build emits the new index.html).
- Old pages (screener/compare/portfolio/paper/token) keep serving as-is (copied into the build).
- Daily snapshot Action is untouched; data commits don't trigger a rebuild (paths-ignore data/**),
  the site fetches fresh data at runtime regardless.
- Next: Phase 2 = /paper migrated into the SvelteKit app.

## Removing the old vanilla main (index.html)
The old root `index.html` is already OFF production: the Deploy workflow excludes it and the
SvelteKit build emits the new `index.html`. The leftover repo file is harmless (never published).
The sandbox can't delete files on the mount, so retire it on your machine before/with the next deploy:

    git rm index.html

(Legacy tests no longer depend on it: unit.test.mjs trimmed to token.html; integration.test.mjs
skips the index block when /tmp/index_new.html is absent; nav.test.mjs allowlists index.html as
build-provided.)
