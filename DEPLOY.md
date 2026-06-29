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

## A. Deploy to Heroku (one-time, then `git push` to update)

Run these locally where you have the repo and the Heroku CLI:

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

## Updating the site later
Edit files in `web/`, commit, then `git push heroku <branch>:main`. That's the whole loop.

## Alternative (if you ever want free hosting)
Cloudflare Pages or Netlify will host `web/` for free with auto-HTTPS; you'd point the same
GoDaddy records at them instead. Heroku is the right call now since you already have it.
