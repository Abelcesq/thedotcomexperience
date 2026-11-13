// The Dot Com Experience — front door web server (static site + email capture) for Heroku.
// Serves the contents of /web. Binds to Heroku's $PORT.
const express = require('express');
const path = require('path');
const fs = require('fs');
const os = require('os');

const app = express();
const ROOT = path.join(__dirname, 'web');

app.enable('trust proxy');
app.use(express.json({ limit: '8kb' }));

// CORS for the public subscribe API so our other sites (e.g. abelcalderon.com) can
// POST to it cross-origin. Only these origins are allowed.
const ALLOWED_ORIGINS = new Set([
  'https://www.thedotx.com', 'https://thedotx.com',
  'https://www.thedotcomexperience.com', 'https://thedotcomexperience.com',
  'https://www.abelcalderon.com', 'https://abelcalderon.com',
]);
app.use('/api/', (req, res, next) => {
  const origin = req.headers.origin;
  if (origin && ALLOWED_ORIGINS.has(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin);
    res.setHeader('Vary', 'Origin');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  }
  if (req.method === 'OPTIONS') return res.sendStatus(204);
  next();
});

// Domains this site answers on. Each bare apex redirects to its own "www" host.
// (Both domains serve the same site; the <link rel="canonical"> in index.html
// points search engines to www.thedotx.com as the single SEO canonical.)
const APEX_HOSTS = new Set(['thedotx.com', 'thedotcomexperience.com']);

// Force HTTPS + apex→www in production (behind Heroku's proxy).
app.use((req, res, next) => {
  if (process.env.NODE_ENV === 'production') {
    const proto = req.headers['x-forwarded-proto'];
    const host = (req.headers.host || '').toLowerCase();
    if (proto && proto !== 'https') {
      return res.redirect(301, 'https://' + host + req.url);
    }
    if (APEX_HOSTS.has(host)) {
      return res.redirect(301, 'https://www.' + host + req.url);
    }
  }
  next();
});

// --- Email capture -------------------------------------------------------
// Signups POST here. We send each email to your owned list. Two ways to wire it,
// set via Heroku config vars (use either / both):
//
//   1) FLODESK (recommended) — set FLODESK_API_KEY (and optionally FLODESK_SEGMENT_ID).
//      The email is upserted into your Flodesk audience (and added to the segment),
//      ready for campaigns. Get the key in Flodesk → Account → Integrations/API.
//
//   2) SUBSCRIBE_WEBHOOK — a generic endpoint (Zapier/Make/Formspree/Apps Script).
//      We POST { email, source } as JSON to it.
//
// Heroku's filesystem is EPHEMERAL, so the local CSV below is only a transient
// fallback for logs/debugging — your real, durable list lives in Flodesk.
const SUBSCRIBE_FILE = process.env.SUBSCRIBE_FILE || path.join(os.tmpdir(), 'subscribers.csv');
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// --- Welcome email, sent by US via Resend (no external editor needed) ----
// Enable by setting RESEND_API_KEY. WELCOME_FROM must be an address on a domain
// you've verified in Resend (e.g. "The Dot Com Experience <hello@thedotx.com>").
// The template is the on-brand HTML in content/email/welcome-email.html.
function loadTemplate(file) {
  try { return fs.readFileSync(path.join(__dirname, 'content', 'email', file), 'utf8'); }
  catch (e) { console.error('[welcome] template not loaded:', file, e.message); return ''; }
}
const WELCOME_HTML = loadTemplate('welcome-email.html');            // The Dot Com Experience (thedotx.com)
const WELCOME_HTML_ABEL = loadTemplate('welcome-abelcalderon.html'); // My Path to Me (abelcalderon.com)

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

