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

// Push a subscriber into Flodesk via its API. Best-effort; logs the outcome.
async function addToFlodesk(email) {
  const key = process.env.FLODESK_API_KEY;
  if (!key) return;
  // Flodesk uses HTTP Basic auth with the API key as the username.
  const auth = 'Basic ' + Buffer.from(key + ':').toString('base64');
  const headers = { Authorization: auth, 'Content-Type': 'application/json' };
  try {
    // Upsert the subscriber (creates or updates by email).
    const r = await fetch('https://api.flodesk.com/v1/subscribers', {
      method: 'POST', headers, body: JSON.stringify({ email }),
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

// POST to a generic webhook (Zapier/Make/Formspree/etc.). Best-effort.
async function postWebhook(email) {
  const hook = process.env.SUBSCRIBE_WEBHOOK;
  if (!hook) return;
  try {
    const r = await fetch(hook, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify({ email, source: 'thedotx.com' }),
    });
    if (!r.ok) console.error('[subscribe] webhook returned', r.status);
  } catch (e) {
    console.error('[subscribe] webhook error:', e.message);
  }
}

app.post('/api/subscribe', async (req, res) => {
  const email = ((req.body && req.body.email) || '').toString().trim().toLowerCase();
  if (!EMAIL_RE.test(email) || email.length > 254) {
    return res.status(400).json({ ok: false, error: 'Please enter a valid email.' });
  }
  try { fs.appendFileSync(SUBSCRIBE_FILE, `${new Date().toISOString()},${email}\n`); } catch (e) { /* best-effort */ }
  console.log('[subscribe]', email);

  // Fan out to whatever destinations are configured (both run if set).
  await Promise.allSettled([addToFlodesk(email), postWebhook(email)]);

  // Always acknowledge the visitor; the email is logged even if a provider hiccups.
  return res.json({ ok: true });
});

// Serve static files (index.html, assets, robots.txt, sitemap.xml, llms.txt).
app.use(express.static(ROOT, { extensions: ['html'], maxAge: '1h' }));

// Anything else → home.
app.use((req, res) => res.redirect('/'));

const port = process.env.PORT || 3000;
app.listen(port, () => console.log('The Dot Com Experience listening on :' + port));
