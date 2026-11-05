#!/usr/bin/env python3
"""Find the ice rinks around every NHL city from OpenStreetMap (Overpass API)
and save them to data/local.json for the /local/<team>/ pages.

Rink data (c) OpenStreetMap contributors, ODbL. Runs weekly from
.github/workflows/local.yml (rinks don't change often). A city whose query
fails keeps its previous list.
"""
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "local.json"
ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
             "https://overpass.kumi.systems/api/interpreter"]
BUDGET_S = 20 * 60  # stop after 20 minutes and keep what we have
RADIUS_KM = 45
MAX_RINKS = 40

# team: (area name shown on the site, arena latitude, longitude, country)
CITIES = {
    "ANA": ("Orange County", 33.8078, -117.8765, "US"), "BOS": ("Boston", 42.3662, -71.0621, "US"),
    "BUF": ("Buffalo", 42.8750, -78.8764, "US"), "CAR": ("Raleigh", 35.8033, -78.7220, "US"),
    "CBJ": ("Columbus", 39.9692, -83.0061, "US"), "CGY": ("Calgary", 51.0374, -114.0519, "CA"),
    "CHI": ("Chicago", 41.8807, -87.6742, "US"), "COL": ("Denver", 39.7487, -105.0077, "US"),
    "DAL": ("Dallas", 32.7905, -96.8103, "US"), "DET": ("Detroit", 42.3411, -83.0553, "US"),
    "EDM": ("Edmonton", 53.5469, -113.4979, "CA"), "FLA": ("South Florida", 26.1584, -80.3256, "US"),
    "LAK": ("Los Angeles", 34.0430, -118.2673, "US"), "MIN": ("the Twin Cities", 44.9448, -93.1010, "US"),
    "MTL": ("Montréal", 45.4961, -73.5693, "CA"), "NJD": ("North Jersey", 40.7334, -74.1711, "US"),
    "NSH": ("Nashville", 36.1592, -86.7785, "US"), "NYI": ("Long Island", 40.7170, -73.7255, "US"),
    "NYR": ("New York City", 40.7505, -73.9934, "US"), "OTT": ("Ottawa", 45.2969, -75.9271, "CA"),
    "PHI": ("Philadelphia", 39.9012, -75.1720, "US"), "PIT": ("Pittsburgh", 40.4395, -79.9892, "US"),
    "SEA": ("Seattle", 47.6221, -122.3540, "US"), "SJS": ("San Jose", 37.3327, -121.9010, "US"),
    "STL": ("St. Louis", 38.6268, -90.2026, "US"), "TBL": ("Tampa Bay", 27.9427, -82.4518, "US"),
    "TOR": ("Toronto", 43.6435, -79.3791, "CA"), "UTA": ("Salt Lake City", 40.7683, -111.9011, "US"),
    "VAN": ("Vancouver", 49.2778, -123.1089, "CA"), "VGK": ("Las Vegas", 36.1029, -115.1784, "US"),
    "WPG": ("Winnipeg", 49.8928, -97.1436, "CA"), "WSH": ("Washington, D.C.", 38.8981, -77.0209, "US"),
}


def km(a, b, c, d):
    p = math.pi / 180
    h = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def rinks(lat, lon, endpoint):
    dy, dx = RADIUS_KM / 111.0, RADIUS_KM / (111.0 * math.cos(math.radians(lat)))
    bbox = f"{lat - dy:.4f},{lon - dx:.4f},{lat + dy:.4f},{lon + dx:.4f}"
    q = f'[out:json][timeout:80][bbox:{bbox}];nwr["leisure"="ice_rink"];out center tags;'
    req = urllib.request.Request(endpoint, data=urllib.parse.urlencode({"data": q}).encode(),
                                 headers={"User-Agent": "hockeynetworkusa.com local rinks updater"})
    with urllib.request.urlopen(req, timeout=100) as r:
        els = json.loads(r.read().decode("utf-8")).get("elements", [])
    out, seen = [], set()
    for e in els:
        t = e.get("tags", {})
        name = (t.get("name") or "").strip()
        if not name or name.lower() in seen:
            continue
        if (t.get("sport") or "").strip() == "curling" or "curling" in name.lower():
            continue  # curling sheets are tagged as ice rinks too
        y, x = (e.get("lat"), e.get("lon")) if e["type"] == "node" else (e.get("center", {}).get("lat"), e.get("center", {}).get("lon"))
        if y is None:
            continue
        if km(lat, lon, y, x) > RADIUS_KM:
            continue
        indoor = (t.get("indoor") == "yes" or t.get("covered") == "yes" or "building" in t
                  or e["type"] in ("way", "relation") and t.get("building") is not None)
        outdoor = t.get("indoor") == "no" or t.get("covered") == "no" or t.get("seasonal") == "yes"
        sports = (t.get("sport") or "").replace(";", " ").split()
        seen.add(name.lower())
        out.append({
            "name": name, "lat": round(y, 5), "lon": round(x, 5), "km": round(km(lat, lon, y, x), 1),
            "city": t.get("addr:city", ""), "street": " ".join(v for v in (t.get("addr:housenumber"), t.get("addr:street")) if v),
            "website": t.get("website") or t.get("contact:website") or "",
            "kind": "indoor" if indoor and not outdoor else "outdoor" if outdoor else "",
            "hockey": "ice_hockey" in sports, "skating": "ice_skating" in sports or "skating" in sports,
        })
    # rinks people can look up first: indoor, with a website, then by distance
    out.sort(key=lambda r: (r["kind"] != "indoor", not r["website"], r["km"]))
    return out[:MAX_RINKS]


def main():
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    cities = dict(old.get("cities", {}))
    ok, start, n = 0, time.time(), 0  # noqa
    order = sorted(CITIES, key=lambda ab: (len(cities.get(ab, {}).get("rinks", [])) > 0, cities.get(ab, {}).get("checked", "")))
    for ab in order:
        if time.time() - start > BUDGET_S:
            cities.setdefault(ab, {"area": CITIES[ab][0], "country": CITIES[ab][3], "lat": CITIES[ab][1], "lon": CITIES[ab][2], "rinks": []})
            continue
        area, lat, lon, country = CITIES[ab]
        prev = cities.get(ab, {})
        entry = {"area": area, "country": country, "lat": lat, "lon": lon, "rinks": prev.get("rinks", []), "checked": prev.get("checked", "")}
        for attempt in range(len(ENDPOINTS)):
            if time.time() - start > BUDGET_S:
                break
            ep = ENDPOINTS[(n + attempt) % len(ENDPOINTS)]
            try:
                entry["rinks"] = rinks(lat, lon, ep)
                entry["checked"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                ok += 1
                break
            except Exception as e:
                print(f"{ab} via {ep} failed: {e}", flush=True)
                time.sleep(5)
        n += 1
        cities[ab] = entry
        print(ab, len(entry["rinks"]), "rinks", flush=True)
        time.sleep(2)
    if not ok:
        print("Overpass unavailable, keeping existing file")
        return 0
    OUT.write_text(json.dumps({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "cities": cities},
                              separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved rinks for {ok} cities")
    return 0


if __name__ == "__main__":
    sys.exit(main())
