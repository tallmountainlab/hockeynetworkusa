#!/usr/bin/env python3
"""Pull league-wide scores, highlight links, upcoming games and standings
from the NHL's public web API into data/league.json.

The site uses it for "choose your team" and the league highlights page.
Runs every morning from .github/workflows/update.yml. No dependencies.
If the API is down, the existing file is kept.

Testing without network: HNUSA_FIXTURES=dir with score-YYYY-MM-DD.json,
schedule.json and standings.json. HNUSA_TODAY=YYYY-MM-DD fakes the date.
"""
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "league.json"
API = "https://api-web.nhle.com/v1"
NHL = "https://www.nhl.com"
MT = ZoneInfo("America/Denver")
DAYS_BACK = 7


def today():
    t = os.environ.get("HNUSA_TODAY")
    return date.fromisoformat(t) if t else datetime.now(MT).date()


def fetch(name, url):
    fx = os.environ.get("HNUSA_FIXTURES")
    if fx:
        p = Path(fx) / f"{name}.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    req = urllib.request.Request(url, headers={"User-Agent": "hockeynetworkusa.com updater"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def txt(v):
    return v.get("default", "") if isinstance(v, dict) else (v or "")


def link(path):
    if not path:
        return ""
    return path if path.startswith("http") else NHL + path


def final_game(g):
    away, home = g.get("awayTeam", {}), g.get("homeTeam", {})
    goals = []
    for x in g.get("goals", []) or []:
        goals.append({
            "team": x.get("teamAbbrev", ""),
            "scorer": f'{txt(x.get("firstName"))} {txt(x.get("lastName"))}'.strip() or txt(x.get("name")),
            "period": (x.get("periodDescriptor") or {}).get("periodType", "REG") if (x.get("periodDescriptor") or {}).get("number", 0) > 3 else str(x.get("period", "")),
            "time": x.get("timeInPeriod", ""),
            "strength": x.get("strength", ""),
            "clip": link(x.get("highlightClipSharingUrl", "")),
        })
    return {
        "id": g.get("id"), "date": g.get("gameDate", ""), "type": g.get("gameType", 2),
        "away": away.get("abbrev", ""), "home": home.get("abbrev", ""),
        "as": away.get("score", 0), "hs": home.get("score", 0),
        "ending": (g.get("gameOutcome") or {}).get("lastPeriodType", "REG"),
        "recap": link(g.get("threeMinRecap", "")),
        "condensed": link(g.get("condensedGame", "")),
        "center": link(g.get("gameCenterLink", "")),
        "goals": goals,
    }


def main():
    d = today()
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    try:
        stand = fetch("standings", f"{API}/standings/now")
        week = fetch("schedule", f"{API}/schedule/{d.isoformat()}")
        scores = []
        for back in range(DAYS_BACK, -1, -1):
            day = (d - timedelta(days=back)).isoformat()
            scores.append(fetch(f"score-{day}", f"{API}/score/{day}"))
    except Exception as e:
        print(f"NHL API unavailable, keeping existing data: {e}")
        return 0

    teams = {}
    for s in stand.get("standings", []):
        ab = txt(s.get("teamAbbrev"))
        teams[ab] = {
            "name": txt(s.get("teamName")), "place": txt(s.get("placeName")),
            "common": txt(s.get("teamCommonName")),
            "division": s.get("divisionName", ""), "conference": s.get("conferenceName", ""),
            "gp": s.get("gamesPlayed", 0), "w": s.get("wins", 0), "l": s.get("losses", 0),
            "otl": s.get("otLosses", 0), "pts": s.get("points", 0),
            "div_rank": s.get("divisionSequence", 0), "conf_rank": s.get("conferenceSequence", 0),
            "league_rank": s.get("leagueSequence", 0),
            "streak": f'{s.get("streakCode", "")}{s.get("streakCount", "")}',
            "l10": f'{s.get("l10Wins", 0)}-{s.get("l10Losses", 0)}-{s.get("l10OtLosses", 0)}',
        }
    if not teams:
        print("No standings returned, keeping existing data")
        return 0

    finals, seen = [], set()
    for sc in scores:
        for g in sc.get("games", []) or []:
            if g.get("gameState") in ("FINAL", "OFF") and g.get("id") not in seen:
                seen.add(g["id"])
                finals.append(final_game(g))
    finals.sort(key=lambda g: (g["date"], g["id"]), reverse=True)

    upcoming = []
    for day in week.get("gameWeek", []) or []:
        for g in day.get("games", []) or []:
            if g.get("gameState") in ("FUT", "PRE", "LIVE", "CRIT"):
                upcoming.append({
                    "id": g.get("id"), "date": day.get("date", ""), "start": g.get("startTimeUTC", ""),
                    "away": g.get("awayTeam", {}).get("abbrev", ""), "home": g.get("homeTeam", {}).get("abbrev", ""),
                    "venue": txt(g.get("venue")),
                })
    upcoming.sort(key=lambda g: g["start"] or g["date"])

    data = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "teams": teams, "finals": finals, "upcoming": upcoming}
    if not finals and old.get("finals"):
        data["finals"] = old["finals"]  # e.g. All-Star break: keep the last highlights up
    OUT.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {len(teams)} teams, {len(data['finals'])} finals, {len(upcoming)} upcoming")
    return 0


if __name__ == "__main__":
    sys.exit(main())
