# hockeynetworkusa.com

Static site about Utah hockey: Utah Mammoth weekly reports and schedule, rinks, youth and adult hockey, learn to skate.

- `content/articles/*.html` – articles (front matter + HTML body). `section:` is mammoth, youth, adult, skate or rinks.
- `content/pages/*.html` – about, advertise, disclosure, privacy
- `data/mammoth.json` – schedule, results, standings (written by the updater) and hand-kept `key_dates`
- `data/rinks.json` – Utah rink directory
- `site.json` – site settings, AdSense ID, newsletter form, affiliate links, local sponsors (empty = hidden)
- `templates/base.html`, `static/` – layout, CSS, favicon
- `build.py` – zero-dependency builder, writes `public/`
- `scripts/update_mammoth.py` – pulls the NHL public API, saves data, writes the Monday weekly report
- `.github/workflows/update.yml` – runs the updater and build every morning and commits the result
- `.github/workflows/traffic.yml` + `scripts/traffic_snapshot.py` – weekly Cloudflare traffic to `data/traffic.json` (secrets CF_API_TOKEN, CF_ZONE_ID)

Build: `python3 build.py`. Host: Cloudflare Workers static assets (`wrangler.jsonc` serves `public/`, prebuilt and committed). Deploy command: `npx wrangler deploy`, no build command.

Shortcodes: `{{affiliate:tickets|gear|skates|sticks|fan}}`, `{{ad}}`, `{{newsletter}}`, `{{sponsor}}`, `{{next_game}}`.
Mark an article `draft: true` to hide it, `featured: true` to pin it first.
