"""Build per-town delivery routes for lawn-sign requests.

Usage: python3 build_routes.py REQUESTS.csv CAPTAINS.csv [OUT_DIR]

Free services only: U.S. Census geocoder (no key) and the public OSRM demo server.
Writes routes.csv, routes_map.html and geocode_cache.json to OUT_DIR (default: current folder).
"""
import csv
import itertools
import json
import os
import sys
import socket
import time
import urllib.parse

import requests
import urllib3.util.connection
from collections import defaultdict
from datetime import datetime

TOWN_HALLS = {  # (street, town, zip)
    "Duxbury": ("878 Tremont St", "Duxbury", "02332"),
    "Halifax": ("499 Plymouth St", "Halifax", "02338"),
    "Hanson": ("542 Liberty St", "Hanson", "02341"),
    "Marshfield": ("870 Moraine St", "Marshfield", "02050"),
    "Pembroke": ("100 Center St", "Pembroke", "02359"),
}
COLORS = ["#2a78d6", "#d6452a", "#1f9e6e", "#9b4fd1", "#d98a00", "#0aa3b8", "#c2378f"]
MAX_WAYPOINTS = 9  # Google Maps mobile limit on intermediate stops
CACHE_FILE = "geocode_cache.json"
UA = {"User-Agent": "jbr-lawn-sign-routing-poc"}
# Python on this Mac stalls ~20s per request trying IPv6 first; force IPv4.
urllib3.util.connection.allowed_gai_family = lambda: socket.AF_INET


def get_json(url, tries=3):
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))


# ---------- 1. load ----------
def load_requests(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))[3:]  # skip the three title rows
    header, body = rows[0], rows[1:]
    recs = [dict(zip(header, r)) for r in body if any(c.strip() for c in r)]
    keep = [r for r in recs
            if r["Installation Authorized"].strip().lower() == "yes"
            and r["Delivery Status"].strip().lower() != "delivered"]
    return recs, keep


