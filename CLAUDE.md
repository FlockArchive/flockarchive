# Flock Archiver

On-demand archival tool for Flock Safety's public websites. Flock blocks the Wayback Machine from archiving their sites — this tool preserves their public claims for ALPR transparency and FOIA/IPRA work.

## Architecture

**GitHub Actions + GitHub Pages + Cloudflare Worker**

- **GitHub Actions** runs the crawler (Playwright + httpx). No recurring schedule — snapshots are point-in-time, triggered on demand.
- **GitHub Pages** hosts the static site built from archived data.
- **Cloudflare Worker** (`flockarchivesubmit.cloudflare-hamper588.workers.dev`) proxies URL submissions from the public site to GitHub `repository_dispatch`. Holds the PAT as a secret so users don't need a GitHub account.
- **Local server** (`main.py`) still works standalone on port 8888 (FastAPI + SQLite). Separate from the GitHub deployment.

### Key Files

- `crawl.py` — Standalone crawler. `--url <url>` for single snapshot, no args for bulk crawl of all URLs in `urls.json`.
- `build_site.py` — Generates static HTML site from `archive/index.json` into `_site/`.
- `urls.json` — Tracked URL list (seed + user-submitted). Source of truth for what gets crawled.
- `archive/` — HTML snapshots + screenshots, organized by domain/path.
- `archive/index.json` — Metadata index of all snapshots (timestamps, hashes, change detection).
- `worker/submit-worker.js` — Cloudflare Worker source.
- `.github/workflows/crawl.yml` — Actions workflow (dispatch + manual bulk crawl + site build + deploy).
- Local server: `main.py`, `archiver.py`, `database.py`, `scheduler.py`, `config.py`, `templates/`.

### Data Flow

1. User submits URL on the Pages site → JS form validates `flocksafety.com` domain
2. POST to Cloudflare Worker → Worker validates domain again → dispatches `repository_dispatch`
3. GitHub Actions checks out repo, runs `crawl.py --url <url>` → fetches HTML (httpx, Playwright fallback for Cloudflare 403s) + takes screenshot
4. Commits snapshot to `archive/`, updates `urls.json` and `archive/index.json`
5. Runs `build_site.py` to regenerate static site → deploys to GitHub Pages

## Repo & Deployment

- **Repo:** `github.com/FlockArchive/flockarchive` (public, dedicated GitHub org)
- **Site:** `https://flockarchive.github.io/flockarchive/`
- **PAT:** Fine-grained token stored at `.flock-archive-pat` (gitignored). Needs: Contents, Actions, Pages, Workflows (all read/write).
- **Worker secret:** `GITHUB_PAT` in Cloudflare Worker settings (same token value).

## Development

```bash
# Local server (standalone, uses SQLite)
./run.sh  # bootstraps venv, installs deps, starts on port 8888

# Test crawler locally
source venv/bin/activate
python crawl.py --url "https://www.flocksafety.com/trust"

# Build static site locally
python build_site.py  # outputs to _site/

# Trigger remote crawl via GitHub Actions
# (uses PAT from .flock-archive-pat)
```

## Key Conventions

- **flocksafety.com only** — Domain validation at 3 layers: JS form, Cloudflare Worker, `crawl.py`. Don't weaken this.
- **On-demand snapshots** — No recurring schedule. Each submission = one snapshot. Same URL submitted again = new snapshot.
- **Screenshot every snapshot** — Not just on change. Every archive includes a full-page PNG.
- **Cloudflare bypass** — httpx tries first; on 403, falls back to Playwright headless browser.
- **HTML normalization** — Strips nonces, CSRF tokens, timestamps before SHA-256 hashing for change detection.
- **Concurrent crawling** — Semaphore(4) for bulk runs to avoid hammering Flock's servers.

## Git

- Tim is the sole author. Never include Co-Authored-By lines in commits.
- Commit identity: `tkraus13` / `tkraus13@users.noreply.github.com`
- The Actions bot commits as `FlockArchive Bot` / `bot@flockarchive.github.io`
- Port 8888 for local server (Tim uses 8080 for Burp Suite).

## Gotchas

- `.flock-archive-pat` is the PAT file (dashes not dots). Gitignored.
- `data/` directory (SQLite + local snapshots) is gitignored — only used by the local server.
- Two concurrent `repository_dispatch` runs can race on `git push`. The workflow includes `git pull --rebase` before push to handle this.
- Some Flock pages are SPAs that need `wait_for_load_state("networkidle")` + 5s delay to fully render.
- Flock's `transparency.flocksafety.com` subdomain uses Cloudflare protection — always needs browser fallback.
