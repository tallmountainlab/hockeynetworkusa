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
PHOTOS_FILE = ROOT / "data" / "photos.json"
PHOTOS = json.loads(PHOTOS_FILE.read_text(encoding="utf-8")) if PHOTOS_FILE.exists() else {}
LEAGUE_FILE = ROOT / "data" / "league.json"
LEAGUE = json.loads(LEAGUE_FILE.read_text(encoding="utf-8")) if LEAGUE_FILE.exists() else {"teams": {}, "finals": [], "upcoming": []}
VIDEOS_FILE = ROOT / "data" / "videos.json"
VIDEOS = json.loads(VIDEOS_FILE.read_text(encoding="utf-8")).get("videos", []) if VIDEOS_FILE.exists() else []
TEAM_THEMES = {  # primary, secondary
    "ANA": ("#F47A38", "#000000"), "BOS": ("#FFB81C", "#000000"), "BUF": ("#003087", "#FFB81C"),
    "CAR": ("#CE1126", "#000000"), "CBJ": ("#002654", "#CE1126"), "CGY": ("#C8102E", "#F1BE48"),
    "CHI": ("#CF0A2C", "#000000"), "COL": ("#6F263D", "#236192"), "DAL": ("#006847", "#111111"),
    "DET": ("#CE1126", "#FFFFFF"), "EDM": ("#041E42", "#FF4C00"), "FLA": ("#C8102E", "#041E42"),
    "LAK": ("#111111", "#A2AAAD"), "MIN": ("#154734", "#A6192E"), "MTL": ("#AF1E2D", "#192168"),
    "NJD": ("#CE1126", "#000000"), "NSH": ("#FFB81C", "#041E42"), "NYI": ("#00539B", "#F47D30"),
    "NYR": ("#0038A8", "#CE1126"), "OTT": ("#C52032", "#000000"), "PHI": ("#F74902", "#000000"),
    "PIT": ("#FCB514", "#000000"), "SEA": ("#001628", "#99D9D9"), "SJS": ("#006D75", "#EA7200"),
    "STL": ("#002F87", "#FCB514"), "TBL": ("#002868", "#FFFFFF"), "TOR": ("#00205B", "#FFFFFF"),
    "UTA": ("#010101", "#71AFE5"), "VAN": ("#00205B", "#00843D"), "VGK": ("#B4975A", "#333F42"),
    "WPG": ("#041E42", "#AC162C"), "WSH": ("#C8102E", "#041E42"),
}


def _lum(c):
    r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b