async function sendWelcomeEmail(email, name, source) {
  const key = process.env.RESEND_API_KEY;
  if (!key) return;
  // Pick the welcome variant by signup source.
  const isAbel = /abelcalderon/i.test(source || '');
  const template = isAbel && WELCOME_HTML_ABEL ? WELCOME_HTML_ABEL : WELCOME_HTML;
  if (!template) return;
  const firstRaw = name || 'friend';
  const logo = process.env.WELCOME_LOGO_URL || 'https://www.thedotx.com/assets/hero-poster.jpg';
  const unsub = process.env.WELCOME_UNSUBSCRIBE_URL || 'mailto:info@thedotcomexperience.com?subject=Unsubscribe';
  const html = template
    .split('LOGO_URL').join(logo)
    .split('{$name}').join(escapeHtml(firstRaw))
    .split('{$unsubscribe}').join(unsub);
  const from = isAbel
    ? (process.env.WELCOME_FROM_ABEL || 'Abel Calderon · My Path to Me <info@thedotcomexperience.com>')
    : (process.env.WELCOME_FROM || 'The Dot Com Experience <info@thedotcomexperience.com>');
  const subject = (isAbel ? 'Welcome to My Path to Me' : 'Welcome to the Experience') + (name ? ', ' + firstRaw : '');
  try {
    const r = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: { Authorization: 'Bearer ' + key, 'Content-Type': 'application/json' },
      body: JSON.stringify({ from, to: email, subject, html }),
    });
    if (!r.ok) console.error('[welcome] resend returned', r.status, await r.text().catch(() => ''));
    else console.log('[welcome] sent to', email);
  } catch (e) {
    console.error('[welcome] error:', e.message);
  }
}

// Notify the admin (you) of every new opt-in, via Resend. Best-effort.
// Sends to ADMIN_NOTIFY_EMAIL (default info@thedotcomexperience.com). Reply-To is the
// subscriber, so you can reply to them directly from the notification.
async function notifyAdmin(email, name, source, city, intent) {
  const key = process.env.RESEND_API_KEY;
  if (!key) return;
  const to = process.env.ADMIN_NOTIFY_EMAIL || 'info@thedotcomexperience.com';
  const from = process.env.ADMIN_NOTIFY_FROM || process.env.WELCOME_FROM
    || 'The Dot Com Experience <info@thedotcomexperience.com>';
  const rows = [
    ['Email', email], ['Name', name || '—'], ['City', city || '—'],
    ['Intent', intent || '—'], ['Source', source || '—'], ['Time (UTC)', new Date().toISOString()],
  ];
  const html =
    '<div style="font-family:Arial,sans-serif;color:#1a2230">' +
    '<h2 style="margin:0 0 12px">New signup — The Dot Com Experience</h2>' +
    '<table style="border-collapse:collapse;font-size:15px">' +
    rows.map(([k, v]) =>
      `<tr><td style="padding:6px 14px 6px 0;color:#6b7686">${k}</td>` +
      `<td style="padding:6px 0;font-weight:600">${escapeHtml(v)}</td></tr>`).join('') +
    '</table></div>';
  const text = rows.map(([k, v]) => `${k}: ${v}`).join('\n');
  const subject = `New signup: ${email}` + (city ? ' · ' + city : '');
  try {
    const r = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: { Authorization: 'Bearer ' + key, 'Content-Type': 'application/json' },
      body: JSON.stringify({ from, to, reply_to: email, subject, html, text }),
    });
    if (!r.ok) console.error('[notify] resend returned', r.status, await r.text().catch(() => ''));
    else console.log('[notify] admin notified of', email);
  } catch (e) {
    console.error('[notify] error:', e.message);
  }
}

// Push a subscriber into Flodesk via its API. Best-effort; logs the outcome.
async function addToFlodesk(email, name) {
  const key = process.env.FLODESK_API_KEY;
  if (!key) return;
  // Flodesk uses HTTP Basic auth with the API key as the username.
  const auth = 'Basic ' + Buffer.from(key + ':').toString('base64');
  const headers = { Authorization: auth, 'Content-Type': 'application/json' };
  const payload = name ? { email, first_name: name } : { email };
  try {
    // Upsert the subscriber (creates or updates by email).
    const r = await fetch('https://api.flodesk.com/v1/subscribers', {
      method: 'POST', headers, body: JSON.stringify(payload),
    });
    if (!r.ok) { console.error('[flodesk] subscriber upsert returned', r.status); return; }

    // Optionally add to a segment so campaigns can target this audience.
    const seg = process.env.FLODESK_SEGMENT_ID;
    if (seg) {
      const r2 = await fetch(
        'https://api.flodesk.com/v1/subscribers/' + encodeURIComponent(email) + '/segments',
        { method: 'POST', headers, body: JSON.stringify({ segment_ids: [seg] }) }
      );
      if (!r2.ok) console.error('[flodesk] add-to-segment returned', r2.status);
    }
    console.log('[flodesk] added', email);
  } catch (e) {
    console.error('[flodesk] error:', e.message);
  }
}

