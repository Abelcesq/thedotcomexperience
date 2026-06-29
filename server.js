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

// Force HTTPS + canonical host (www) in production (behind Heroku's proxy).
app.use((req, res, next) => {
  if (process.env.NODE_ENV === 'production') {
    const proto = req.headers['x-forwarded-proto'];
    const host = req.headers.host || '';
    if (proto && proto !== 'https') {
      return res.redirect(301, 'https://' + host + req.url);
    }
    if (host === 'thedotx.com') {
      return res.redirect(301, 'https://www.thedotx.com' + req.url);
    }
  }
  next();
});

// --- Email capture -------------------------------------------------------
// Durable + owned: set the SUBSCRIBE_WEBHOOK config var to an endpoint that stores
// the email (Formspree, a Google Apps Script URL, a Zapier/Make webhook, Mailchimp,
// etc.). Without it, the email is still validated and logged (visible in `heroku logs`)
// and appended to a local CSV — but note Heroku's filesystem is EPHEMERAL, so the CSV
// is lost on restart/redeploy. Set SUBSCRIBE_WEBHOOK for real, durable capture.
const SUBSCRIBE_FILE = process.env.SUBSCRIBE_FILE || path.join(os.tmpdir(), 'subscribers.csv');
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

app.post('/api/subscribe', async (req, res) => {
  const email = ((req.body && req.body.email) || '').toString().trim().toLowerCase();
  if (!EMAIL_RE.test(email) || email.length > 254) {
    return res.status(400).json({ ok: false, error: 'Please enter a valid email.' });
  }
  const row = `${new Date().toISOString()},${email}\n`;
  try { fs.appendFileSync(SUBSCRIBE_FILE, row); } catch (e) { /* best-effort */ }
  console.log('[subscribe]', email);

  const hook = process.env.SUBSCRIBE_WEBHOOK;
  if (hook) {
    try {
      const r = await fetch(hook, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ email, source: 'thedotx.com' }),
      });
      if (!r.ok) console.error('[subscribe] webhook returned', r.status);
    } catch (e) {
      console.error('[subscribe] webhook error:', e.message);
      // Still acknowledge to the visitor; the email is in the logs/CSV.
    }
  }
  return res.json({ ok: true });
});

// Serve static files (index.html, assets, robots.txt, sitemap.xml, llms.txt).
app.use(express.static(ROOT, { extensions: ['html'], maxAge: '1h' }));

// Anything else → home.
app.use((req, res) => res.redirect('/'));

const port = process.env.PORT || 3000;
app.listen(port, () => console.log('The Dot Com Experience listening on :' + port));
