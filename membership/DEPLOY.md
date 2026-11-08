# Deploy the membership app to Heroku (test)

This stands up the Django membership app as **its own Heroku app**, separate from
the live Node site, so nothing on www.thedotx.com changes. You'll test it at a
`*.herokuapp.com` URL. Everything here is verified to boot in production mode
(gunicorn + whitenoise + Postgres migrations all pass locally).

The app lives in the `membership/` subdirectory of the repo, so the deploy uses a
**monorepo buildpack** to build from that subfolder.

---

## What you'll need (5 min)
- The Heroku CLI logged in (`heroku login`), or the Heroku dashboard.
- A Stripe account (test mode is fine to start).

## 1. Create the app + database

```bash
# from anywhere; names the app (pick your own unique name)
heroku create thedotx-members

# build from the membership/ subfolder
heroku buildpacks:add https://github.com/lstoll/heroku-buildpack-monorepo -a thedotx-members
heroku buildpacks:add heroku/python -a thedotx-members
heroku config:set APP_BASE=membership -a thedotx-members

# Postgres (smallest paid tier; Heroku no longer offers a free db)
heroku addons:create heroku-postgresql:essential-0 -a thedotx-members
```

## 2. Set config vars

```bash
heroku config:set -a thedotx-members \
  DJANGO_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(50))')" \
  DJANGO_DEBUG=false \
  DJANGO_ALLOWED_HOSTS="members.thedotx.com,.herokuapp.com" \
  SITE_URL="https://members.thedotx.com" \
  MEMBERSHIP_PRICE_LABEL='$20 / month'
```

The live site's "Log in" and "Become a member" buttons point to
`https://members.thedotx.com`, so set that as `SITE_URL`. Until the subdomain
is live (step 3b), you can test at the `*.herokuapp.com` URL — the app already
trusts both.

## 3. Deploy

The app is on the branch `claude/life-purpose-movement-4j2zdx`. Deploy that branch:

```bash
# option A: push the subtree'd branch
git push https://git.heroku.com/thedotx-members.git \
  claude/life-purpose-movement-4j2zdx:main

# option B: connect the GitHub repo in the Heroku dashboard
#   (Deploy tab -> GitHub -> pick repo -> Deploy Branch:
#    claude/life-purpose-movement-4j2zdx)
```

The `Procfile` runs `migrate` on release automatically. Then create your admin
login:

```bash
heroku run python manage.py createsuperuser -a thedotx-members
```

Open it: `heroku open -a thedotx-members` → you should see the members home,
`/accounts/signup/`, `/dots/`, and `/admin/`.

## 3b. Point members.thedotx.com at the app (the subdomain the site links to)

```bash
heroku domains:add members.thedotx.com -a thedotx-members
# Heroku prints a DNS target like xxxx.herokudns.com — copy it.
```

Then in **GoDaddy DNS** (same place you set up thedotx.com), add a **CNAME**:
- Type: `CNAME` · Host/Name: `members` · Value: the `xxxx.herokudns.com` target
  Heroku gave you · TTL: default.

Heroku issues HTTPS automatically (ACM). Give DNS a few minutes, then
`https://members.thedotx.com` should load the app. Until it resolves, the live
site's Log in / Become a member buttons won't open — so do this before (or right
after) you deploy the updated Node site.

## 4. Wire Stripe (test mode)

1. In the Stripe dashboard (test mode), create a **Product** with a **$20.00 /
   month recurring Price**. Copy the Price id (`price_…`).
2. Set the keys:
   ```bash
   heroku config:set -a thedotx-members \
     STRIPE_PUBLISHABLE_KEY=pk_test_xxx \
     STRIPE_SECRET_KEY=sk_test_xxx \
     STRIPE_PRICE_ID=price_xxx
   ```
3. Create the webhook endpoint in Stripe → Developers → Webhooks → Add endpoint:
   - URL: `https://thedotx-members.herokuapp.com/stripe/webhook/`
   - Events: `checkout.session.completed`, `customer.subscription.updated`,
     `customer.subscription.deleted`, `invoice.payment_failed`
   - Copy the signing secret (`whsec_…`) →
     `heroku config:set STRIPE_WEBHOOK_SECRET=whsec_xxx -a thedotx-members`
4. Enable the **Customer Portal**: Stripe → Settings → Billing → Customer portal →
   activate (so "Manage billing" works).

## 5. Test the full flow

1. Sign up (you must tick the Code of Conduct box).
2. Go to **Join** → **Continue to secure checkout** → pay with Stripe's test card
   `4242 4242 4242 4242`, any future date, any CVC.
3. You land back on the profile with "Payment complete…" and, within a few
   seconds, **Status: Active** and a renewal date (the webhook did that).
4. Click **Manage billing** → the Stripe portal opens; try updating the card or
   cancelling.
5. In `/admin/`, confirm the member, and try **promote to Ambassador**.

## Going live later (not now)
- Switch Stripe to **live** keys + a live Price + a live webhook secret.
- Point a real domain at this app and set `SITE_URL` / `DJANGO_ALLOWED_HOSTS` to it.
- Set the `django.contrib.sites` Site domain to the real host (admin → Sites).
- Wire transactional email (reuse Resend) and set `ACCOUNT_EMAIL_VERIFICATION=mandatory`.
- Then retire the Node dyno and move the domains (see README "Cutover plan").

## Troubleshooting
- **Build can't find requirements.txt** → the monorepo buildpack must be *first*
  and `APP_BASE=membership` set. Re-check step 1.
- **400 / DisallowedHost** → add your host to `DJANGO_ALLOWED_HOSTS`.
- **CSRF error on admin/login** → the app already trusts `*.herokuapp.com`; for a
  custom domain add it to `DJANGO_CSRF_TRUSTED_ORIGINS`.
- **Status stays "Incomplete" after paying** → the webhook isn't reaching the app;
  re-check the endpoint URL and that `STRIPE_WEBHOOK_SECRET` matches.
