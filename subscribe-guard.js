// Protection for the public sign-up form: email verification codes, rate limits, captcha (Google reCAPTCHA v3).
//
// Verification is stateless. When someone asks to join, we email them a 6-digit code and
// hand the browser a signed token carrying their details. The code is never stored: the
// token's signature can only be reproduced with the right code, so checking a code means
// re-computing the signature. Nothing is added to the list until that check passes.
const crypto = require('crypto');

const CODE_TTL_MS = 15 * 60 * 1000;
const MAX_CODE_ATTEMPTS = 6;

function b64url(buf) {
  return Buffer.from(buf).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function unb64url(str) {
  return Buffer.from(String(str).replace(/-/g, '+').replace(/_/g, '/'), 'base64');
}

function createGuard(options) {
  const secret = options.secret;
  const now = options.now || (() => Date.now());
  const tokens = new Map();     // token id -> { exp, tries, used }
  const hits = new Map();       // rate-limit key -> recent timestamps

  function sign(body, code) {
    return b64url(crypto.createHmac('sha256', secret).update('code:' + body + '.' + code).digest());
  }
  // A second signature that does not depend on the code: proves we issued this token,
  // so its contents can be trusted (for example, to send that address a fresh code).
  function seal(body) {
    return b64url(crypto.createHmac('sha256', secret).update('body:' + body).digest());
  }
  function same(a, b) {
    const x = Buffer.from(String(a)), y = Buffer.from(String(b));
    return x.length === y.length && crypto.timingSafeEqual(x, y);
  }

  function tidy() {
    const t = now();
    for (const [id, state] of tokens) if (state.exp < t) tokens.delete(id);
  }

  /** Start a verification: returns the 6-digit code to email and the token for the browser. */
  function issue(details) {
    const code = String(crypto.randomInt(0, 1000000)).padStart(6, '0');
    const payload = Object.assign({}, details, { x: now() + CODE_TTL_MS, k: b64url(crypto.randomBytes(9)) });
    const body = b64url(JSON.stringify(payload));
    return { code, token: [body, sign(body, code), seal(body)].join('.') };
  }

  /** The details inside a token we issued, or null if it is malformed or not ours. */
  function read(token) {
    try {
      const parts = String(token || '').split('.');
      if (parts.length !== 3 || !same(parts[2], seal(parts[0]))) return null;
      const payload = JSON.parse(unb64url(parts[0]).toString('utf8'));
      return payload && typeof payload === 'object' && payload.k ? payload : null;
    } catch (e) { return null; }
  }

  /** Whether a genuine token can still be used: 'open', 'used', 'expired', or 'invalid'. */
  function status(token) {
    const payload = read(token);
    if (!payload) return 'invalid';
    if (!(payload.x > now())) return 'expired';
    return (tokens.get(payload.k) || {}).used ? 'used' : 'open';
  }

  /** Check a code against a token. Each token allows a few guesses and works once. */
  function redeem(token, code) {
    tidy();
    const payload = read(token);
    if (!payload) return { ok: false, reason: 'invalid' };
    if (!(payload.x > now())) return { ok: false, reason: 'expired' };
    const parts = String(token).split('.');
    const state = tokens.get(payload.k) || { exp: payload.x, tries: 0, used: false };
    tokens.set(payload.k, state);
    if (state.used) return { ok: false, reason: 'used' };
    if (state.tries >= MAX_CODE_ATTEMPTS) return { ok: false, reason: 'locked' };
    if (!same(parts[1], sign(parts[0], String(code || '').replace(/\D/g, '')))) {
      state.tries += 1;
      return { ok: false, reason: state.tries >= MAX_CODE_ATTEMPTS ? 'locked' : 'wrong' };
    }
    state.used = true;
    return { ok: true, details: payload };
  }

  /** True if this key (an IP, an email) is still under `max` events per `windowMs`. Counts the event. */
  function allow(key, max, windowMs) {
    const t = now();
    const recent = (hits.get(key) || []).filter((stamp) => stamp > t - windowMs);
    if (recent.length >= max) { hits.set(key, recent); return false; }
    recent.push(t);
    hits.set(key, recent);
    if (hits.size > 20000) for (const k of hits.keys()) { hits.delete(k); if (hits.size < 10000) break; }
    return true;
  }

  return { issue, read, status, redeem, allow };
}

/**
 * Ask Google reCAPTCHA (v3) whether a visitor looks human.
 * v3 is invisible: Google returns a score from 0.0 (bot) to 1.0 (human) and we require a
 * minimum. Returns true/false. If Google itself can't be reached we let the request
 * through, because the emailed code still stands between a bot and the list.
 */
async function captchaPasses(secretKey, responseToken, ip, options) {
  const opts = options || {};
  const minScore = typeof opts.minScore === 'number' ? opts.minScore : 0.5;
  if (!responseToken) return false;
  try {
    const r = await (opts.fetchImpl || fetch)('https://www.google.com/recaptcha/api/siteverify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ secret: secretKey, response: String(responseToken), remoteip: ip || '' }),
    });
    const data = await r.json();
    if (!data || !data.success) return false;
    if (typeof data.score === 'number' && data.score < minScore) return false;
    if (opts.action && data.action && data.action !== opts.action) return false;
    return true;
  } catch (e) {
    console.error('[captcha] could not reach Google reCAPTCHA:', e.message);
    return true;
  }
}

module.exports = { createGuard, captchaPasses, CODE_TTL_MS, MAX_CODE_ATTEMPTS };
