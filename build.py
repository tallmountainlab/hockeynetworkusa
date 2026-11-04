#!/usr/bin/env python3
"""Build hockeynetworkusa.com into ./public. No dependencies, just Python 3.9+.

Articles live in content/articles/*.html, static pages in content/pages/*.html.
Each file starts with a front-matter block:

    ---
    title: Learn to skate in Utah
    description: One-line summary for Google and social cards.
    date: 2026-10-31
    updated: 2026-10-31
    section: skate            (mammoth | youth | adult | skate | rinks)
    category: Guide
    ---
    <p>Body HTML...</p>

Shortcodes inside the body:
    {{affiliate:tickets}}  -> affiliate box (hidden until its URL is set in site.json)
    {{ad}}                 -> ad slot (hidden until adsense_client_id is set)
    {{newsletter}}         -> newsletter sign-up (hidden until newsletter_form_action is set)
    {{sponsor}}            -> local sponsor strip (hidden until site.json has sponsors)
    {{next_game}}          -> the Mammoth's next game, from data/mammoth.json
"""
import html
import json
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "public"
SITE = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
TEMPLATE = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
MAMMOTH = json.loads((ROOT / "data" / "mammoth.json").read_text(encoding="utf-8"))
RINKS = json.loads((ROOT / "data" / "rinks.json").read_text(encoding="utf-8"))
TODAY = date.today().isoformat()

SECTIONS = {
    "mammoth": {"path": "mammoth", "title": "Utah Mammoth",
                "blurb": "Weekly reports, the full schedule and standings, updated every morning."},
    "youth": {"path": "youth-hockey", "title": "Youth hockey",
              "blurb": "How kids get started in Utah hockey, from the first free clinic to travel teams."},
    "adult": {"path": "adult-hockey", "title": "Adult hockey",
              "blurb": "Rec leagues, drop-in and stick-and-puck for grown-ups, beginners welcome."},
    "skate": {"path": "learn-to-skate", "title": "Learn to skate",
              "blurb": "Lessons and public skating for kids and adults who are starting from zero."},
    "rinks": {"path": "rinks", "title": "Rinks",
              "blurb": "Every sheet of ice we know of in Utah, indoor and outdoor."},
}
NAV = ["mammoth", "rinks", "youth", "adult", "skate"]
esc = html.escape


# ---------- content ----------
def parse(path):
    text = path.read_text(encoding="utf-8")
    meta, body = {}, text
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        for line in fm.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    meta["slug"] = path.stem
    meta["body"] = body.strip()
    meta.setdefault("updated", meta.get("date", ""))
    meta.setdefault("section", "mammoth")
    meta["url"] = f"/{SECTIONS[meta['section']]['path']}/{meta['slug']}/"
    return meta


def fmt_date(s):
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%B %-d, %Y")
    except ValueError:
        return s


def short_date(s):
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%a, %b %-d")
    except ValueError:
        return s


def game_time(g):
    iso = g.get("start_local", "")
    if "T" not in iso:
        return "Time TBD"
    return datetime.fromisoformat(iso).strftime("%-I:%M %p MT").replace(":00 ", " ")


def ordinal(n):
    n = int(n or 0)
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


# ---------- money blocks ----------
def affiliate_box(key):
    aff = SITE.get("affiliates", {}).get(key)
    if not aff or not aff.get("url"):
        return ""
    return ('<aside class="aff"><span class="aff-tag">Partner link</span>'
            f'<a href="{esc(aff["url"])}" rel="sponsored nofollow noopener" target="_blank">'
            f'{esc(aff["label"])} &rarr;</a></aside>')


def ad_slot():
    cid = SITE.get("adsense_client_id")
    if not cid:
        return ""
    return ('<div class="ad"><ins class="adsbygoogle" style="display:block" '
            f'data-ad-client="{esc(cid)}" data-ad-format="auto" data-full-width-responsive="true"></ins>'
            "<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></div>")


def newsletter():
    action = SITE.get("newsletter_form_action")
    if not action:
        return ""
    return ('<section class="news"><h3>Get the Monday Mammoth report by email</h3>'
            "<p>Last week's results, this week's games and what's happening at Utah rinks. Free, once a week.</p>"
            f'<form action="{esc(action)}" method="post" target="_blank">'
            '<input type="email" name="email" placeholder="you@example.com" required aria-label="Email">'
            "<button>Subscribe</button></form></section>")


