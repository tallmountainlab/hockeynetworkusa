#!/usr/bin/env python3
"""Pull player stats for every NHL team (top scorers and goalies) plus the
league leaders from the NHL's public web API into data/stats.json.

Runs from .github/workflows/update.yml. No dependencies. If the API is
down, the existing file is kept. Needs data/league.json for the team list.
"""
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "stats.json"
LEAGUE = ROOT / "data" / "league.json"
API = "https://api-web.nhle.com/v1"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "hockeynetworkusa.com updater"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def txt(v):
    return v.get("default", "") if isinstance(v, dict) else (v or "")


def name(p):
    return f'{txt(p.get("firstName"))} {txt(p.get("lastName"))}'.strip()


def team_stats(ab):
    raw = fetch(f"{API}/club-stats/{ab}/now")
    sk = sorted(raw.get("skaters", []) or [], key=lambda p: (p.get("points", 0), p.get("goals", 0)), reverse=True)
    gl = sorted(raw.get("goalies", []) or [], key=lambda p: p.get("gamesPlayed", 0), reverse=True)
    return {
        "skaters": [{"name": name(p), "pos": p.get("positionCode", ""), "gp": p.get("gamesPlayed", 0),
                     "g": p.get("goals", 0), "a": p.get("assists", 0), "p": p.get("points", 0),
                     "pm": p.get("plusMinus", 0)} for p in sk[:6]],
        "goalies": [{"name": name(p), "gp": p.get("gamesPlayed", 0), "w": p.get("wins", 0),
                     "l": p.get("losses", 0), "otl": p.get("overtimeLosses", 0),
                     "svp": round(float(p.get("savePercentage", 0) or 0), 3),
                     "gaa": round(float(p.get("goalsAgainstAverage", 0) or 0), 2)} for p in gl[:2]],
    }


def leaders():
    raw = fetch(f"{API}/skater-stats-leaders/current?categories=points,goals,assists&limit=5")
    out = {}
    for cat in ("points", "goals", "assists"):
        out[cat] = [{"name": name(p), "team": p.get("teamAbbrev", ""), "value": p.get("value", 0)}
                    for p in raw.get(cat, []) or []]
    return out


def main():
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    teams = json.loads(LEAGUE.read_text(encoding="utf-8")).get("teams", {}) if LEAGUE.exists() else {}
    data = {"teams": dict(old.get("teams", {})), "leaders": old.get("leaders", {})}
    ok = 0
    for ab in sorted(teams):
        try:
            data["teams"][ab] = team_stats(ab)
            ok += 1
        except Exception as e:
            print(f"stats for {ab} failed, keeping old: {e}")
        time.sleep(0.2)
    try:
        data["leaders"] = leaders()
    except Exception as e:
        print(f"league leaders failed, keeping old: {e}")
    if not ok and not data["leaders"]:
        print("NHL API unavailable, keeping existing stats")
        return 0
    data["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    OUT.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved stats for {ok} teams")
    return 0


if __name__ == "__main__":
    sys.exit(main())
