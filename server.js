// The Dot Com Experience — front door web server (static site for Heroku).
// Serves the contents of /web. Binds to Heroku's $PORT.
const express = require('express');
const path = require('path');

const app = express();
const ROOT = path.join(__dirname, 'web');

// Force HTTPS + canonical host (www) in production (behind Heroku's proxy).
app.enable('trust proxy');
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

// Serve static files (index.html, assets, robots.txt, sitemap.xml, llms.txt).
app.use(express.static(ROOT, { extensions: ['html'], maxAge: '1h' }));

// Anything else → home.
app.use((req, res) => res.redirect('/'));

const port = process.env.PORT || 3000;
app.listen(port, () => console.log('The Dot Com Experience listening on :' + port));