def sponsor_strip():
    sp = [s for s in SITE.get("sponsors", []) if s.get("name")]
    if not sp:
        return ""
    items = "".join(
        f'<a href="{esc(s.get("url", "#"))}" rel="sponsored noopener" target="_blank">'
        f'<strong>{esc(s["name"])}</strong><span>{esc(s.get("blurb", ""))}</span></a>' for s in sp)
    return f'<aside class="sponsors"><span class="aff-tag">Local sponsors</span><div>{items}</div></aside>'


def next_game_card():
    upcoming = [g for g in MAMMOTH.get("games", []) if g.get("state") != "final" and g.get("date", "") >= TODAY]
    if upcoming:
        g = upcoming[0]
        return ('<div class="nextgame"><span class="kicker">Next Mammoth game</span>'
                f'<strong>{"vs" if g["home"] else "at"} {esc(g["opponent"])}</strong>'
                f'<span>{short_date(g["date"])} · {game_time(g)} · {esc(g.get("venue", ""))}</span>'
                '<a href="/mammoth/">Schedule &amp; standings &rarr;</a></div>')
    keys = [k for k in MAMMOTH.get("key_dates", []) if k["date"] >= TODAY]
    if keys:
        k = keys[0]
        return ('<div class="nextgame"><span class="kicker">Coming up</span>'
                f'<strong>{esc(k["text"])}</strong><span>{fmt_date(k["date"])}</span>'
                '<a href="/mammoth/">Schedule &amp; standings &rarr;</a></div>')
    return ""


def memories():
    e = SITE["contact_email"]
    return ('<aside class="memories"><span class="kicker">Memory lane</span>'
            "<h3>Got a Utah hockey memory?</h3>"
            "<p>A Golden Eagles game at the Salt Palace, a Grizzlies promo night, Olympic hockey in 2002, "
            "a frozen pond, or your kid's first goal. Send it in, with a photo if you have one, "
            "and we may share it here.</p>"
            f'<a class="btn" href="mailto:{e}?subject=My%20Utah%20hockey%20memory">Share your memory</a></aside>')


def shortcodes(body):
    body = re.sub(r"\{\{affiliate:(\w+)\}\}", lambda m: affiliate_box(m.group(1)), body)
    for k, fn in {"ad": ad_slot, "newsletter": newsletter, "sponsor": sponsor_strip, "next_game": next_game_card, "memories": memories}.items():
        body = body.replace("{{" + k + "}}", fn())
    return body


# ---------- page shell ----------
def render(title, description, content, path, extra_head="", active=""):
    head = extra_head
    if SITE.get("adsense_client_id"):
        head += ('<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
                 f'?client={esc(SITE["adsense_client_id"])}" crossorigin="anonymous"></script>')
    nav = "".join(
        f'<a href="/{SECTIONS[k]["path"]}/"{" aria-current=page" if k == active else ""}>{SECTIONS[k]["title"]}</a>'
        for k in NAV)
    full_title = title if title == SITE["name"] else f"{title} | {SITE['name']}"
    out = TEMPLATE
    for k, v in {
        "{{title}}": esc(full_title), "{{description}}": esc(description),
        "{{canonical}}": SITE["url"] + path, "{{site_name}}": SITE["name"],
        "{{tagline}}": esc(SITE["tagline"]), "{{extra_head}}": head, "{{nav}}": nav,
        "{{content}}": content, "{{year}}": str(date.today().year),
        "{{contact_email}}": SITE["contact_email"],
    }.items():
        out = out.replace(k, v)
    return out


def write(rel, text):
    dest = OUT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")


def card(a):
    sec = SECTIONS[a["section"]]["title"]
    return (f'<a class="card s-{a["section"]}" href="{a["url"]}">'
            f'<span class="kicker">{esc(sec)} · {esc(a.get("category", "Guide"))}</span>'
            f'<h3>{esc(a["title"])}</h3><p>{esc(a.get("description", ""))}</p>'
            f'<span class="meta">Updated {fmt_date(a["updated"])}</span></a>')


