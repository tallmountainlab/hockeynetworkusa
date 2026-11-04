#!/usr/bin/env python3
"""Save daily Cloudflare traffic for this site to data/traffic.json.

Needs two GitHub secrets: CF_API_TOKEN (Analytics Read) and CF_ZONE_ID.
Runs weekly from .github/workflows/traffic.yml. No dependencies.
"""
import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "traffic.json"
QUERY = """query($zone: String!, $since: Date!) {
  viewer { zones(filter: {zoneTag: $zone}) {
    httpRequests1dGroups(limit: 100, filter: {date_geq: $since}, orderBy: [date_ASC]) {
      dimensions { date } sum { requests pageViews } uniq { uniques }
    } } } }"""


def main():
    token, zone = os.environ.get("CF_API_TOKEN"), os.environ.get("CF_ZONE_ID")
    if not token or not zone:
        print("CF_API_TOKEN or CF_ZONE_ID secret missing, skipping")
        return 0
    since = (date.today() - timedelta(days=30)).isoformat()
    req = urllib.request.Request(
        "https://api.cloudflare.com/client/v4/graphql",
        data=json.dumps({"query": QUERY, "variables": {"zone": zone, "since": since}}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.loads(r.read().decode())
    if res.get("errors"):
        print("Cloudflare error:", res["errors"])
        return 1
    zones = res["data"]["viewer"]["zones"]
    rows = zones[0]["httpRequests1dGroups"] if zones else []
    old = json.loads(OUT.read_text()) if OUT.exists() else {"days": []}
    days = {d["date"]: d for d in old.get("days", [])}
    for g in rows:
        d = g["dimensions"]["date"]
        days[d] = {"date": d, "page_views": g["sum"]["pageViews"], "requests": g["sum"]["requests"],
                   "unique_visitors": g["uniq"]["uniques"]}
    OUT.write_text(json.dumps({"source": "cloudflare", "updated": date.today().isoformat(),
                               "days": [days[k] for k in sorted(days)]}, indent=1) + "\n")
    print(f"Saved {len(rows)} days")
    return 0


if __name__ == "__main__":
    sys.exit(main())
