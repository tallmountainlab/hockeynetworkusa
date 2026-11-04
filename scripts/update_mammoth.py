#!/usr/bin/env python3
"""Pull Utah Mammoth schedule, results and standings from the NHL's public
web API, save them to data/mammoth.json, and write the weekly report.

Runs every morning from .github/workflows/update.yml. No dependencies.
If the API is down, it leaves the existing data alone and exits cleanly.

For testing without network: HNUSA_FIXTURES=/path/to/dir with
schedule.json and standings.json in it. HNUSA_TODAY=YYYY-MM-DD fakes the date.
"""
import html
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
SITE = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
DATA = ROOT / "data" / "mammoth.json"
ARTICLES = ROOT / "content" / "articles"
TEAM = SITE.get("team_abbrev", "UTA")
MT = ZoneInfo("America/Denver")
API = "https://api-web.nhle.com/v1"


def today():
    t = os.environ.get("HNUSA_TODAY")
    return date.fromisoformat(t) if t else datetime.now(MT).date()


def season_id(d):
    return f"{d.year}{d.year + 1}" if d.month >= 7 else f"{d.year - 1}{d.year}"


def fetch(name, url):
    fx = os.environ.get("HNUSA_FIXTURES")
    if fx:
        return json.loads((Path(fx) / f"{name}.json").read_text(encoding="utf-8"))
    req = urllib.request.Request(url, headers={"User-Agent": "hockeynetworkusa.com updater"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def txt(v):
    return v.get("default", "") if isinstance(v, dict) else (v or "")


def team_name(t):
    place, common = txt(t.get("placeName")), txt(t.get("commonName"))
    return f"{place} {common}".strip() or t.get("abbrev", "")


def norm_game(g):
    home, away = g.get("homeTeam", {}), g.get("awayTeam", {})
    is_home = home.get("abbrev") == TEAM
    us, them = (home, away) if is_home else (away, home)
    start = g.get("startTimeUTC", "")
    local = ""
    if start:
        local = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(MT).isoformat()
    state = g.get("gameState", "FUT")
    final = state in ("FINAL", "OFF")
    out = {
        "id": g.get("id"),
        "date": g.get("gameDate", local[:10]),
        "start_local": local,
        "type": {1: "Preseason", 2: "Regular season", 3: "Playoffs"}.get(g.get("gameType"), ""),
        "home": is_home,
        "opponent": team_name(them),
        "opponent_abbrev": them.get("abbrev", ""),
        "venue": txt(g.get("venue")),
        "state": "final" if final else ("live" if state in ("LIVE", "CRIT") else "scheduled"),
    }
    if final:
        out["us"], out["them"] = us.get("score", 0), them.get("score", 0)
        out["ending"] = (g.get("gameOutcome") or {}).get("lastPeriodType", "REG")
        out["result"] = "W" if out["us"] > out["them"] else ("OTL" if out["ending"] in ("OT", "SO") else "L")
    return out


def norm_standings(raw):
    rows = []
    for s in raw.get("standings", []):
        rows.append({
            "abbrev": txt(s.get("teamAbbrev")),
            "team": txt(s.get("teamName")),
            "division": s.get("divisionName", ""),
            "gp": s.get("gamesPlayed", 0), "w": s.get("wins", 0), "l": s.get("losses", 0),
            "otl": s.get("otLosses", 0), "pts": s.get("points", 0),
            "div_rank": s.get("divisionSequence", 0), "league_rank": s.get("leagueSequence", 0),
            "streak": f'{s.get("streakCode", "")}{s.get("streakCount", "")}',
            "l10": f'{s.get("l10Wins", 0)}-{s.get("l10Losses", 0)}-{s.get("l10OtLosses", 0)}',
        })
    me = next((r for r in rows if r["abbrev"] == TEAM), None)
    division = sorted([r for r in rows if me and r["division"] == me["division"]], key=lambda r: r["div_rank"])
    return me, division


def fmt_day(iso):
    d = datetime.fromisoformat(iso) if "T" in iso else datetime.fromisoformat(iso + "T00:00:00")
    return d.strftime("%a, %b %-d")


def fmt_time(iso):
    if "T" not in iso:
        return "TBD"
    return datetime.fromisoformat(iso).strftime("%-I:%M %p MT").replace(":00 ", " ")


def score_line(g):
    tail = f" ({g['ending']})" if g.get("ending") in ("OT", "SO") else ""
    return f"{g['result']} {g['us']}-{g['them']}{tail}"


def weekly_report(data, monday):
    """Write the report for the week ending the day before `monday`."""
    slug = f"utah-mammoth-weekly-report-{monday.isoformat()}"
    path = ARTICLES / f"{slug}.html"
    if path.exists():
        return None
    start, end = monday - timedelta(days=7), monday - timedelta(days=1)
    nxt_end = monday + timedelta(days=6)
    games = data["games"]
    played = [g for g in games if g["state"] == "final" and start.isoformat() <= g["date"] <= end.isoformat()]
    coming = [g for g in games if g["state"] != "final" and monday.isoformat() <= g["date"] <= nxt_end.isoformat()]
    if not played and not coming:
        return None  # off week (All-Star break, offseason)

    rec, div = data.get("record"), data.get("division", [])
    w = sum(g["result"] == "W" for g in played)
    l = sum(g["result"] == "L" for g in played)
    otl = sum(g["result"] == "OTL" for g in played)
    gf, ga = sum(g["us"] for g in played), sum(g["them"] for g in played)
    span = f"{start.strftime('%b %-d')} to {end.strftime('%b %-d')}"

    if not played:
        lede = f"No games for the Mammoth from {span}, so everybody got a breather."
    elif w > l + otl:
        lede = f"A good week to be a Mammoth fan: {w}-{l}-{otl} from {span}, " + (f"outscoring opponents {gf}-{ga}." if gf > ga else f"with opponents scoring {ga} to our {gf}." if ga > gf else f"with goals even at {gf}-{ga}.")
    elif w < l + otl:
        lede = f"A tough week for the Mammoth: {w}-{l}-{otl} from {span}, " + (f"outscoring opponents {gf}-{ga}." if gf > ga else f"with opponents scoring {ga} to our {gf}." if ga > gf else f"with goals even at {gf}-{ga}.")
    else:
        lede = f"A split week for the Mammoth: {w}-{l}-{otl} from {span}, " + (f"outscoring opponents {gf}-{ga}." if gf > ga else f"with opponents scoring {ga} to our {gf}." if ga > gf else f"with goals even at {gf}-{ga}.")
    body = ["<p>Grab a coffee, here's your Monday catch-up.</p>", f"<p>{html.escape(lede)}"]
    if rec:
        body.append(f" That puts Utah at {rec['w']}-{rec['l']}-{rec['otl']} with {rec['pts']} points, "
                    f"{ordinal(rec['div_rank'])} in the {html.escape(rec['division'])} Division.")
    body.append("</p>")

    if played:
        body.append("<h2>Last week's results</h2><table><tr><th>Date</th><th>Opponent</th><th>Result</th></tr>")
        for g in played:
            body.append(f"<tr><td>{fmt_day(g['date'])}</td><td>{'vs' if g['home'] else 'at'} "
                        f"{html.escape(g['opponent'])}</td><td>{score_line(g)}</td></tr>")
        body.append("</table>")
    body.append("{{sponsor}}")
    if coming:
        body.append("<h2>This week's games</h2><table><tr><th>Date</th><th>Opponent</th><th>Puck drop</th></tr>")
        for g in coming:
            body.append(f"<tr><td>{fmt_day(g['start_local'] or g['date'])}</td><td>{'vs' if g['home'] else 'at'} "
                        f"{html.escape(g['opponent'])}</td><td>{fmt_time(g['start_local'])}</td></tr>")
        body.append("</table>")
        homes = sum(g["home"] for g in coming)
        if homes:
            body.append(f"<p>{homes} of this week's games {'is' if homes == 1 else 'are'} at Delta Center.</p>{{{{affiliate:tickets}}}}")
    if div:
        body.append("<h2>Division standings</h2><table><tr><th></th><th>Team</th><th>GP</th><th>Record</th><th>Pts</th></tr>")
        for r in div:
            mark = ' class="us"' if r["abbrev"] == TEAM else ""
            body.append(f"<tr{mark}><td>{r['div_rank']}</td><td>{html.escape(r['team'])}</td><td>{r['gp']}</td>"
                        f"<td>{r['w']}-{r['l']}-{r['otl']}</td><td>{r['pts']}</td></tr>")
        body.append("</table>")
    body.append('<p>Full schedule and live standings are on our <a href="/mammoth/">Mammoth page</a>, updated every morning. '
                'See you next Monday.</p>{{memories}}')

    title = f"Utah Mammoth weekly report: week of {monday.strftime('%B %-d, %Y')}"
    desc = f"{lede} Results, this week's schedule and the {rec['division'] if rec else 'division'} standings."
    path.write_text(
        "---\n"
        f"title: {title}\n"
        f"description: {desc}\n"
        f"date: {monday.isoformat()}\n"
        f"updated: {monday.isoformat()}\n"
        "section: mammoth\n"
        "category: Weekly report\n"
        "---\n" + "\n".join(body) + "\n", encoding="utf-8")
    return path


def ordinal(n):
    n = int(n or 0)
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def main():
    d = today()
    old = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {}
    try:
        sched = fetch("schedule", f"{API}/club-schedule-season/{TEAM}/{season_id(d)}")
        stand = fetch("standings", f"{API}/standings/now")
    except Exception as e:  # network or API change: keep the last good data
        print(f"NHL API unavailable, keeping existing data: {e}")
        return 0

    games = sorted((norm_game(g) for g in sched.get("games", [])), key=lambda g: g["start_local"] or g["date"])
    me, division = norm_standings(stand)
    data = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": season_id(d),
        "record": me,
        "division": division,
        "games": games,
        "key_dates": old.get("key_dates", []),
    }
    if not games:
        print("API returned no games, keeping existing data")
        return 0
    DATA.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(f"Saved {len(games)} games")

    monday = d - timedelta(days=d.weekday())
    made = weekly_report(data, monday)
    if made:
        print(f"Wrote {made.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
