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

## E. Make email capture durable (important)
The page has an email-capture form that POSTs to `/api/subscribe`. It works out of the box
(emails are validated and logged — visible in `heroku logs --tail`), **but Heroku's disk is
ephemeral**, so don't rely on the local CSV. To capture emails durably into something you own,
set ONE config var to a webhook that stores them:

- **Heroku → your app → Settings → Reveal Config Vars** → add
  `SUBSCRIBE_WEBHOOK` = `<your endpoint URL>`

Easy endpoints to use as the value (pick one, ~2 min):
- **Formspree** (formspree.io) — create a form, use its `https://formspree.io/f/xxxx` URL.
- **Google Sheet** — a Google Apps Script Web App URL that appends a row.
- **Zapier / Make webhook** — catches the POST and pushes to Mailchimp/Sheets/etc.
- **Mailchimp / ConvertKit / Beehiiv** — via their webhook or a Zap.

The server POSTs `{ "email": "...", "source": "thedotx.com" }` to that URL. Once set, every
signup lands in a list you control. (Until then, signups still succeed for the visitor and
appear in the logs.)

## Updating the site later
Edit files in `web/`, commit, then re-deploy (Deploy Branch in the dashboard, or
`git push heroku <branch>:main` with the CLI). That's the whole loop.

## Alternative (if you ever want free hosting)
Cloudflare Pages or Netlify will host `web/` for free with auto-HTTPS; you'd point the same
GoDaddy records at them instead. Heroku is the right call now since you already have it.