# ---------- Mammoth hub ----------
def mammoth_panel():
    games = MAMMOTH.get("games", [])
    rec = MAMMOTH.get("record")
    parts = []
    if rec:
        parts.append(
            '<div class="stats">'
            f'<div><b>{rec["w"]}-{rec["l"]}-{rec["otl"]}</b><span>Record</span></div>'
            f'<div><b>{rec["pts"]}</b><span>Points</span></div>'
            f'<div><b>{ordinal(rec["div_rank"])}</b><span>{esc(rec["division"])} Division</span></div>'
            f'<div><b>{esc(rec["l10"])}</b><span>Last 10</span></div>'
            f'<div><b>{esc(rec["streak"])}</b><span>Streak</span></div></div>')
    parts.append(next_game_card())
    finals = [g for g in games if g.get("state") == "final"][-6:][::-1]
    coming = [g for g in games if g.get("state") != "final" and g.get("date", "") >= TODAY][:8]
    if finals:
        parts.append('<h2>Recent results</h2><table class="sched"><tr><th>Date</th><th>Opponent</th><th>Result</th></tr>')
        for g in finals:
            ot = f' ({g["ending"]})' if g.get("ending") in ("OT", "SO") else ""
            parts.append(f'<tr><td>{short_date(g["date"])}</td><td>{"vs" if g["home"] else "at"} {esc(g["opponent"])}</td>'
                         f'<td class="r-{g["result"]}">{g["result"]} {g["us"]}-{g["them"]}{ot}</td></tr>')
        parts.append("</table>")
    if coming:
        parts.append('<h2>Upcoming games</h2><table class="sched"><tr><th>Date</th><th>Opponent</th><th>Puck drop</th></tr>')
        for g in coming:
            parts.append(f'<tr><td>{short_date(g["date"])}</td><td>{"vs" if g["home"] else "at"} {esc(g["opponent"])}</td>'
                         f'<td>{game_time(g)}</td></tr>')
        parts.append("</table>")
    parts.append(affiliate_box("tickets"))
    div = MAMMOTH.get("division", [])
    if div:
        parts.append(f'<h2>{esc(div[0]["division"])} Division</h2><table class="sched"><tr><th></th><th>Team</th>'
                     "<th>GP</th><th>W-L-OTL</th><th>Pts</th></tr>")
        for r in div:
            us = ' class="us"' if r["abbrev"] == SITE.get("team_abbrev") else ""
            parts.append(f'<tr{us}><td>{r["div_rank"]}</td><td>{esc(r["team"])}</td><td>{r["gp"]}</td>'
                         f'<td>{r["w"]}-{r["l"]}-{r["otl"]}</td><td>{r["pts"]}</td></tr>')
        parts.append("</table>")
    keys = MAMMOTH.get("key_dates", [])
    if keys:
        parts.append('<h2>2026-27 dates to circle</h2><ul class="keys">' + "".join(
            f'<li class="{"past" if k["date"] < TODAY else ""}"><b>{fmt_date(k["date"])}</b> {esc(k["text"])}</li>'
            for k in keys) + "</ul>")
    if MAMMOTH.get("updated"):
        parts.append(f'<p class="meta">Schedule and standings refreshed {fmt_date(MAMMOTH["updated"])}.</p>')
    else:
        parts.append('<p class="meta">The full schedule and live standings start refreshing every morning once the site is live.</p>')
    return "".join(parts)