// Push a subscriber into MailerLite via its API. Best-effort; logs the outcome.
async function addToMailerLite(email, name, source, extra) {
  const key = process.env.MAILERLITE_API_KEY;
  if (!key) return;
  const body = { email };
  const fields = {};
  if (name) fields.name = name;
  if (source) fields.source = source;               // which site the signup came from
  if (extra && extra.city) fields.city = extra.city;        // for Dot (local circle) matching
  if (extra && extra.intent) fields.intent = extra.intent;  // join | start a Dot
  if (Object.keys(fields).length) body.fields = fields;
  if (process.env.MAILERLITE_GROUP_ID) body.groups = [process.env.MAILERLITE_GROUP_ID];
  try {
    const r = await fetch('https://connect.mailerlite.com/api/subscribers', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer ' + key,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(body),
    });
    if (!r.ok) console.error('[mailerlite] returned', r.status);
    else console.log('[mailerlite] added', email);
  } catch (e) {
    console.error('[mailerlite] error:', e.message);
  }
}

// POST to a generic webhook (Zapier/Make/Formspree/etc.). Best-effort.
async function postWebhook(email, name) {
  const hook = process.env.SUBSCRIBE_WEBHOOK;
  if (!hook) return;
  try {
    const r = await fetch(hook, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify({ email, name: name || '', source: 'thedotx.com' }),
    });
    if (!r.ok) console.error('[subscribe] webhook returned', r.status);
  } catch (e) {
    console.error('[subscribe] webhook error:', e.message);
  }
}

// --- Sign-up protection ---------------------------------------------------
// Bots were posting made-up addresses here, and each one triggered a welcome email, a
// list entry and an admin notification. Now a sign-up only counts once the person has
// typed the 6-digit code we email them. In front of that: a hidden-field bot trap, an
// Google reCAPTCHA “I’m not a robot” checkbox (v2), and rate limits.
//
// Config vars (all optional):
//   RECAPTCHA_SITE_KEY + RECAPTCHA_SECRET_KEY — a reCAPTCHA v2 “Checkbox” key pair. Both must be
//       set for the checkbox to appear. Keep the secret key in config vars only, never in code.
//   CAPTCHA_EXEMPT_ORIGINS — sites allowed to post without a captcha (default: abelcalderon.com,
//       whose form has no reCAPTCHA yet). Remove the exemption once that form has one.
//   SUBSCRIBE_SECRET — signing key for verification tokens (defaults to one derived from RESEND_API_KEY).
//   SUBSCRIBE_VERIFY=off — turn the emailed code off (not recommended).
const crypto = require('crypto');
const { createGuard, captchaPasses } = require('./subscribe-guard');

const SIGNING_SECRET = process.env.SUBSCRIBE_SECRET
  || (process.env.RESEND_API_KEY
    ? crypto.createHash('sha256').update('subscribe:' + process.env.RESEND_API_KEY).digest('hex')
    : crypto.randomBytes(32).toString('hex'));
const guard = createGuard({ secret: SIGNING_SECRET });
const SITE_BASE_URL = (process.env.SITE_BASE_URL || 'https://www.thedotx.com').replace(/\/+$/, '');
const CAPTCHA_EXEMPT_ORIGINS = new Set((process.env.CAPTCHA_EXEMPT_ORIGINS
  || 'https://www.abelcalderon.com,https://abelcalderon.com').split(',').map((o) => o.trim()).filter(Boolean));

const RECAPTCHA_SITE_KEY = process.env.RECAPTCHA_SITE_KEY || '';
function captchaOn() { return !!(RECAPTCHA_SITE_KEY && process.env.RECAPTCHA_SECRET_KEY); }

const MINUTE = 60 * 1000;
function verificationEnabled() {
  return !!process.env.RESEND_API_KEY && (process.env.SUBSCRIBE_VERIFY || '').toLowerCase() !== 'off';
}
function clientIp(req) { return req.ip || 'unknown'; }

