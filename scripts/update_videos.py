#!/usr/bin/env python3
"""Pull the latest NHL and Utah Mammoth YouTube videos, with view counts and
thumbnails, into data/videos.json. The site uses them for "most viewed"
highlights and for each team's video row (videos play in YouTube's player).

Needs the YT_API_KEY repo secret (a free YouTube Data API v3 key).
Without it the script does nothing and the site falls back to NHL.com links.
Cost: about 6 quota units a run out of the free 10,000 a day.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "videos.json"
LEAGUE = ROOT / "data" / "league.json"
API = "https://www.googleapis.com/youtube/v3"
CHANNELS = {
    "NHL": "UCqFMzb-4AUf6WAIbl132QKA",
    "UTA": "UCT0uj5F-RnIAqkp0XLSMaqg",  # Utah Mammoth
}
KEEP_DAYS = 14


def get(path, **params):
    params["key"] = os.environ["YT_API_KEY"]
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def team_matchers():
    teams = json.loads(LEAGUE.read_text(encoding="utf-8")).get("teams", {}) if LEAGUE.exists() else {}
    out = []
    for ab, t in teams.items():
        names = {t.get("common", ""), t.get("name", "")} - {""}
        out.append((ab, re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\b", re.I)))
    return out


def kind(title):
    t = title.lower()
    if "highlights" in t and (" vs" in t or " at " in t or " @ " in t):
        return "game"
    if "goal" in t or "scores" in t or "snipe" in t or "save" in t:
        return "clip"
    return "video"


def main():
    if not os.environ.get("YT_API_KEY"):
        print("YT_API_KEY secret not set, skipping videos")
        return 0
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"videos": []}
    match = team_matchers()
    found = {}
    try:
        for src, ch in CHANNELS.items():
            uploads = "UU" + ch[2:]
            ids, token = [], None
            for _ in range(2 if src == "NHL" else 1):
                q = {"part": "contentDetails", "playlistId": uploads, "maxResults": 50}
                if token:
                    q["pageToken"] = token
                res = get("playlistItems", **q)
                ids += [i["contentDetails"]["videoId"] for i in res.get("items", [])]
                token = res.get("nextPageToken")
                if not token:
                    break
            for i in range(0, len(ids), 50):
                res = get("videos", part="snippet,statistics,contentDetails", id=",".join(ids[i:i + 50]))
                for v in res.get("items", []):
                    sn, st = v["snippet"], v.get("statistics", {})
                    if v.get("contentDetails", {}).get("duration", "PT") in ("P0D",):
                        continue
                    title = sn.get("title", "")
                    teams = sorted({ab for ab, rx in match if rx.search(title)})
                    if src == "UTA" and "UTA" not in teams:
                        teams.append("UTA")
                    th = sn.get("thumbnails", {})
                    thumb = (th.get("high") or th.get("medium") or th.get("default") or {}).get("url", "")
                    found[v["id"]] = {
                        "id": v["id"], "title": title, "published": sn.get("publishedAt", ""),
                        "views": int(st.get("viewCount", 0) or 0), "thumb": thumb, "channel": src,
                        "teams": teams, "kind": kind(title),
                    }
    except Exception as e:
        print(f"YouTube API error, keeping existing videos: {e}")
        return 0

    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for v in old.get("videos", []):
        if v["id"] not in found and v.get("published", "") >= cutoff:
            found[v["id"]] = v
    vids = sorted((v for v in found.values() if v["published"] >= cutoff), key=lambda v: v["published"], reverse=True)
    OUT.write_text(json.dumps({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "videos": vids},
                              separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {len(vids)} videos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