# ---------- rinks directory ----------
def rinks_panel():
    by_region = {}
    for r in RINKS["rinks"]:
        by_region.setdefault(r["region"], []).append(r)
    out = ['<div class="filters" role="group" aria-label="Filter rinks">'
           '<button data-f="all" aria-pressed="true">All</button>'
           '<button data-f="Indoor" aria-pressed="false">Indoor</button>'
           '<button data-f="Outdoor" aria-pressed="false">Outdoor</button>'
           '<button data-f="hockey" aria-pressed="false">Has hockey</button>'
           '<button data-f="skate" aria-pressed="false">Learn to skate</button></div>']
    for region, rs in by_region.items():
        out.append(f'<h2>{esc(region)}</h2><div class="rinks">')
        for r in rs:
            offers = " ".join(r["offers"]).lower()
            tags = [r["type"]] + (["hockey"] if "hockey" in offers else []) + (["skate"] if "learn to skate" in offers else [])
            status = {"closed": '<span class="pill closed">Temporarily closed</span>',
                      "seasonal": '<span class="pill seasonal">Seasonal</span>'}.get(r["status"], "")
            link = (f'<a href="{esc(r["url"])}" rel="noopener" target="_blank">Hours and prices &rarr;</a>'
                    if r.get("url") else '<span class="meta">Check the rink\'s own site for hours.</span>')
            out.append(f'<article class="rink" data-tags="{" ".join(tags)}">'
                       f'<h3>{esc(r["name"])}</h3>{status}'
                       f'<p class="meta">{esc(r["city"])} · {esc(r["type"])}</p>'
                       f'<p>{esc(r["notes"])}</p>'
                       f'<ul class="offers">{"".join(f"<li>{esc(o)}</li>" for o in r["offers"])}</ul>{link}</article>')
        out.append("</div>")
    out.append(f'<p class="meta">Listings last checked {fmt_date(RINKS["checked"])}. Hours change with the season, so confirm '
               f'before you drive over. Run a rink or see a mistake? <a href="mailto:{SITE["contact_email"]}">Tell us</a>.</p>')
    out.append("<script>document.querySelectorAll('.filters button').forEach(b=>b.onclick=()=>{"
               "document.querySelectorAll('.filters button').forEach(x=>x.setAttribute('aria-pressed',x===b));"
               "const f=b.dataset.f;document.querySelectorAll('.rink').forEach(r=>{"
               "r.hidden=f!=='all'&&!r.dataset.tags.split(' ').includes(f)})});</script>")
    return "".join(out)