async function sendCodeEmail(details, code, token) {
  const isAbel = /abelcalderon/i.test(details.s || '');
  const from = isAbel
    ? (process.env.WELCOME_FROM_ABEL || 'Abel Calderon · My Path to Me <info@thedotcomexperience.com>')
    : (process.env.WELCOME_FROM || 'The Dot Com Experience <info@thedotcomexperience.com>');
  const link = SITE_BASE_URL + '/confirm?t=' + encodeURIComponent(token) + '&c=' + code;
  const brand = isAbel ? 'My Path to Me' : 'The Dot Com Experience';
  const html = '<div style="font-family:Georgia,serif;max-width:480px;margin:0 auto;padding:32px 24px;color:#1a2230">'
    + '<p style="font-size:16px;margin:0 0 18px">' + (details.n ? 'Hi ' + escapeHtml(details.n) + ',' : 'Hello,') + '</p>'
    + '<p style="font-size:16px;margin:0 0 18px">Here is your code to confirm your email with ' + brand + ':</p>'
    + '<p style="font-size:34px;letter-spacing:8px;font-weight:bold;margin:0 0 18px">' + code + '</p>'
    + '<p style="font-size:15px;margin:0 0 22px">Type it into the page where you signed up, or '
    + '<a href="' + link + '" style="color:#8a6a1c">confirm with one click</a>. The code works for 15 minutes.</p>'
    + '<p style="font-size:13px;color:#6b7686;margin:0">If you didn&rsquo;t ask for this, ignore this email — nothing will be sent to you.</p></div>';
  const r = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + process.env.RESEND_API_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ from, to: details.e, subject: code + ' is your ' + brand + ' confirmation code', html }),
  });
  if (!r.ok) throw new Error('resend returned ' + r.status + ' ' + (await r.text().catch(() => '')));
}

// The real sign-up: record it, add it to the list, welcome them, tell the admin.
async function completeSignup(details) {
  const email = details.e, name = details.n || '', source = details.s || 'thedotx.com';
  const city = details.c || '', intent = details.i || '';
  try { fs.appendFileSync(SUBSCRIBE_FILE, `${new Date().toISOString()},${email},${name},${source},${city},${intent}\n`); } catch (e) { /* best-effort */ }
  console.log('[subscribe] confirmed', email, name ? '(' + name + ')' : '', 'src:' + source, city ? 'city:' + city : '', intent ? 'intent:' + intent : '');
  await Promise.allSettled([
    addToMailerLite(email, name, source, { city, intent }),
    addToFlodesk(email, name),
    postWebhook(email, name),
    sendWelcomeEmail(email, name, source),
    notifyAdmin(email, name, source, city, intent),
  ]);
}

// The public pages ask this which captcha key to show (the site key is not a secret).
app.get('/api/config', (req, res) => {
  res.setHeader('Cache-Control', 'public, max-age=300');
  res.json({
    recaptchaSiteKey: captchaOn() ? RECAPTCHA_SITE_KEY : '',
    verify: verificationEnabled(),
  });
});

