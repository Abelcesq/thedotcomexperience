# Membership & Payment Flow — Spec for the Django Build

> Hand-off from the live (Node/Heroku) thedotx project to the Django build chat.
> Scope: member auth, the **$20/mo Stripe subscription flow** (modeled on the Tasks app,
> ezaitask.com), the **member profile page**, payment-method management, phone/SMS capture,
> the **Dots** local-circle finder, and admin/**ambassador** roles.
>
> Reference example (the pattern to copy): **ezaitask.com** — hosted Stripe Checkout →
> success redirect `/accounts/profile/?stripe=ok` ("Payment complete — your plan is being
> activated…") → profile page with a **Subscription** card and a **Manage billing** button
> (Stripe Customer Portal).

---

## 1. The payment flow (copy the Tasks app)

1. Visitor clicks **"Become a member — $20/month"** (`/join/`).
2. **Auth first.** If not logged in, sign up / log in (recommend **django-allauth**), creating the `User`.
3. Server creates a **Stripe Checkout Session** (`mode=subscription`, the $20/mo recurring Price):
   - `success_url = https://www.thedotx.com/accounts/profile/?stripe=ok`
   - `cancel_url  = https://www.thedotx.com/join/?stripe=cancel`
   - tie it to the user: `customer` (or `customer_email`) + `client_reference_id = user.id`
   - `allow_promotion_codes=True` (optional)
4. **Redirect to hosted `checkout.stripe.com`** (Stripe enters/handles the card — PCI stays with
   Stripe; you keep SAQ-A). This is the `cs_live_…` session pattern you saw.
5. On success Stripe returns to `/accounts/profile/?stripe=ok`. Show the same reassurance the Tasks
   app shows: *"Payment complete — your plan is being activated. This page will reflect the change
   within a few seconds."*
6. **The webhook is the source of truth — not the redirect.** Add `POST /stripe/webhook/`
   (verify the signature with `STRIPE_WEBHOOK_SECRET`) and handle:
   - `checkout.session.completed` → mark membership **active**; store `stripe_customer_id` + `stripe_subscription_id`.
   - `customer.subscription.updated` / `.deleted` → sync status (active / past_due / canceled) + `current_period_end`.
   - `invoice.payment_failed` → mark **past_due**, notify the member.
7. Profile shows **Plan / Status / Renews** (next billing date), exactly like the Tasks app.

## 2. Manage billing (update card, view invoices, cancel)

- **"Manage billing"** button → server creates a **Stripe Billing/Customer Portal** session
  (`stripe.billing_portal.Session.create(customer=…, return_url=profile_url)`) → redirect.
- The Portal handles **update payment method, invoices, and cancellation** — no custom billing UI
  to build. (This is the purple "Manage billing" button in the Tasks app.)

## 3. The member profile page (`/accounts/profile/`) — mirror the Tasks app layout

- **Account:** Username · Email · Member since · buttons: *Edit username & email*, *Change password* (allauth).
- **Membership / Subscription:** Plan ($20/mo) · Status (Active / Past due / Canceled) · Renews (date) ·
  **Manage billing** (Portal). (Replaces the Tasks app's "AI usage" card.)
- **Profile details (the CEO's requested fields):** display name, **City** (used to match them to a
  local Dot), **Phone number** (E.164) + checkbox **"Text me about my Dot"** (explicit SMS consent).
- **My Dot:** the Dot they belong to, its weekly night/location — or their waitlist status if none yet.
- **Help & Support.**

## 4. Data model (sketch)

- `Profile` (OneToOne `User`): display_name, city, phone (E.164), sms_opt_in (bool),
  stripe_customer_id, stripe_subscription_id, membership_status, current_period_end,
  role (`member` / `ambassador` / `admin`).
- `Dot`: name, city, location (address + optional lat/lng), meeting_night, meeting_time,
  ambassador (FK User), capacity (~8–12), status (forming / active / full), description.
- `Membership` (or fields on Profile): status, current_period_end, price_id.
- `Waitlist`: first_name, email, city, intent (`join` / `start`) — from the home-page form.

## 5. Dots finder + ambassadors

- **`/dots/`** — search by city/zip → list nearby Dots (map optional later). If none: offer the
  waitlist ("we'll tell you when one forms") or "start a Dot."
- **Ambassador** = `Profile.role='ambassador'`, can create/manage their Dot. **Admin assigns** the role.
- **"Start a Dot"** → Waitlist `intent=start` → admin reviews → promotes to ambassador.

## 6. SMS (phone) — phased, with compliance

- **Now:** capture `phone` + `sms_opt_in` on the profile (don't send yet).
- **Later (own sub-project):** **Twilio** to send. Requires **A2P 10DLC** carrier registration
  (weeks + a small cost), plus consent records and **STOP/HELP** opt-out handling. Don't send a
  single text before that's done.

## 7. Recommended Django stack

- **django-allauth** (signup/login/password/email) · **Stripe Python SDK** (+ optional **dj-stripe**
  to sync Stripe objects) · **Postgres** · Heroku or similar. Stripe **Checkout + Customer Portal**
  (hosted) so you build almost no billing UI.
- **Pricing by country** (the design mentions it): use Stripe's adaptive pricing / multiple Prices —
  configured in the Stripe dashboard, not in code.

## 8. Security & compliance (do not skip)

- Never store card data — hosted Checkout/Portal keep you at **SAQ-A**.
- **Verify webhook signatures.** Live keys only in env vars (never in the repo or a shared doc).
- CSRF on all forms; HTTPS only; sessions secured.
- SMS: consent + STOP/HELP before sending. Publish **/privacy/** and **/terms/** (the home page links them).

## 9. Carry over from the current site — do NOT rebuild from zero

The live Node/Heroku site already has a **working funnel** worth preserving in Django:
- **Email capture → MailerLite** (owned list, `source` tag per site).
- **Resend welcome emails** — two on-brand templates (`welcome-email.html` for thedotx,
  `welcome-abelcalderon.html` "My Path to Me" for abelcalderon.com), personalized, → Skool.
- **abelcalderon.com** cross-site signup integration (CORS + source).
- Brand/voice, **llms.txt**, the **About** page, AI-discoverability, and the **Ask-AI** blocks.

**Two options in Django:** (a) have Django POST new signups to the existing Node `/api/subscribe`
endpoint (fastest — reuse what works), or (b) re-implement the MailerLite + Resend calls natively in
Django. Either way, the two welcome emails and brand content should migrate, not be reinvented.

## 10. Open decisions for the CEO (flagging these honestly)

1. **Does Django replace the current Node site?** If yes: plan the migration + domain cutover
   deliberately so the live funnel and brand don't get orphaned. (Recommend: keep Node live until
   Django is ready, then cut over.)
2. **Stewardship/integrity flag — the charge-before-a-Dot question.** If someone in a city with **no
   Dot yet** pays $20/mo, what are they paying for? Charging for a local circle that doesn't exist
   would violate our own stewardship/integrity standard. Options: (a) $20/mo includes the online
   community + weekly reflections for everyone, and a local Dot *when available* (honest — you get
   value day one); or (b) don't charge until they can actually join a Dot (waitlist is free). **Pick
   (a) or (b) and state it plainly on the join page.** This is a values decision, not just UX.
3. **Pricing by country:** yes/no.
4. **SMS:** confirm phased (collect now, send later via Twilio).
