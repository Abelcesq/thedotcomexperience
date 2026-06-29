# Deploy runbook — thedotx.com on Heroku + GoDaddy

Goal: serve the front door (`web/`) on **Heroku**, then point the **GoDaddy** domain
`thedotx.com` (and `www`) at the Heroku app with HTTPS.

How it's served: a tiny Express server (`server.js`) hosts the static files in `web/`.
`Procfile` runs it; `package.json` pins Node 22 and the one dependency (express). In
production the server forces HTTPS and redirects the bare apex to `www`.

> Heads-up: Heroku has no free tier — the app needs an **Eco or Basic dyno** (paid), and
> automated TLS certs (ACM) require a paid dyno. You said you already have Heroku, so this
> should be covered.

---

## ⭐ Option A — Deploy from the Heroku website (NO command line, recommended)

Easiest path. Nothing to install. Deploys this repo's branch straight from GitHub.

1. Go to **https://dashboard.heroku.com** → **New → Create new app**.
   - App name: e.g. `thedotx` (must be globally unique; try `thedotx-app` if taken). Create.
2. Open the app's **Deploy** tab.
   - **Deployment method:** click **GitHub** → **Connect to GitHub** → authorize.
   - Search `thedotcomexperience` → **Connect** to `abelcesq/thedotcomexperience`.
3. Scroll to **Manual deploy** → choose branch **`claude/life-purpose-movement-4j2zdx`**
   → click **Deploy Branch**. Watch the build log finish ("Your app was successfully deployed").
4. Open the **Settings** tab → **Reveal Config Vars** → add:
   `NODE_ENV` = `production`  (turns on HTTPS + apex→www redirects).
5. Back on **Deploy**, click **Deploy Branch** once more so it picks up the config var.
6. Click **Open app** (top right) → you should see the front door on `https://<app>.herokuapp.com`.
7. **Custom domain:** Settings tab → **Add domain** → `www.thedotx.com`, then again `thedotx.com`.
   Heroku shows a **DNS Target** for each (`…herokudns.com`) — copy them, then do **Section C**.
   HTTPS is issued automatically once the domain is added (on a paid Eco/Basic dyno).

To update the site later: push changes to the branch on GitHub, then **Deploy Branch** again
(or enable "Automatic deploys" on the Deploy tab so every push deploys itself).

---

## Option B — Deploy with the Heroku CLI (if you prefer the terminal)

The CLI isn't installed yet (that's the `heroku : The term 'heroku' is not recognized` error).
Install it first, then run the commands.

**Install on Windows (PowerShell), pick one:**
```powershell
winget install --id=Heroku.HerokuCLI       # if you have winget
# or download the 64-bit installer: https://devcenter.heroku.com/articles/heroku-cli
```
Close and reopen PowerShell after installing so `heroku` is on your PATH. You'll also need
**Git** (https://git-scm.com/download/win) and a local clone of the repo:
```powershell
git clone https://github.com/abelcesq/thedotcomexperience.git
cd thedotcomexperience
git checkout claude/life-purpose-movement-4j2zdx
```
Then:

```bash
# 1. Log in
heroku login

# 2a. Create a new app...                      (pick ONE of 2a / 2b)
heroku create thedotx
# 2b. ...or attach to an existing Heroku app
heroku git:remote -a <your-existing-app-name>

# 3. Production env (enables HTTPS + apex→www redirects in server.js)
heroku config:set NODE_ENV=production

# 4. Ship it. Heroku builds its 'main' branch, so push this branch onto heroku/main:
git push heroku claude/life-purpose-movement-4j2zdx:main
#   (once this branch is merged to your main, it's simply: git push heroku main)

# 5. Confirm it's up on the Heroku URL
heroku open          # opens https://<app>.herokuapp.com
heroku logs --tail   # watch if anything misbehaves
```

You should see the front door at `https://<app>.herokuapp.com`. Verify `/robots.txt`,
`/sitemap.xml`, `/llms.txt`, and that the CTA goes to Skool.

## B. Add your custom domain on Heroku

```bash
heroku domains:add www.thedotx.com
heroku domains:add thedotx.com
heroku certs:auto:enable        # free automated HTTPS certificate (paid dyno required)
heroku domains                  # shows the DNS targets to use in step C
```

`heroku domains` prints a **DNS Target** for each (looks like
`xxxx.herokudns.com`). Copy them.

## C. Point GoDaddy DNS at Heroku

In GoDaddy: **My Products → Domains → thedotx.com → DNS → Manage DNS.**

1. **www (the canonical host):** add/edit a record
   - Type: `CNAME` · Name: `www` · Value: `<the www DNS target from step B>` · TTL: 1 hour
2. **Apex (thedotx.com):** GoDaddy can't CNAME the root cleanly, so use **Domain Forwarding**:
   - Domain Settings → **Forwarding** → Add → forward `thedotx.com` → `https://www.thedotx.com`
     (permanent / 301, "forward only").
   - This sends bare `thedotx.com` to `www`, where Heroku serves the site over HTTPS.

DNS can take 10–60 minutes (sometimes longer) to propagate. Then visit
`https://www.thedotx.com` — done.

## D. After it's live (quick checks)
- `https://www.thedotx.com` loads with the padlock (HTTPS).
- `https://thedotx.com` redirects to `https://www.thedotx.com`.
- `/robots.txt`, `/sitemap.xml`, `/llms.txt` resolve.
- Paste the URL into an X/LinkedIn composer to confirm the social share card (OG image).

---

## E. Wire email capture to your owned list (important)
The page's email form POSTs to `/api/subscribe`. It works out of the box (emails are validated
and logged in `heroku logs --tail`), **but Heroku's disk is ephemeral**, so the local CSV isn't
a real list. Point it at an ESP you own. Two supported ways (set via **Settings → Config Vars**):

### Option 1 — Flodesk (recommended)
Flat pricing (unlimited subscribers), premium templates, built-in automations + Stripe checkout.
1. Create a Flodesk account (flodesk.com — 30-day free trial, no card).
2. In Flodesk, get your **API key**: Account → **Integrations / API** → copy the key.
3. (Optional) Create a **Segment** (e.g. "Website Signups"). To find its ID, with your key run:
   ```bash
   curl -s https://api.flodesk.com/v1/segments -u "YOUR_API_KEY:"
   ```
   Copy the `id` of the segment you want.
4. In Heroku → app → **Settings → Reveal Config Vars**, add:
   - `FLODESK_API_KEY` = `<your key>`
   - `FLODESK_SEGMENT_ID` = `<segment id>`  *(optional — omit to land everyone in the main audience)*
5. The dyno restarts automatically. Submit a test email on the live site → it appears in Flodesk.

The server upserts each email into your Flodesk audience (and the segment), ready for campaigns.

### Option 2 — Generic webhook (Zapier / Make / Formspree / Apps Script)
Add `SUBSCRIBE_WEBHOOK` = `<endpoint URL>`. The server POSTs `{ "email": "...", "source":
"thedotx.com" }` to it. Use this to push into a tool that has no direct API, via Zapier etc.

> Both can be set at once. If neither is set, signups still succeed for the visitor and are
> logged — but won't reach a durable list, so configure at least one before driving traffic.

## Updating the site later
Edit files in `web/`, commit, then re-deploy (Deploy Branch in the dashboard, or
`git push heroku <branch>:main` with the CLI). That's the whole loop.

## Alternative (if you ever want free hosting)
Cloudflare Pages or Netlify will host `web/` for free with auto-HTTPS; you'd point the same
GoDaddy records at them instead. Heroku is the right call now since you already have it.