def _mix(c, t, k):
    a = [int(c[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(t[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * k):02x}" for x, y in zip(a, b))


def _ink(c):
    return "#111111" if _lum(c) > 150 else "#ffffff"


def team_theme(ab):
    """Every team always gets the same scheme, built from its two brand colors:
    tc1 = the darker color (header, hero, stat tiles), tc2 = the other one
    (stripes, buttons, accents on dark), tcl = a version readable on light
    backgrounds (links, headings), sig = the signature color used for tints."""
    p, s2 = TEAM_THEMES[ab]
    dark, light = (p, s2) if _lum(p) <= _lum(s2) else (s2, p)
    if 40 <= _lum(light) <= 140:
        link = light
    elif _lum(dark) >= 25:
        link = dark
    else:
        link = _mix(light, "#000000", 0.42)
    sig = TEAM_COLORS.get(ab, light)
    return {"tc1": dark, "tc1i": _ink(dark), "tc2": light, "tc2i": _ink(light), "tcl": link, "sig": sig}


TEAM_COLORS = {
    "ANA": "#F47A38", "BOS": "#FFB81C", "BUF": "#003087", "CAR": "#CE1126", "CBJ": "#002654", "CGY": "#C8102E",
    "CHI": "#CF0A2C", "COL": "#6F263D", "DAL": "#006847", "DET": "#CE1126", "EDM": "#FF4C00", "FLA": "#C8102E",
    "LAK": "#111111", "MIN": "#154734", "MTL": "#AF1E2D", "NJD": "#CE1126", "NSH": "#FFB81C", "NYI": "#00539B",
    "NYR": "#0038A8", "OTT": "#C52032", "PHI": "#F74902", "PIT": "#FCB514", "SEA": "#001628", "SJS": "#006D75",
    "STL": "#002F87", "TBL": "#002868", "TOR": "#00205B", "UTA": "#71AFE5", "VAN": "#00205B", "VGK": "#B4975A",
    "WPG": "#041E42", "WSH": "#C8102E",
}
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
SECTION_IMAGES = {"mammoth": "delta-center", "rinks": "peaks-arena", "youth": "youth-game",
                  "adult": "pond-hockey", "skate": "holiday-rink"}
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


# ---------- photos ----------
def has_photo(key):
    return key in PHOTOS and (ROOT / "static" / "img" / f"{key}.jpg").exists()


def figure(key, cls="photo", eager=False):
    if not has_photo(key):
        return ""
    p = PHOTOS[key]
    author = re.sub(r"\s+from .*$", "", p.get("author", "")) or "Wikimedia Commons"
    return (f'<figure class="{cls}"><img src="/img/{key}.jpg" srcset="/img/{key}-sm.jpg 720w, /img/{key}.jpg 1600w" '
            f'sizes="(max-width: 780px) 100vw, 780px" alt="{esc(p.get("alt", ""))}"{"" if eager else " loading=lazy"}>'
            f'<figcaption>{esc(p.get("caption", ""))} <a href="/photo-credits/">Photo: {esc(author)}, '
            f'{esc(p.get("license", ""))}</a></figcaption></figure>')


# ---------- teams ----------
def team_badge(ab):
    if ab not in TEAM_THEMES:
        return f'<span class="badge" style="background:#555;color:#fff">{esc(ab)}</span>'
    t = team_theme(ab)
    ink = t["tc2"] if abs(_lum(t["tc2"]) - _lum(t["tc1"])) > 90 else t["tc1i"]
    return (f'<span class="badge" style="background:{t["tc1"]};color:{ink};box-shadow:inset 0 -3px 0 {t["tc2"]}">'
            f'{esc(ab)}</span>')


def team_photos():
    """Photo for each team's hero (data/photos.json keys team-XXX), plus
    general game-action photos used for teams without one of their own."""
    def entry(k):
        p = PHOTOS[k]
        author = re.sub(r"\s+from .*$", "", p.get("author", "")) or "Wikimedia Commons"
        return {"src": f"/img/{k}.jpg", "sm": f"/img/{k}-sm.jpg", "alt": p.get("alt", ""),
                "credit": f'{author}, {p.get("license", "")}'}
    teams = {k[5:]: entry(k) for k in PHOTOS if k.startswith("team-") and has_photo(k)}
    action = [entry(k) for k in PHOTOS if k.startswith("action-") and has_photo(k)]
    if not action and has_photo("olympic-hockey-2002"):
        action = [entry("olympic-hockey-2002")]
    return {"teams": teams, "action": action}


def pagehead(kicker, title, lede, key=""):
    """Colored banner in the visitor's team colors, over a hockey photo."""
    if not has_photo(key):
        acts = [k for k in PHOTOS if k.startswith("action-") and has_photo(k)]
        key = acts[sum(map(ord, title)) % len(acts)] if acts else ""
    credit = ""
    if has_photo(key):
        author = re.sub(r"\s+from .*$", "", PHOTOS[key].get("author", "")) or "Wikimedia Commons"
        credit = f'<a class="credit" href="/photo-credits/">Photo: {esc(author)}, {esc(PHOTOS[key].get("license", ""))}</a>'
    style = f' style="--hero-img:url(/img/{key}.jpg)"' if has_photo(key) else ""
    return (f'<header class="pagehead{" has-photo" if style else ""}"{style}><div class="wrap">'
            f'<p class="kicker">{kicker}</p><h1>{title}</h1><p class="lede">{lede}</p></div>{credit}'
            '<div class="stripes" aria-hidden="true"></div></header>')


def theme_vars(t):
    return ";".join(f"--{k}:{v}" for k, v in t.items())


def theme_script():
    themes = {ab: team_theme(ab) for ab in TEAM_THEMES}
    return ("<script>(function(){var T=" + json.dumps(themes, separators=(",", ":")) + ",t;"
            "try{t=localStorage.getItem('hnusa-team')}catch(e){}"
            "if(t&&T[t]){var r=document.documentElement,c=T[t];r.dataset.team=t;"
            "for(var k in c)r.style.setProperty('--'+k,c[k]);}"
            "window.HNUSA_THEMES=T;window.HNUSA_PHOTOS=" + json.dumps(team_photos(), separators=(",", ":")) + ";})();</script>")


def video_for_game(g):
    want = {g["away"], g["home"]}
    for v in VIDEOS:
        if v.get("kind") == "game" and want <= set(v.get("teams", [])) and v.get("published", "")[:10] >= g["date"]:
            return v
    return None


def team_name(ab):
    return LEAGUE.get("teams", {}).get(ab, {}).get("name", ab)


def game_card(g):
    ot = f' <span class="ot">{g["ending"]}</span>' if g.get("ending") in ("OT", "SO") else ""
    win_a, win_h = g["as"] > g["hs"], g["hs"] > g["as"]
    goals = "".join(
        f'<li>{team_badge(x["team"])} <a href="{esc(x["clip"])}" target="_blank" rel="noopener">{esc(x["scorer"])}</a>'
        f'<span class="meta"> {esc(x["period"] if x["period"] in ("OT", "SO") else ordinal(x["period"] or 0))} {esc(x["time"])}'
        f'{" · PP" if x.get("strength") == "pp" else " · SH" if x.get("strength") == "sh" else ""}</span></li>'
        if x.get("clip") else
        f'<li>{team_badge(x["team"])} {esc(x["scorer"])}</li>'
        for x in g.get("goals", []))
    vids = "".join(
        f'<a class="vid" href="{esc(u)}" target="_blank" rel="noopener">&#9654; {lbl}</a>'
        for u, lbl in ((g.get("recap"), "Recap"), (g.get("condensed"), "Condensed game")) if u)
    yv = video_for_game(g)
    thumb = (f'<button type="button" class="yt" data-yt="{yv["id"]}" aria-label="Play {esc(yv["title"])}">'
             f'<img src="{esc(yv["thumb"])}" alt="" loading="lazy"><span class="play"></span></button>' if yv else "")
    return (f'<article class="game" data-teams="{g["away"]} {g["home"]}">{thumb}'
            f'<div class="line{" won" if win_a else ""}">{team_badge(g["away"])}<span>{esc(team_name(g["away"]))}</span><b>{g["as"]}</b></div>'
            f'<div class="line{" won" if win_h else ""}">{team_badge(g["home"])}<span>{esc(team_name(g["home"]))}</span><b>{g["hs"]}</b></div>'
            f'<p class="meta">Final{ot}</p><div class="vids">{vids}</div>'
            + (f'<details><summary>Goal highlights ({len(g.get("goals", []))})</summary><ul class="goals">{goals}</ul></details>' if goals else "")
            + "</article>")


def team_picker():
    teams = LEAGUE.get("teams", {})
    if not teams:
        return ""
    divs = {}
    for ab, t in sorted(teams.items(), key=lambda kv: kv[1]["name"]):
        divs.setdefault(t["division"], []).append(ab)
    body = "".join(
        f'<h3>{esc(d)}</h3><div class="picks">' + "".join(
            f'<button type="button" data-team="{ab}">{team_badge(ab)}<span>{esc(teams[ab]["name"])}</span></button>' for ab in abs_)
        + "</div>" for d, abs_ in sorted(divs.items()))
    return ('<dialog id="teampick" class="teampick"><form method="dialog"><button class="x" aria-label="Close">&times;</button></form>'
            '<h2>Choose your team</h2><p class="meta">We\'ll remember it on this device and put your team\'s scores and '
            f'highlights first. Utah hockey stories stay right where they are.</p>{body}</dialog>')


def highlights_strip(n=4):
    finals = LEAGUE.get("finals", [])
    if not finals:
        return ""
    last = finals[0]["date"]
    games = [g for g in finals if g["date"] == last][:n]
    return (f'<h2 class="band">Around the league · {short_date(last)}</h2><div class="games">'
            + "".join(game_card(g) for g in games)
            + '</div><p><a class="btn ghost" href="/highlights/">All scores and highlight videos &rarr;</a></p>')


def side_scores(n=8):
    finals = LEAGUE.get("finals", [])
    if not finals:
        return ""
    last = finals[0]["date"]
    rows = "".join(
        f'<li data-teams="{g["away"]} {g["home"]}">{team_badge(g["away"])} <b>{g["as"]}</b> '
        f'<span class="at">@</span> {team_badge(g["home"])} <b>{g["hs"]}</b>'
        f'{" <span class=ot>" + g["ending"] + "</span>" if g.get("ending") in ("OT", "SO") else ""}'
        + (f' <a href="{esc(g["recap"])}" target="_blank" rel="noopener">recap</a>' if g.get("recap") else "") + "</li>"
        for g in [g for g in finals if g["date"] == last][:n])
    return (f'<section class="side-box"><span class="kicker">Around the NHL · {short_date(last)}</span>'
            f'<ul class="mini-scores">{rows}</ul><a href="/highlights/">All scores &amp; highlights &rarr;</a></section>')


def gallery():
    keys = [k for k in ("action-goal", "salt-palace", "action-stadium", "olympic-hockey-2002", "action-goalie", "grizzlies",
                        "action-celebrate", "pond-hockey", "action-faceoff", "youth-game", "team-CGY", "peaks-sign") if has_photo(k)]
    if not keys:
        return ""
    return ('<h2 class="band">Hockey in pictures</h2><div class="gallery">' + "".join(
        f'<figure><img src="/img/{k}-sm.jpg" alt="{esc(PHOTOS[k]["alt"])}" loading="lazy"><figcaption>{esc(PHOTOS[k]["caption"])}</figcaption></figure>'
        for k in keys) + '</div><p class="meta"><a href="/photo-credits/">Photo credits</a></p>')


def highlights_page():
    finals = LEAGUE.get("finals", [])
    by_day = {}
    for g in finals:
        by_day.setdefault(g["date"], []).append(g)
    days = "".join(f'<h2>{fmt_date(d)}</h2><div class="games">' + "".join(game_card(g) for g in gs) + "</div>"
                   for d, gs in by_day.items())
    if not days:
        days = "<p>Highlights show up here the morning after games are played.</p>"
    return (pagehead("NHL", "Scores &amp; highlights", "Every NHL game from the past week, with the official recap, "
                     "the condensed game and a clip of every goal. Videos play on NHL.com.", "action-goal")
            + '<section class="wrap hub">'
            '<label class="onlymine"><input type="checkbox" id="onlymine"> Only show <span data-myteam-name>my team</span></label>'
            f'{sponsor_strip()}{days}{ad_slot()}'
            '<p class="note">Scores and video links come from the NHL\'s public data and refresh every morning. '
            'Videos belong to the NHL.</p></section>')


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
    body = re.sub(r"\{\{photo:([\w-]+)\}\}", lambda m: figure(m.group(1)), body)
    for k, fn in {"ad": ad_slot, "newsletter": newsletter, "sponsor": sponsor_strip, "next_game": next_game_card, "memories": memories}.items():
        body = body.replace("{{" + k + "}}", fn())
    return body


# ---------- page shell ----------
def render(title, description, content, path, extra_head="", active=""):
    head = theme_script() + extra_head
    if SITE.get("adsense_client_id"):
        head += ('<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
                 f'?client={esc(SITE["adsense_client_id"])}" crossorigin="anonymous"></script>')
    def nl(href, label, key, cls=""):
        return f'<a href="{href}"{" aria-current=page" if key == active else ""}{f" class={cls}" if cls else ""}>{label}</a>'
    nav = ("".join(nl(f'/{SECTIONS[k]["path"]}/', SECTIONS[k]["title"], k, "utah-only") for k in NAV)
           + nl("/news/", "News", "news", "other-only") + nl("/stats/", "Stats", "stats", "other-only")
           + nl("/standings/", "Standings", "standings") + nl("/highlights/", "Highlights", "highlights"))
    full_title = title if title == SITE["name"] else f"{title} | {SITE['name']}"
    out = TEMPLATE
    for k, v in {
        "{{title}}": esc(full_title), "{{description}}": esc(description),
        "{{canonical}}": SITE["url"] + path, "{{site_name}}": SITE["name"],
        "{{tagline}}": esc(SITE["tagline"]), "{{extra_head}}": head, "{{nav}}": nav,
        "{{content}}": content, "{{year}}": str(date.today().year),
        "{{contact_email}}": SITE["contact_email"], "{{team_picker}}": team_picker(),
    }.items():
        out = out.replace(k, v)
    return out


def write(rel, text):
    dest = OUT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")


def card(a):
    sec = SECTIONS[a["section"]]["title"]
    img = a.get("image", "")
    thumb = (f'<img class="thumb" src="/img/{img}-sm.jpg" alt="" loading="lazy">' if has_photo(img) else "")
    return (f'<a class="card s-{a["section"]}{" has-img" if thumb else ""}" href="{a["url"]}">{thumb}'
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
            f'{figure(a.get("image", ""), "photo lead-photo", eager=True)}'
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
        body = (pagehead("Utah", esc(sec["title"]), esc(sec["blurb"]), SECTION_IMAGES.get(key, ""))
                + f'<section class="wrap hub">{panel}{sponsor_strip()}'
                + (f'<h2>{"Reports and guides" if key == "mammoth" else "Guides"}</h2><div class="grid">'
                   + "".join(card(a) for a in mine) + "</div>" if mine else "")
                + f"{ad_slot()}{newsletter()}</section>")
        write(f'{sec["path"]}/index.html', render(f'{sec["title"]} in Utah', sec["blurb"], body, f'/{sec["path"]}/', active=key))

    reports = [a for a in arts if a.get("category") == "Weekly report"]
    lane = [a for a in arts if a.get("category") == "Memory lane"]
    guides = [a for a in arts if a.get("category") not in ("Weekly report", "Memory lane")]
    tiles = "".join(
        f'<a class="ptile s-{k}" href="/{SECTIONS[k]["path"]}/"'
        + (f' style="--img:url(/img/{SECTION_IMAGES[k]}-sm.jpg)"' if has_photo(SECTION_IMAGES.get(k, "")) else "")
        + f'><b>{SECTIONS[k]["title"]}</b><span>{SECTIONS[k]["blurb"]}</span></a>'
        for k in NAV)
    uta = LEAGUE.get("teams", {}).get("UTA")
    tp = team_photos()
    hp = tp["teams"].get("UTA") or (tp["action"][0] if tp["action"] else None)
    home = (
        f'<section class="thero{" has-photo" if hp else ""}" id="thero"'
        + (f' style="--hero-img:url({hp["src"]})"' if hp else "")
        + '><div class="wrap"><div class="th-main">'
        '<p class="kicker">Utah\'s team</p><h1>Utah Mammoth</h1>'
        + (f'<div class="chips"><span><b>{uta["w"]}-{uta["l"]}-{uta["otl"]}</b>Record</span><span><b>{uta["pts"]}</b>Points</span>'
           f'<span><b>{ordinal(uta["div_rank"])}</b>{esc(uta["division"])}</span></div>' if uta else "")
        + "<p>Scores, goals, news, stats and standings for your team, plus Utah rinks, youth and adult hockey, "
        "and learn to skate. Pick any NHL team and the whole site switches to its colors.</p>"
        '<button type="button" class="btn alt" data-open-picker>Pick your team</button>'
        f'</div><div class="th-next">{next_game_card()}</div></div>'
        + (f'<span class="credit">Photo: {esc(hp["credit"])}</span>' if hp else "")
        + '<div class="stripes" aria-hidden="true"></div></section>'
        '<section class="wrap">'
        '<div class="teamzone"><div id="myteam" class="myteam" aria-live="polite"></div>'
        '<aside class="tz-side" id="leagueside"><div id="tonight"></div><div id="mostviewed"></div>'
        f'{side_scores()}<div id="leaguenews"></div><div id="leagueleaders"></div></aside></div>'
        f'<div class="utah-only"><h2 class="band">Utah hockey</h2><div class="ptiles">{tiles}</div></div>'
        f'<div class="other-only">{highlights_strip(6)}</div>'
        f'{sponsor_strip()}{gallery()}'
        + '<div class="utah-only">'
        + (f'<h2>Latest Mammoth report</h2><div class="grid">{card(reports[0])}</div>' if reports else "")
        + "".join(
            f'<a class="lane" href="{a["url"]}"><span class="kicker">Memory lane</span>'
            f'<h2>{esc(a["title"])}</h2><p>{esc(a.get("description", ""))}</p><span class="more-link">Read the story &rarr;</span></a>'
            for a in lane[:1])
        + '<h2>Start here</h2><div class="grid">' + "".join(card(a) for a in guides[:6]) + "</div>"
        f"{memories()}</div>"
        '<aside class="other-only utah-strip"><span class="kicker">Live in Utah?</span><p>We also cover local hockey: '
        + " · ".join(f'<a href="/{SECTIONS[k]["path"]}/">{SECTIONS[k]["title"]}</a>' for k in NAV)
        + f'</p></aside>{ad_slot()}{newsletter()}</section>')
    write("index.html", render(SITE["name"], SITE["description"], home, "/"))
    for slug, title, lede, box in (
            ("news", "news", "The latest headlines about your team from around the web, plus league news. "
             "Every headline links to the original story.", "newspage"),
            ("stats", "stats", "Top scorers and goalies for your team, and the NHL scoring leaders. Updated three times a day.", "statspage"),
            ("standings", "standings", "Division, conference and league standings, with your team highlighted. "
             "Updated three times a day.", "standpage")):
        head = pagehead("Your team", f'<span data-myteam-name>Utah Mammoth</span> {title}', lede, "team-UTA")
        head = head.replace('<header class="pagehead', '<header data-teamphoto class="pagehead', 1)
        write(f"{slug}/index.html", render(f"NHL {title} for your team", lede, head +
              f'<section class="wrap hub"><div id="{box}" class="myteam teampage" aria-live="polite"></div>'
              f'{ad_slot()}</section>', f"/{slug}/", active=slug))
    write("highlights/index.html", render("NHL scores and highlights", "Every NHL game from the past week with recap, "
          "condensed game and goal highlight videos, filtered to your team.", highlights_page(), "/highlights/",
          active="highlights"))
    (OUT / "data").mkdir(exist_ok=True)
    for name in ("league", "videos", "stats", "news"):
        f = ROOT / "data" / f"{name}.json"
        if f.exists():
            shutil.copy(f, OUT / "data" / f"{name}.json")
    used = [k for k in PHOTOS if has_photo(k)]
    if used:
        rows = "".join(
            f'<li><img src="/img/{k}-sm.jpg" alt="" loading="lazy"><div><b>{esc(PHOTOS[k].get("caption", ""))}</b><br>'
            f'<a href="{esc(PHOTOS[k].get("page", ""))}" rel="noopener">{esc(PHOTOS[k].get("title", "").replace("File:", ""))}</a> '
            f'by {esc(PHOTOS[k].get("author", ""))}, <a href="{esc(PHOTOS[k].get("license_url", ""))}" rel="noopener">'
            f'{esc(PHOTOS[k].get("license", ""))}</a></div></li>' for k in used)
        write("photo-credits/index.html", render(
            "Photo credits", "The photographers behind the pictures on Hockey Network USA.",
            '<article class="post"><h1>Photo credits</h1><p>Our photos come from Wikimedia Commons and are shared under '
            'Creative Commons or public-domain licenses. Thank you to every photographer below.</p>'
            f'<ul class="credits">{rows}</ul></article>', "/photo-credits/"))

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

    urls = ["/", "/highlights/", "/standings/", "/stats/", "/news/"] + [f'/{s["path"]}/' for s in SECTIONS.values()] + [a["url"] for a in arts] + \
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
