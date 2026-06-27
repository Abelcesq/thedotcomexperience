# web/ — AI-Discoverable Site Assets (Step 6)

Staging area for the public site's discoverability layer. These files are **drafted now** and
**deployed in Phase 3** (see `../projects/the-dot-com-experience/roadmap.md`), once a domain
and host are chosen.

## What's here
- [`robots.txt`](robots.txt) — welcomes all crawlers incl. AI bots; deploy at web root.
- The canonical [`../llms.txt`](../llms.txt) — AI manifest; also serve at `https://<domain>/llms.txt`.

## Discoverability checklist for the live site (Step 6 requirements)
- [ ] **Clean semantic HTML** — real `<header>/<nav>/<main>/<article>/<footer>`, one `<h1>`,
      logical heading order; content in markup, not baked into images.
- [ ] **Clear meta descriptions** — unique `<title>` + `<meta name="description">` per page.
- [ ] **Open Graph + Twitter cards** — for rich link previews when shared.
- [ ] **`llms.txt` at root** — the AI manifest (already drafted).
- [ ] **`robots.txt` at root** — already drafted; update the Sitemap domain.
- [ ] **`sitemap.xml`** — generate on build.
- [ ] **Structured data (JSON-LD)** — `Organization` / `Brand` schema for the movement.
- [ ] **Fast, accessible, mobile-first** — performance and a11y aid both humans and crawlers.
- [ ] **Canonical URLs + HTTPS** — one canonical home per page.

## Platform-hub decision (deferred to Phase 3, decide with the board)
Candidate stacks to weigh — pick for *quality + low maintenance + AI-readability*, not novelty:
- **Static site** (e.g., Astro/Next static export) on a CDN host — fast, cheap, semantic, secure.
- **No-code/low-code** (e.g., a premium site builder) — fastest to launch, less control.
- **Headless CMS + static front end** — best for a growing content library.

> Security note: whatever the stack, secrets never live in the repo (`.gitignore` enforces a
> baseline). Use a managed host with HTTPS, 2FA, least-privilege tokens, dependency scanning,
> and backups. Full hardening is scoped in roadmap Phase 3.
