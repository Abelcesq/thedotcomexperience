# Spam protection, email codes and two-step verification — setup

Everything here is built and deployed, but two pieces wait for a config var before
they switch on. Config vars live in Heroku → the app → Settings → Reveal Config Vars.

## What protects what

| Protection | Home site form (`thadotx`) | Member signup + Dot forms (`thedotx-members`) | Switches on when |
| --- | --- | --- | --- |
| Emailed 6-digit code | Yes | Yes (signup) | Home: already on. Members: `RESEND_API_KEY` is set |
| Google reCAPTCHA v3 (invisible) | Yes | Yes | `RECAPTCHA_SECRET_KEY` is set on that app |
| Hidden bot-trap field | Yes | Yes | Always on |
| Rate limits | Yes | Yes (built into sign-in) | Always on |
| Two-step verification (Google Authenticator) | — | Offered to every member | Always available; needs a confirmed email |

## Config vars to add

**App `thadotx` (home site)**

| Key | Value |
| --- | --- |
| `RECAPTCHA_SECRET_KEY` | The *secret key* from the Google reCAPTCHA admin page |

**App `thedotx-members` (member site)**

| Key | Value |
| --- | --- |
| `RECAPTCHA_SECRET_KEY` | The same secret key |
| `RESEND_API_KEY` | Copy the value of `RESEND_API_KEY` from the `thadotx` app |
| `DEFAULT_FROM_EMAIL` | Optional. Only if `thadotx` has a `WELCOME_FROM` value: copy it here so both sites send from the same address |

The reCAPTCHA *site* key is public and already in the code. The *secret* key must only
ever be in config vars.

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

- Allowed domains at Google must include every address the forms are served from:
  `www.thedotx.com`, `members.thedotx.com`, `www.thedotcomexperience.com`.
- v3 has no checkbox. Google scores each visitor from 0.0 (bot) to 1.0 (human) and the site
  requires 0.5. If real people are being refused, lower it with `RECAPTCHA_MIN_SCORE`
  (for example `0.3`) on that app.
- The form on abelcalderon.com has no reCAPTCHA yet, so the home site lets that one origin
  through without it (it still needs the emailed code).
