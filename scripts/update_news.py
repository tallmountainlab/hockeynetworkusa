#!/usr/bin/env python3
"""Pull the latest headlines for every NHL team (and the league) from
Google News RSS into data/news.json. The site shows headline, source and
date and links out to the original story; it never copies articles.

Runs from .github/workflows/update.yml. No dependencies. A failed feed
keeps that team's previous headlines.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "news.json"
LEAGUE = ROOT / "data" / "league.json"
PER_TEAM = 8


def feed(query):
    q = urllib.parse.quote(f"{query} when:4d")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (hockeynetworkusa.com news updater)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        root = ET.fromstring(r.read())
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        src_el = it.find("source")
        src = (src_el.text or "").strip() if src_el is not None else ""
        if src and title.endswith(" - " + src):
            title = title[: -len(src) - 3].strip()
        try:
            when = parsedate_to_datetime(it.findtext("pubDate")).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            when = ""
        if title and it.findtext("link"):
            items.append({"title": title, "source": src, "link": it.findtext("link").strip(), "date": when})
    items.sort(key=lambda x: x["date"], reverse=True)
    seen, out = set(), []
    for x in items:  # drop near-duplicate headlines from syndicated copies
        k = re.sub(r"\W+", "", x["title"].lower())[:60]
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def main():
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    teams = json.loads(LEAGUE.read_text(encoding="utf-8")).get("teams", {}) if LEAGUE.exists() else {}
    news = dict(old.get("teams", {}))
    league = old.get("league", [])
    ok = 0
    for ab, t in sorted(teams.items()):
        try:
            news[ab] = feed(f'"{t["name"]}" NHL')[:PER_TEAM]
            ok += 1
        except Exception as e:
            print(f"news for {ab} failed, keeping old: {e}")
        time.sleep(0.5)
    try:
        league = feed("NHL hockey")[:12]
    except Exception as e:
        print(f"league news failed, keeping old: {e}")
    if not ok:
        print("No news feeds reached, keeping existing file")
        return 0
    OUT.write_text(json.dumps({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                               "teams": news, "league": league}, separators=(",", ":"), ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"Saved news for {ok} teams, {len(league)} league headlines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
