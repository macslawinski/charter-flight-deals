# web

Static deals page: plain HTML + CSS + JS in `public/`, no build step. It reads `public/deals.json`,
which `scripts/export_deals.py` writes in CI (`.github/workflows/web.yml`) right before each Vercel
deploy; the file is gitignored and the browser never talks to the database.

Local preview:

```powershell
python scripts/export_deals.py                       # real data (needs DATABASE_URL)
python -m http.server 8765 -d web --bind 127.0.0.1
# http://127.0.0.1:8765/public/                       real data
# http://127.0.0.1:8765/public/?src=../dev/sample-deals.json   synthetic deals (localhost only)
```

`dev/` holds synthetic preview data and is excluded from deploys (`.vercelignore`).
Donation link: set `CONFIG.donateUrl` in `public/app.js` (hidden while `null`).
