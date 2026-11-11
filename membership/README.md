# The Dot Com Experience — Membership Platform (Django)

The member engine for The Dot Com Experience: accounts, the **$100/mo Stripe
subscription** (hosted Checkout + Customer Portal, modeled on the Tasks app /
ezaitask.com), member **profiles** (city, phone, SMS opt-in), the **Dots**
local-circle finder, the **Request a new Dot location** application, and
**ambassador/admin** roles.

> This runs alongside the live Node/Heroku marketing site. The Node site stays
> live until this is ready; then we cut the domains over. See "Cutover" below.

## What's built (and verified)

- **Auth** via django-allauth (email login, signup, password reset). Signup
  **requires a Code of Conduct checkbox** — you cannot create an account without
  agreeing; the consent + timestamp are stored on the profile.
- **$100/mo subscription**: `/join/` → hosted Stripe Checkout (`mode=subscription`)
  → success returns to `/accounts/profile/?stripe=ok`. **The Stripe webhook is the
  source of truth** (`/stripe/webhook/`, signature-verified): it sets membership
  active / past_due / canceled and stores the renewal date.
- **Manage billing**: profile → "Manage billing" → Stripe Customer Portal
  (update card, invoices, cancel). No custom billing UI.
- **Profile page** (`/accounts/profile/`): Account, Membership (plan / status /
  renews + Manage billing), My Dot, Help — mirrors the Tasks app layout.
- **Profile details**: display name, **city** (for Dot matching), **phone (E.164)**
  + **"Text me about my Dot"** SMS consent. SMS is *collected only* (send later via
  Twilio once A2P 10DLC is done).
- **Dots finder** (`/dots/`): search by city; if none, join the waitlist or
  request a new location.
- **Request a new Dot location** (`/dots/request/`): a vetted **application**
  (a vetted application) — reviewed and promoted to Ambassador by an admin.
- **Admin** (`/admin/`): manage Dots, applications, waitlist, and members;
  one-click **promote to Ambassador**.

All of the above is covered by a smoke test and a webhook signature/state test
(see "Verify" below) — both pass.

## Run it locally

```bash
cd membership
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then edit: set DJANGO_SECRET_KEY at minimum
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
# open http://localhost:8000/  (admin at /admin/)
```

Without Stripe keys the app still runs — `/join/` shows the waitlist path and
no charge is attempted. Add Stripe test keys to exercise real checkout.

### Stripe setup (test mode first)

1. In the Stripe dashboard, create a **Product** with a **$100/month recurring
   Price**. Copy the Price id (`price_…`) into `STRIPE_PRICE_ID`.
2. Set `STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY` (test keys).
3. Webhook: run `stripe listen --forward-to localhost:8000/stripe/webhook/`
   and copy the `whsec_…` into `STRIPE_WEBHOOK_SECRET`. Subscribe to
   `checkout.session.completed`, `customer.subscription.updated`,
   `customer.subscription.deleted`, `invoice.payment_failed`.
4. Enable the **Customer Portal** in the Stripe dashboard (Billing → Customer
   portal) so "Manage billing" works.
5. **Pricing by country** (optional, a CEO decision): configure additional
   Prices / adaptive pricing in the dashboard — not in code.

## Verify

```bash
# from the membership/ dir, with the venv active and DJANGO_SECRET_KEY set:
python manage.py check
python manage.py test        # (add app tests here as they grow)
```

Ad-hoc smoke/webhook scripts used during the build live outside the repo; the
flows they cover: CoC-gated signup, profile edit (phone/SMS), Dot application,
waitlist, and the four Stripe webhook transitions with signature verification.

## Security & compliance (already wired)

- Card data never touches us — hosted Checkout/Portal keep us at **SAQ-A**.
- **Webhook signatures are verified**; unsigned/invalid calls are rejected (400).
- CSRF on all forms; in production: HTTPS redirect, secure cookies, HSTS
  (enabled when `DJANGO_DEBUG=false`).
- **Forfeiture of fees** on removal for a Code-of-Conduct violation is stated in
  the public `/terms/` (served by the Node site today) and in the signup consent.
- SMS: consent captured now; **do not send** until A2P 10DLC + STOP/HELP are done.

## Still to do before launch (honest list)

- Wire transactional email (allauth verification / welcome) — reuse the existing
  **Resend** setup or the Node `/api/subscribe` funnel (`billing/notify.py` is the
  place to forward signups to MailerLite so the owned list stays unified).
- Set the `django.contrib.sites` Site domain/name to thedotx.com (currently the
  default "example.com" shows in auth emails).
- Ambassador dashboard (create/manage their Dot) — models support it; needs views.
- Seed real Dots; add map/geo to the finder (optional, later).
- Legal review of `/terms/` by the CEO (an attorney) before taking payments.

## Cutover plan (Node → Django)

Keep the Node site live. When this app is ready:
1. Deploy this `membership/` project as its own Heroku app (Python buildpack,
   add Heroku Postgres; the `Procfile` runs migrations on release + gunicorn).
2. Port the marketing home/about into Django templates (or keep Node serving the
   static marketing pages and let Django own `/accounts`, `/join`, `/dots`).
3. Move the domains (thedotx.com, thedotcomexperience.com) to the Django app and
   retire the Node dyno. Carry over favicons and `/terms`, `/about`, `llms.txt`.