# ---------- build ----------
def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "static", OUT, dirs_exist_ok=True)

    arts = [parse(p) for p in (ROOT / "content" / "articles").glob("*.html")]
    arts = [a for a in arts if a.get("draft", "").lower() != "true"]
    arts.sort(key=lambda a: (a["updated"], a.get("date", "")), reverse=True)
    arts.sort(key=lambda a: a.get("featured") == "true", reverse=True)

    for a in arts:
        same = [x for x in arts if x["section"] == a["section"] and x["slug"] != a["slug"]]
        related = (same + [x for x in arts if x not in same and x["slug"] != a["slug"]])[:3]
        sec = SECTIONS[a["section"]]
        ld = {"@context": "https://schema.org", "@type": "Article", "headline": a["title"],
              "description": a.get("description", ""), "datePublished": a.get("date"),
              "dateModified": a["updated"], "publisher": {"@type": "Organization", "name": SITE["name"]}}
        content = (
            '<article class="post">'
            f'<p class="kicker"><a href="/{sec["path"]}/">{esc(sec["title"])}</a> · {esc(a.get("category", "Guide"))}</p>'
            f'<h1>{esc(a["title"])}</h1><p class="lede">{esc(a.get("description", ""))}</p>'
            f'<p class="meta">Updated {fmt_date(a["updated"])} · <a href="/disclosure/">How we make money</a></p>'
            f'{ad_slot()}<div class="prose">{shortcodes(a["body"])}</div>'
            f'{sponsor_strip() if "{{sponsor}}" not in a["body"] else ""}'
            '<p class="note">Hockey Network USA is an independent fan site. We are not affiliated with the NHL, '
            "the Utah Mammoth, USA Hockey or any rink. Schedules and prices change, so check the official source.</p>"
            f"{newsletter()}"
            '<h2 class="more">Keep reading</h2><div class="grid">' + "".join(card(r) for r in related) + "</div></article>")
        write(a["url"].strip("/") + "/index.html", render(
            a["title"], a.get("description", ""), content, a["url"],
            f'<script type="application/ld+json">{json.dumps(ld)}</script><meta property="og:type" content="article">',
            a["section"]))

    for key, sec in SECTIONS.items():
        mine = [a for a in arts if a["section"] == key]
        panel = mammoth_panel() if key == "mammoth" else rinks_panel() if key == "rinks" else ""
        body = (f'<section class="wrap hub"><p class="kicker">Utah</p><h1>{esc(sec["title"])}</h1>'
                f'<p class="lede">{esc(sec["blurb"])}</p>{panel}{sponsor_strip()}'
                + (f'<h2>{"Reports and guides" if key == "mammoth" else "Guides"}</h2><div class="grid">'
                   + "".join(card(a) for a in mine) + "</div>" if mine else "")
                + f"{ad_slot()}{newsletter()}</section>")
        write(f'{sec["path"]}/index.html', render(f'{sec["title"]} in Utah', sec["blurb"], body, f'/{sec["path"]}/', active=key))

    reports = [a for a in arts if a.get("category") == "Weekly report"]
    lane = [a for a in arts if a.get("category") == "Memory lane"]
    guides = [a for a in arts if a.get("category") not in ("Weekly report", "Memory lane")]
    tiles = "".join(
        f'<a class="tile s-{k}" href="/{SECTIONS[k]["path"]}/"><b>{SECTIONS[k]["title"]}</b><span>{SECTIONS[k]["blurb"]}</span></a>'
        for k in NAV)
    home = (
        '<section class="hero"><div class="wrap"><div class="hero-text">'
        '<p class="kicker">Utah hockey</p>'
        '<h1>Everything on ice in the Beehive State.</h1>'
        "<p>From the old Salt Palace to the Delta Center, and from frozen ponds to Saturday-morning rec games. "
        "Mammoth reports every Monday, plus where to skate, how to get your kids started, and which leagues take "
        "beginners.</p>"
        f'</div>{next_game_card()}</div></section>'
        f'<section class="wrap"><div class="tiles">{tiles}</div>{sponsor_strip()}'
        + (f'<h2>Latest Mammoth report</h2><div class="grid">{card(reports[0])}</div>' if reports else "")
        + "".join(
            f'<a class="lane" href="{a["url"]}"><span class="kicker">Memory lane</span>'
            f'<h2>{esc(a["title"])}</h2><p>{esc(a.get("description", ""))}</p><span class="more-link">Read the story &rarr;</span></a>'
            for a in lane[:1])
        + '<h2>Start here</h2><div class="grid">' + "".join(card(a) for a in guides[:6]) + "</div>"
        f"{memories()}{ad_slot()}{newsletter()}</section>")
    write("index.html", render(SITE["name"], SITE["description"], home, "/"))

    for p in (ROOT / "content" / "pages").glob("*.html"):
        text = p.read_text(encoding="utf-8")
        _, fm, body = text.split("---", 2)
        meta = dict(l.split(":", 1) for l in fm.strip().splitlines() if ":" in l)
        t = meta.get("title", p.stem).strip()
        write(f"{p.stem}/index.html", render(
            t, meta.get("description", "").strip(),
            f'<article class="post"><h1>{esc(t)}</h1><div class="prose">{shortcodes(body.strip())}</div></article>', f"/{p.stem}/"))

    write("404.html", render("Page not found", "", '<section class="wrap hub"><h1>Off-side.</h1>'
          '<p>That page does not exist. Try the <a href="/">home page</a> or the <a href="/rinks/">rink list</a>.</p></section>', "/404"))

    urls = ["/"] + [f'/{s["path"]}/' for s in SECTIONS.values()] + [a["url"] for a in arts] + \
           [f"/{p.stem}/" for p in (ROOT / "content" / "pages").glob("*.html")]
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"  <url><loc>{SITE['url']}{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE['url']}/sitemap.xml\n")
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    items = "".join(f"<item><title>{esc(a['title'])}</title><link>{SITE['url']}{a['url']}</link>"
                    f"<guid>{SITE['url']}{a['url']}</guid><description>{esc(a.get('description', ''))}</description></item>"
                    for a in arts[:20])
    write("feed.xml", f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{esc(SITE["name"])}</title>'
          f"<link>{SITE['url']}</link><description>{esc(SITE['description'])}</description>"
          f"<lastBuildDate>{now}</lastBuildDate>{items}</channel></rss>")
    if SITE.get("adsense_client_id"):
        write("ads.txt", f"google.com, {SITE['adsense_client_id'].replace('ca-', '')}, DIRECT, f08c47fec0942fa0\n")
    print(f"Built {len(arts)} articles into {OUT}")


if __name__ == "__main__":
    main()
