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
let WELCOME_HTML = '';
try {
  WELCOME_HTML = fs.readFileSync(path.join(__dirname, 'content', 'email', 'welcome-email.html'), 'utf8');
} catch (e) { console.error('[welcome] template not loaded:', e.message); }

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

async function sendWelcomeEmail(email, name) {
  const key = process.env.RESEND_API_KEY;
  if (!key || !WELCOME_HTML) return;
  const firstRaw = name || 'friend';
  const logo = process.env.WELCOME_LOGO_URL || 'https://www.thedotx.com/assets/hero-poster.jpg';
  const unsub = process.env.WELCOME_UNSUBSCRIBE_URL || 'mailto:info@thedotcomexperience.com?subject=Unsubscribe';
  const html = WELCOME_HTML
    .split('LOGO_URL').join(logo)
    .split('{$name}').join(escapeHtml(firstRaw))
    .split('{$unsubscribe}').join(unsub);
  const from = process.env.WELCOME_FROM || 'The Dot Com Experience <info@thedotcomexperience.com>';
  const subject = 'Welcome to the Experience' + (name ? ', ' + firstRaw : '');
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
async function addToMailerLite(email, name, source) {
  const key = process.env.MAILERLITE_API_KEY;
  if (!key) return;
  const body = { email };
  const fields = {};
  if (name) fields.name = name;
  if (source) fields.source = source;               // which site the signup came from
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

app.post('/api/subscribe', async (req, res) => {
  const email = ((req.body && req.body.email) || '').toString().trim().toLowerCase();
  const name = ((req.body && req.body.name) || '').toString().trim().slice(0, 100);
  const source = ((req.body && req.body.source) || 'thedotx.com').toString().trim().slice(0, 60);
  if (!EMAIL_RE.test(email) || email.length > 254) {
    return res.status(400).json({ ok: false, error: 'Please enter a valid email.' });
  }
  try { fs.appendFileSync(SUBSCRIBE_FILE, `${new Date().toISOString()},${email},${name},${source}\n`); } catch (e) { /* best-effort */ }
  console.log('[subscribe]', email, name ? '(' + name + ')' : '', 'src:' + source);

  // Fan out: add to the list provider(s) AND send the welcome email (all run if set).
  await Promise.allSettled([
    addToMailerLite(email, name, source),
    addToFlodesk(email, name),
    postWebhook(email, name),
    sendWelcomeEmail(email, name),
  ]);

  // Always acknowledge the visitor; the email is logged even if a provider hiccups.
  return res.json({ ok: true });
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