app.post('/api/subscribe', async (req, res) => {
  const body = req.body || {};
  const email = (body.email || '').toString().trim().toLowerCase();
  const name = (body.name || '').toString().trim().slice(0, 100);
  const source = (body.source || 'thedotx.com').toString().trim().slice(0, 60);
  const city = (body.city || '').toString().trim().slice(0, 120);
  const intent = (body.intent || '').toString().trim().slice(0, 20);
  if (!EMAIL_RE.test(email) || email.length > 254) {
    return res.status(400).json({ ok: false, error: 'Please enter a valid email.' });
  }
  // Bot trap: people never see this field, so anything in it means a script filled the form.
  // Answer as if it worked so the bot learns nothing.
  if ((body.website || '').toString().trim()) {
    console.log('[subscribe] bot trap caught', clientIp(req));
    return res.json({ ok: true });
  }
  if (!guard.allow('ip:' + clientIp(req), 8, 10 * MINUTE)) {
    return res.status(429).json({ ok: false, error: 'Too many attempts. Please wait a few minutes and try again.' });
  }
  if (captchaOn() && !CAPTCHA_EXEMPT_ORIGINS.has(req.headers.origin || '')) {
    const human = await captchaPasses(process.env.RECAPTCHA_SECRET_KEY, body.captcha, clientIp(req));
    if (!human) {
      return res.status(400).json({ ok: false, captcha: true,
        error: 'Please tick the “I’m not a robot” box and try again.' });
    }
  }
  const details = { e: email, n: name, s: source, c: city, i: intent };
  if (!verificationEnabled()) {          // no way to email a code (e.g. local development)
    await completeSignup(details);
    return res.json({ ok: true });
  }
  // One code per address every so often, and a ceiling on codes sent without a captcha.
  if (!guard.allow('email:' + email, 3, 15 * MINUTE)
      || (!captchaOn() && !guard.allow('codes:nocaptcha', 120, 60 * MINUTE))) {
    return res.status(429).json({ ok: false, error: 'We just sent a code to that address. Please check your inbox (and spam folder).' });
  }
  const { code, token } = guard.issue(details);
  try {
    await sendCodeEmail(details, code, token);
  } catch (e) {
    console.error('[subscribe] could not send code:', e.message);
    return res.status(502).json({ ok: false, error: 'We couldn’t send your confirmation email. Please try again in a moment.' });
  }
  console.log('[subscribe] code sent to', email, 'src:' + source);
  return res.json({ ok: true, verify: true, token });
});

app.post('/api/subscribe/verify', async (req, res) => {
  const body = req.body || {};
  if (!guard.allow('verify:' + clientIp(req), 30, 10 * MINUTE)) {
    return res.status(429).json({ ok: false, error: 'Too many attempts. Please wait a few minutes and try again.' });
  }
  const result = guard.redeem(body.token, body.code);
  if (!result.ok) {
    const messages = {
      wrong: 'That code doesn’t match. Please check it and try again.',
      expired: 'That code has expired. Please ask for a new one.',
      locked: 'Too many wrong codes. Please ask for a new one.',
      used: 'This email is already confirmed — you’re on the list.',
    };
    return res.status(result.reason === 'used' ? 200 : 400)
      .json({ ok: result.reason === 'used', reason: result.reason, error: messages[result.reason] || 'That link or code isn’t valid. Please sign up again.' });
  }
  await completeSignup(result.details);
  return res.json({ ok: true, intent: result.details.i || '' });
});

app.post('/api/subscribe/resend', async (req, res) => {
  // Only for a token we issued ourselves (its signature is checked) that hasn't been used.
  const oldToken = (req.body || {}).token;
  const previous = guard.read(oldToken);
  const state = guard.status(oldToken);
  if (!previous || !verificationEnabled() || state === 'invalid' || state === 'used') {
    return res.status(400).json({ ok: false, error: 'Please sign up again.' });
  }
  if (!guard.allow('ip:' + clientIp(req), 8, 10 * MINUTE) || !guard.allow('email:' + previous.e, 3, 15 * MINUTE)) {
    return res.status(429).json({ ok: false, error: 'Please wait a few minutes before asking for another code.' });
  }
  const details = { e: previous.e, n: previous.n, s: previous.s, c: previous.c, i: previous.i };
  const { code, token } = guard.issue(details);
  try {
    await sendCodeEmail(details, code, token);
  } catch (e) {
    console.error('[subscribe] could not re-send code:', e.message);
    return res.status(502).json({ ok: false, error: 'We couldn’t send the email. Please try again in a moment.' });
  }
  return res.json({ ok: true, verify: true, token });
});

// Serve static files (index.html, assets, robots.txt, sitemap.xml, llms.txt).
app.use(express.static(ROOT, {
  extensions: ['html'],
  setHeaders: (res, filePath) => {
    // HTML: always revalidate so deploys show immediately. Assets: cache 1h.
    if (filePath.endsWith('.html')) res.setHeader('Cache-Control', 'no-cache');
    else res.setHeader('Cache-Control', 'public, max-age=3600');
  },
}));

// Anything else → home.
app.use((req, res) => res.redirect('/'));

const port = process.env.PORT || 3000;
app.listen(port, () => console.log('The Dot Com Experience listening on :' + port));
