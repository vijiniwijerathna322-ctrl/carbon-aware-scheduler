# Deploying a live demo (free tier)

This walks through putting the API and dashboard on free-tier hosts so a CV
link opens a working app instead of only README instructions. Both steps
need you to sign in with your own GitHub account on the host's site — that
part can't be automated or done on your behalf.

The API and dashboard deploy **separately**: `streamlit_app.py` only ever
talks to the API over HTTP via `CARBON_API_URL` (see `docs/architecture.md`),
so there's no shared build step between them.

## 1. API on Railway (free trial/tier, no card required)

Railway's own pricing page states its trial and free tier need no credit
card, and it auto-detects a `Dockerfile` in the repo. `railway.toml` at the
repo root pins the builder explicitly so it doesn't try Nixpacks instead.

1. Go to [railway.com](https://railway.com) and sign in with GitHub.
2. **New Project → Deploy from GitHub repo**, pick this repository.
3. Railway should detect `railway.toml`/`Dockerfile` and build from it. If it
   instead proposes a Nixpacks build, open the service's **Settings → Build**
   and switch the builder to **Dockerfile** manually.
4. The `Dockerfile` already bakes in sane demo defaults (`DEMO_MODE=1`,
   `CARBON_DATA_DIR`, `CARBON_MODELS_DIR`, `PORT=8000`), so the service should
   come up with **zero required configuration**. Railway injects its own
   `PORT`, which the image already respects.
5. Optional environment variables (Settings → Variables), same as the
   Dockerfile's definitions in `src/carbon_scheduler/config.py`:
   - `API_KEYS` — a key you make up if you want `/v1/*` to require
     `X-API-Key`. Leave unset to keep the demo keyless.
   - `CORS_ALLOWED_ORIGINS` — the dashboard's URL once you have it from step
     2 below.
6. Under **Settings → Networking**, generate a public domain
   (`*.up.railway.app`) if one isn't assigned automatically.
7. Confirm it's live:
   ```bash
   curl --fail https://<your-service>.up.railway.app/healthz
   curl --fail "https://<your-service>.up.railway.app/v1/forecast?horizon=1"
   ```
8. **Free-tier caveats**: Railway's free tier is capped (around 1 vCPU /
   0.5 GB RAM per service) and the trial's one-time credit is time- and
   usage-limited before it falls back to a small monthly credit — fine for a
   low-traffic demo, not for sustained load. The service may also sleep on
   inactivity depending on current plan behavior; treat a slow first request
   as expected, not a bug.

**Alternative: Render** (`render.yaml` is also committed and ready) works the
same way via **New → Blueprint**, but Render now asks for a card to verify
identity before using Blueprints, even though the service itself stays free
(a $1 temporary authorization, not a charge). Use it instead if you'd rather
add a card than live with Railway's tighter free-tier limits.

## 2. Dashboard on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with
   GitHub.
2. **New app**, pick this repository, branch `main`, main file path
   `streamlit_app.py`.
3. Under **Advanced settings**, set the Python dependency file to
   `requirements-dashboard.txt` (Streamlit Cloud doesn't run `uv sync`, and
   the dashboard doesn't need the full ML/data stack — see that file's
   comment).
4. Add a secret (Settings → Secrets):
   ```toml
   CARBON_API_URL = "https://<your-service>.up.railway.app"
   ```
5. Deploy. Once live, copy its URL back into the API host's
   `CORS_ALLOWED_ORIGINS` (step 1.5) so the dashboard's browser-side requests
   aren't blocked — the dashboard's own server-side `httpx` calls don't need
   CORS, but Streamlit's client-rendered components may still originate
   browser requests.

## 3. Auto-deploy on release (optional)

Both Railway and Render redeploy on every push to the connected branch by
default — no extra workflow needed for that. If you want releases (`v*`
tags, mirroring `.github/workflows/release.yml`) to also trigger a deploy
explicitly: each host has an equivalent of a deploy-hook URL (Railway:
service → Settings → look for a webhook/trigger URL; Render: service →
Settings → **Deploy Hook**). Copy whichever you use, then add it as a
repository secret:

```bash
gh secret set DEPLOY_HOOK_URL
```

and add a step to a workflow that runs on tag push:

```yaml
- name: Trigger deploy
  run: curl --fail -X POST "$DEPLOY_HOOK_URL"
  env:
    DEPLOY_HOOK_URL: ${{ secrets.DEPLOY_HOOK_URL }}
```

This repo does not ship that workflow by default, since it's only useful once
the API service above already exists.

## 4. Update the README

Once both are live, replace the placeholder in README's "Offline API demo"
section (or add a "Live demo" line near the top) with the real URLs, and note
the free-tier sleep/cold-start behavior next to them.
