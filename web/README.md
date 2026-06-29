# web/ — thedotx.com (the front door)

The owned one-page **front door** for The Dot Com Experience. Its single job: explain the
movement and send the right people to the **Skool** community. This is the middle of the funnel:
`Instagram + X (awareness) → thedotx.com (this page) → Skool (community + events)`.

## What's built
- **`index.html`** — the live front door (cosmic theme, animated sigil + logo video, three-layer
  story, philosophy tenets, and the primary CTA → Skool). ~54KB, self-contained except fonts.
- **`assets/`**
  - `dotx-cosmic-logo.mp4` — the hero cosmic logo animation.
  - `hero-nebula.jpg` — hero background. `hero-poster.jpg` — video poster + social share image.
  - `preview-hero.png` — a rendered preview screenshot (not used by the page).
- **`robots.txt`**, **`sitemap.xml`**, **`llms.txt`** — discoverability (welcomes AI crawlers).

## The one link that matters
Primary CTA → **https://www.skool.com/the-dot-comp-experience-1714/about**
(appears twice: hero "Join us on Skool" and closing "Enter the community").
To change the community URL, edit both `href`s in `index.html`.

## Built-in AI discoverability (Step 6 — done)
- Semantic HTML5 (`<header>`, `<section>`, `<article>`, `<footer>`, one `<h1>`).
- Unique `<title>` + `<meta name="description">`; Open Graph + Twitter cards.
- `<link rel="canonical">`; JSON-LD `Organization` schema (founder, slogan, Skool as `sameAs`).
- `llms.txt`, `robots.txt` (AI bots allowed), `sitemap.xml`.

## How to preview locally
Open `web/index.html` in a browser, or serve it: `python3 -m http.server -d web 8080`
then visit `http://localhost:8080/`. (Fonts load from Google Fonts when online; system fonts
are the fallback.)

## How to deploy (Phase 3 — when ready)
1. Buy/point **thedotx.com** to a static host (Cloudflare Pages, Netlify, GitHub Pages, Vercel).
2. Upload the contents of `web/` to the site root (so `index.html`, `robots.txt`, `sitemap.xml`,
   `llms.txt`, and `assets/` sit at the domain root).
3. Confirm HTTPS, then validate: `/robots.txt`, `/sitemap.xml`, `/llms.txt`, and the rich-link
   preview (paste the URL into a social composer to see the OG card).
4. Optional next: a real video poster export, an email-capture form, and a favicon set.

> Security note: no secrets live in this folder. Keep the host on HTTPS with 2FA; the repo's
> root `.gitignore` enforces a secrets baseline.
