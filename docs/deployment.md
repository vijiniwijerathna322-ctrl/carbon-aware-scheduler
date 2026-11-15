# Deploying a live demo (free tier)

This walks through putting the API and dashboard on free-tier hosts so a CV
link opens a working app instead of only README instructions. Both steps
need you to sign in with your own GitHub account on the host's site — that
part can't be automated or done on your behalf.

The API and dashboard deploy **separately**: `streamlit_app.py` only ever
talks to the API over HTTP via `CARBON_API_URL` (see `docs/architecture.md`),
so there's no shared build step between them.

## 1. API on Render (free Docker web service)

1. Go to [render.com](https://render.com) and sign in with GitHub.
2. **New → Blueprint**, pick this repository. Render reads `render.yaml` at
   the repo root and proposes a `carbon-scheduler-api` web service using the
   existing `Dockerfile`.
3. Before the first deploy, set these environment variables in Render's
   dashboard (they're intentionally left out of `render.yaml` with
   `sync: false` so no values are committed):
   - `API_KEYS` — a key you make up (e.g. a random 32-char string) if you
     want `/v1/*` to require `X-API-Key`. Leave unset to keep the demo
     keyless.
   - `CORS_ALLOWED_ORIGINS` — the dashboard's URL once you have it from step
     2 below (comma-separated if you add more than one origin later).
4. Deploy. Render builds the Docker image (same one `scripts/smoke_docker.sh`
   and CI already verify) and serves it on a `*.onrender.com` URL with
   `/healthz` as the health check path.
5. Confirm it's live:
   ```bash
   curl --fail https://<your-service>.onrender.com/healthz
   curl --fail "https://<your-service>.onrender.com/v1/forecast?horizon=1"
   ```
6. **Free-tier caveat**: Render's free web services sleep after inactivity
   and cold-start on the next request (tens of seconds). That's expected —
   mention it next to the link rather than treating the first slow response
   as a bug.

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
   CARBON_API_URL = "https://<your-service>.onrender.com"
   ```
5. Deploy. Once live, copy its URL back into Render's `CORS_ALLOWED_ORIGINS`
   (step 1.3) so the dashboard's browser-side requests aren't blocked — the
   dashboard's own server-side `httpx` calls don't need CORS, but Streamlit's
   client-rendered components may still originate browser requests.

## 3. Auto-deploy on release (optional)

`render.yaml`'s blueprint deploys on every push to the connected branch by
default — no extra workflow needed for that. If you want releases (`v*`
tags, mirroring `.github/workflows/release.yml`) to also trigger Render
explicitly: in Render, open the service → Settings → **Deploy Hook**, copy
the URL, then add it as a repository secret:

```bash
gh secret set RENDER_DEPLOY_HOOK_URL
```

and add a step to a workflow that runs on tag push:

```yaml
- name: Trigger Render deploy
  run: curl --fail -X POST "$RENDER_DEPLOY_HOOK_URL"
  env:
    RENDER_DEPLOY_HOOK_URL: ${{ secrets.RENDER_DEPLOY_HOOK_URL }}
```

This repo does not ship that workflow by default, since it's only useful once
the Render service above already exists.

## 4. Update the README

Once both are live, replace the placeholder in README's "Offline API demo"
section (or add a "Live demo" line near the top) with the real URLs, and note
the free-tier sleep/cold-start behavior next to them.