def load_captains(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {r["Town"].strip(): r for r in csv.DictReader(f)}


# ---------- 3. geocode ----------
def geocode_all(addresses, cache):
    """Geocode (street, town, zip) tuples with the Census batch endpoint; ties and misses -> None."""
    todo = sorted({a for a in addresses if ", ".join(a) not in cache})
    if todo:
        body = "\n".join(f'{i},"{st}","{town}","MA","{z}"' for i, (st, town, z) in enumerate(todo))
        r = requests.post("https://geocoding.geo.census.gov/geocoder/locations/addressbatch",
                          data={"benchmark": "Public_AR_Current"},
                          files={"addressFile": ("addresses.csv", body)}, headers=UA, timeout=300)
        r.raise_for_status()
        for row in csv.reader(r.text.splitlines()):
            if not row or not row[0].isdigit():
                continue
            key = ", ".join(todo[int(row[0])])
            hit = None
            if len(row) > 5 and row[2] == "Match":
                lon, lat = map(float, row[5].split(","))
                hit = {"lat": lat, "lon": lon, "matched": row[4], "quality": row[3]}
            cache[key] = hit
        json.dump(cache, open(CACHE_FILE, "w"), indent=1)
    return {a: cache.get(", ".join(a)) for a in addresses}


# ---------- 4. route ----------
def osrm_matrix(points):
    coords = ";".join(f"{p['lon']},{p['lat']}" for p in points)
    data = get_json(f"https://router.project-osrm.org/table/v1/driving/{coords}?annotations=duration")
    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM table failed: {data.get('code')}")
    return data["durations"]


def osrm_route(points):
    coords = ";".join(f"{p['lon']},{p['lat']}" for p in points)
    data = get_json(f"https://router.project-osrm.org/route/v1/driving/{coords}"
                    "?overview=full&geometries=geojson")
    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM route failed: {data.get('code')}")
    rt = data["routes"][0]
    return rt["duration"], rt["distance"], rt["geometry"]["coordinates"]


def tour_cost(D, order):
    path = [0] + order + [0]
    return sum(D[a][b] for a, b in zip(path, path[1:]))


def solve_tsp(D):
    """Node 0 is the depot. Exact Held-Karp up to 14 stops, else nearest-neighbor + 2-opt."""
    n = len(D) - 1
    if n == 0:
        return []
    if n <= 14:
        best = {}
        for k in range(1, n + 1):
            best[(1 << (k - 1), k)] = (D[0][k], 0)
        for size in range(2, n + 1):
            for subset in itertools.combinations(range(1, n + 1), size):
                mask = sum(1 << (k - 1) for k in subset)
                for k in subset:
                    prev = mask & ~(1 << (k - 1))
                    best[(mask, k)] = min((best[(prev, m)][0] + D[m][k], m)
                                          for m in subset if m != k)
        full = (1 << n) - 1
        _, last = min((best[(full, k)][0] + D[k][0], k) for k in range(1, n + 1))
        order, mask = [], full
        while last:
            order.append(last)
            mask, last = mask & ~(1 << (last - 1)), best[(mask, last)][1]
        return order[::-1]
    unvisited, order, cur = set(range(1, n + 1)), [], 0
    while unvisited:
        cur = min(unvisited, key=lambda j: D[cur][j])
        order.append(cur)
        unvisited.remove(cur)
    improved = True
    while improved:
        improved = False
        for i in range(n - 1):
            for j in range(i + 1, n):
                cand = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                if tour_cost(D, cand) < tour_cost(D, order) - 1e-9:
                    order, improved = cand, True
    return order


def gmaps_links(points):
    """Split a closed tour into Google Maps links with at most MAX_WAYPOINTS intermediate stops."""
    links, step = [], MAX_WAYPOINTS + 1
    for s in range(0, len(points) - 1, step):
        chunk = points[s:s + step + 1]
        ll = [f"{p['lat']:.6f},{p['lon']:.6f}" for p in chunk]
        q = {"api": "1", "origin": ll[0], "destination": ll[-1], "travelmode": "driving"}
        if len(ll) > 2:
            q["waypoints"] = "|".join(ll[1:-1])
        links.append("https://www.google.com/maps/dir/?" + urllib.parse.urlencode(q, safe=",|"))
    return links


def main(req_path, cap_path):
    all_recs, recs = load_requests(req_path)
    captains = load_captains(cap_path)
    print(f"Loaded {len(all_recs)} requests; {len(recs)} authorized and not yet delivered.")

    cache = json.load(open(CACHE_FILE)) if os.path.exists(CACHE_FILE) else {}
    by_town = defaultdict(list)
    for r in recs:
        by_town[r["Town"].strip()].append(r)
    missing = sorted(t for t in by_town if t not in TOWN_HALLS)
    if missing:
        raise SystemExit(f"No Town Hall address for: {', '.join(missing)}")

    key = lambda r: (r["Street Address"].strip(), r["Town"].strip(), r["ZIP"].strip().zfill(5))
    geo = geocode_all([key(r) for r in recs] + list(TOWN_HALLS.values()), cache)

    failures, routes = [], []
    created = datetime.now().strftime("%Y-%m-%d %H:%M")
    for town in sorted(by_town):
        hall_key = TOWN_HALLS[town]
        hall, hall_addr = geo[hall_key], f"{hall_key[0]}, {town}, MA {hall_key[2]}"
        if not hall:
            raise SystemExit(f"{town} Town Hall did not geocode: {hall_addr}")
        stops, bad = [], []
        for r in by_town[town]:
            k = key(r)
            (stops if geo[k] else bad).append((r, f"{k[0]}, {town}, MA {k[2]}", geo[k]))
        failures += [(town, r["Request ID"], full) for r, full, _ in bad]

        points = [hall] + [g for _, _, g in stops]
        D = osrm_matrix(points)
        order = solve_tsp(D)
        tour = [hall] + [points[i] for i in order] + [hall]
        dur, dist, geom = osrm_route(tour)
        routes.append({
            "town": town, "hall_addr": hall_addr, "hall": hall,
            "ordered": [stops[i - 1] for i in order], "bad": bad,
            "duration_s": dur, "distance_m": dist, "geometry": geom,
            "links": gmaps_links(tour), "captain": captains.get(town, {}),
        })

    # ---------- 5. routes.csv ----------
    cols = ["Route ID", "Town", "Volunteer", "Route Token", "Stop", "Request ID", "Name", "Address",
            "Signs", "Status", "Reason", "Created", "Start", "End", "Active"]
    with open("routes.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for rt in routes:
            cap = rt["captain"]
            base = {"Route ID": f"{rt['town'][:3].upper()}-{datetime.now():%Y%m%d}",
                    "Town": rt["town"],
                    "Volunteer": cap.get("Captain Name") or cap.get("Captain Email", ""),
                    "Route Token": cap.get("Token", ""), "Created": created,
                    "Start": rt["hall_addr"], "End": rt["hall_addr"],
                    "Active": cap.get("Active", "")}
            for i, (r, full, _) in enumerate(rt["ordered"], 1):
                w.writerow({**base, "Stop": i, "Request ID": r["Request ID"], "Name": r["Full Name"],
                            "Address": full, "Signs": r["Number of Signs"], "Status": "Planned",
                            "Reason": ""})
            for r, full, _ in rt["bad"]:
                w.writerow({**base, "Stop": "", "Request ID": r["Request ID"], "Name": r["Full Name"],
                            "Address": full, "Signs": r["Number of Signs"], "Status": "Unrouted",
                            "Reason": "Address not matched by Census geocoder"})

    write_map(routes, failures)

    # ---------- 7. summary ----------
    print(f"\n{'Town':<12}{'Stops':>6}{'Signs':>7}{'Drive':>9}{'Miles':>7}{'Links':>7}")
    for rt in routes:
        signs = sum(int(r["Number of Signs"]) for r, _, _ in rt["ordered"])
        print(f"{rt['town']:<12}{len(rt['ordered']):>6}{signs:>7}"
              f"{rt['duration_s'] / 60:>7.0f} m{rt['distance_m'] / 1609.34:>7.1f}{len(rt['links']):>7}")
    print("\nDid not geocode:" if failures else "\nAll addresses geocoded.")
    for town, rid, addr in failures:
        print(f"  {rid}  {addr}")


def write_map(routes, failures):
    layers, panel = [], []
    for i, rt in enumerate(routes):
        color = COLORS[i % len(COLORS)]
        stops = [{"n": k, "lat": g["lat"], "lon": g["lon"], "id": r["Request ID"],
                  "name": r["Full Name"], "addr": full, "signs": r["Number of Signs"]}
                 for k, (r, full, g) in enumerate(rt["ordered"], 1)]
        layers.append({"town": rt["town"], "color": color, "hall": rt["hall"],
                       "hallAddr": rt["hall_addr"], "line": [[c[1], c[0]] for c in rt["geometry"]],
                       "stops": stops})
        signs = sum(int(s["signs"]) for s in stops)
        links = "".join(
            f'<a class="btn" style="--c:{color}" href="{u}" target="_blank" rel="noopener">'
            f'{"Open in Google Maps" if len(rt["links"]) == 1 else f"Part {j} of {len(rt["links"])}"}</a>'
            for j, u in enumerate(rt["links"], 1))
        panel.append(
            f'<section><h2><span class="dot" style="background:{color}"></span>{rt["town"]}</h2>'
            f'<p class="meta">{len(stops)} stops · {signs} signs · '
            f'{rt["duration_s"] / 60:.0f} min · {rt["distance_m"] / 1609.34:.1f} mi</p>'
            f'<p class="meta">Captain: {rt["captain"].get("Captain Name", "—")}</p>'
            f'<div class="links">{links}</div></section>')
    fail_html = ("".join(f"<li>{rid} — {addr}</li>" for _, rid, addr in failures)
                 or "<li>None</li>")
    html = TEMPLATE.replace("__PANEL__", "".join(panel)).replace("__FAILS__", fail_html) \
                   .replace("__DATA__", json.dumps(layers))
    open("routes_map.html", "w").write(html)


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lawn Sign Routes</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
:root{--bg:#fafaf8;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#e4e2dc}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161615;--fg:#ececea;--muted:#a3a39d;--card:#1f1f1d;--line:#33332f}}
:root[data-theme="dark"]{--bg:#161615;--fg:#ececea;--muted:#a3a39d;--card:#1f1f1d;--line:#33332f}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,sans-serif}
.wrap{display:grid;grid-template-columns:320px 1fr;height:100vh}
aside{overflow:auto;padding:16px;border-right:1px solid var(--line)}
h1{font-size:18px;margin:0 0 4px}h2{font-size:15px;margin:0 0 4px;display:flex;align-items:center;gap:8px}
.sub{color:var(--muted);margin:0 0 16px}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin-bottom:10px}
.dot{width:12px;height:12px;border-radius:50%;display:inline-block}
.meta{color:var(--muted);margin:2px 0}.links{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.btn{background:var(--c);color:#fff;text-decoration:none;padding:7px 10px;border-radius:7px;font-weight:600;font-size:13px}
#map{height:100%}.fails{color:var(--muted)}.fails ul{padding-left:18px;margin:4px 0}
.num{background:var(--c);color:#fff;border:2px solid #fff;border-radius:50%;width:24px;height:24px;
 display:flex;align-items:center;justify-content:center;font:700 11px system-ui;box-shadow:0 1px 3px #0006}
.hall{background:#1d1d1b;color:#fff;border:2px solid #fff;border-radius:6px;padding:2px 5px;font:700 11px system-ui;white-space:nowrap}
@media (max-width:760px){.wrap{grid-template-columns:1fr;grid-template-rows:auto 60vh;height:auto}
 aside{border-right:0;border-bottom:1px solid var(--line)}#map{height:60vh}}
</style></head><body><div class="wrap">
<aside><h1>Lawn sign delivery routes</h1>
<p class="sub">Synthetic proof-of-concept data. Each route starts and ends at Town Hall.</p>
__PANEL__
<div class="fails"><strong>Addresses that did not geocode</strong><ul>__FAILS__</ul></div>
</aside><div id="map"></div></div>
<script>
const DATA = __DATA__;
const map = L.map('map');
// Esri World Street Map: free for non-commercial use with attribution, no key,
// and no Referer requirement (tile.openstreetmap.org blocks requests without one,
// e.g. a downloaded copy opened locally or some privacy browsers).
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
  {maxZoom: 19, attribution: 'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors'}).addTo(map);
const all = [];
for (const t of DATA) {
  L.polyline(t.line, {color: t.color, weight: 4, opacity: .85}).addTo(map);
  L.marker([t.hall.lat, t.hall.lon], {icon: L.divIcon({className: '', html:
    `<div class="hall">${t.town} Town Hall</div>`, iconSize: null})})
    .bindPopup(`<b>${t.town} Town Hall</b><br>${t.hallAddr}`).addTo(map);
  for (const s of t.stops) {
    L.marker([s.lat, s.lon], {icon: L.divIcon({className: '', iconSize: [24, 24],
      html: `<div class="num" style="--c:${t.color}">${s.n}</div>`})})
      .bindPopup(`<b>${t.town} stop ${s.n}</b><br>${s.name}<br>${s.addr}<br>${s.signs} sign(s) · ${s.id}`)
      .addTo(map);
    all.push([s.lat, s.lon]);
  }
  all.push([t.hall.lat, t.hall.lon]);
}
map.fitBounds(all, {padding: [30, 30]});
</script></body></html>"""

if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    req, cap = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    out = sys.argv[3] if len(sys.argv) > 3 else "."
    os.makedirs(out, exist_ok=True)
    os.chdir(out)
    main(req, cap)
