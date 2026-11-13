# Spam protection, email codes and two-step verification — setup

Everything here is built and deployed, but two pieces wait for a config var before
they switch on. Config vars live in Heroku → the app → Settings → Reveal Config Vars.

## What protects what

| Protection | Home site form (`thadotx`) | Member signup, login + Dot forms (`thedotx-members`) | Switches on when |
| --- | --- | --- | --- |
| Emailed 6-digit code | Yes | Yes (signup) | Home: already on. Members: `RESEND_API_KEY` is set |
| Google reCAPTCHA “I’m not a robot” checkbox | Yes | Yes | Both `RECAPTCHA_SITE_KEY` and `RECAPTCHA_SECRET_KEY` are set on that app |
| Hidden bot-trap field | Yes | Yes | Always on |
| Rate limits | Yes | Yes (built into sign-in) | Always on |
| Two-step verification (Google Authenticator) | — | Offered to every member | Always available; needs a confirmed email |

## Step 1 — Create a checkbox key at Google

The checkbox needs a reCAPTCHA **v2 “I’m not a robot” Checkbox** key. A v3 key (the
invisible, score-based kind) will not work for it: keys are tied to their type.

1. Go to google.com/recaptcha/admin and press **+** (Create).
2. Label: `the dot checkbox`. Type: **Challenge (v2)** → **“I’m not a robot” Checkbox**.
3. Domains: `www.thedotx.com`, `members.thedotx.com`, `www.thedotcomexperience.com`.
4. Submit, then copy the **site key** and the **secret key**.

## Step 2 — Config vars to add

Add the same two reCAPTCHA values to both apps.

**App `thadotx` (home site)**

| Key | Value |
| --- | --- |
| `RECAPTCHA_SITE_KEY` | The v2 *site key* |
| `RECAPTCHA_SECRET_KEY` | The v2 *secret key* |

**App `thedotx-members` (member site)**

| Key | Value |
| --- | --- |
| `RECAPTCHA_SITE_KEY` | The v2 *site key* |
| `RECAPTCHA_SECRET_KEY` | The v2 *secret key* |
| `RESEND_API_KEY` | Copy the value of `RESEND_API_KEY` from the `thadotx` app |
| `DEFAULT_FROM_EMAIL` | Optional. Only if `thadotx` has a `WELCOME_FROM` value: copy it here so both sites send from the same address |

The two reCAPTCHA keys must come from the same key pair. A site key paired with a secret
key from a different key (for example the earlier v3 one) makes every sign-up fail the
check. The checkbox appears only when both are set; with either missing, the forms work
without it. The secret key must only ever be in config vars.

## What changes for members once `RESEND_API_KEY` is set

- New accounts get a 6-digit code by email and must enter it before they can sign in.
- Existing accounts that never confirmed their email are asked for a code at their next sign-in.
- "Forgot password" starts working (it could not send email before).
- The Django admin sign-in at `/admin/` is not affected.

## Two-step verification

Members see a prompt on their profile. Setup: profile → Security → Set up → re-enter
password → scan the QR code with Google Authenticator → type the 6-digit code. They are
then shown one-time backup codes to keep somewhere safe; a backup code works in place of
the app if they lose their phone. It is offered, not forced.

If a member is locked out (lost phone and backup codes): Admin → MFA → Authenticators →
delete that member's entries. They can then sign in with their password and set it up again.

## reCAPTCHA notes

- On the login page the checkbox is checked before the password is looked at, so the page
  cannot be used to test stolen passwords. The Django admin sign-in at `/admin/` has no checkbox.

- Allowed domains at Google must include every address the forms are served from:
  `www.thedotx.com`, `members.thedotx.com`, `www.thedotcomexperience.com`.
- Most people just tick the box. Google sometimes follows it with a picture puzzle.
- If a visitor's ad or tracker blocker stops the checkbox from loading, the form tells them
  to switch it off for the page and reload.
- The form on abelcalderon.com has no reCAPTCHA yet, so the home site lets that one origin
  through without it (it still needs the emailed code).
