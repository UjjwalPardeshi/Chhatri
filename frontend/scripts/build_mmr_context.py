#!/usr/bin/env python3
"""
Builds frontend/src/content/mmrContext.json: the land-only hex lattice of the Mumbai Metropolitan
Region outside the 24 covered BMC zones. The console paints these cells with a SIMULATED
sales-vs-expected index (display only, never a payout), so only the geometry is generated here,
once, and committed.

SOURCE   OpenStreetMap (Overpass API, fetched once on the date in the output's `meta.generated`):
           - natural=coastline ways            -> land / sea split (land is left of the way)
           - natural=water, riverbank polygons -> lakes, reservoirs and creeks cut out of the land
           - boundary=administrative relations -> the region: Mumbai City and Suburban districts,
             the Thane, Kalyan, Ulhasnagar, Ambernath, Bhiwandi, Vasai, Panvel and Uran
             sub-districts and the ten municipal corporations (labels for the tooltip)
         src/mock/data/zones.json (DataMeet BMC wards) -> the covered zones, which get no context cell
LICENCE  OpenStreetMap data: Open Database Licence 1.0 (ODbL), (c) OpenStreetMap contributors,
         https://www.openstreetmap.org/copyright . The committed JSON is a Derived Database
         (cells only, no OSM geometry); attribution is shown on the map and in the footer.
         Ward geometry: DataMeet Municipal_Spatial_Data, CC BY-SA 2.5 India.

USAGE    python3 -m venv /tmp/v && /tmp/v/bin/pip install shapely numpy requests
         /tmp/v/bin/python frontend/scripts/build_mmr_context.py [--cache DIR]
         The Overpass answers are cached in DIR (default /tmp/mmr-osm-cache), so a re-run is offline.

Cell lattice: pointy-top hexagons in Web Mercator metres (circumradius CELL_RADIUS_M), so they look
regular on the OSM tiles. A cell is kept when its centre is on land inside the region, at least
MIN_LAND_SHARE of its area is land, and it does not overlap a covered zone. The output stores runs
of columns per row, so the whole file is a few tens of KB; the app rebuilds the vertices.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import date
from pathlib import Path

import numpy as np
import requests
import shapely
import shapely.prepared
from shapely.geometry import Polygon, box
from shapely.ops import polygonize, unary_union

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'frontend' / 'src' / 'content' / 'mmrContext.json'
ZONES = ROOT / 'frontend' / 'src' / 'mock' / 'data' / 'zones.json'
OVERPASS = 'https://overpass-api.de/api/interpreter'
UA = {'User-Agent': 'ChhatriHackathon/1.0 (one-off geometry build; rlfb.git@gmail.com)'}

BBOX = (18.70, 72.65, 19.65, 73.45)  # south, west, north, east (Overpass order)
CELL_RADIUS_M = 640.0  # Mercator metres; flat-to-flat about 1.05 km true, near the res-8 H3 cells of the covered zones
MIN_LAND_SHARE = 0.72
MIN_WATER_KM2 = 0.15
SIMPLIFY_DEG = 0.0002  # about 20 m
R_EARTH = 6378137.0

CORPORATIONS = {
    13184109: 'Bhiwandi', 7120000: 'Thane', 13180677: 'Mira-Bhayandar', 13253971: 'Vasai-Virar',
    13184538: 'Kalyan-Dombivli', 13184432: 'Ulhasnagar', 13184373: 'Ambernath', 7119985: 'Badlapur',
    13180880: 'Navi Mumbai', 13182526: 'Panvel', 10353549: 'Uran',
}
DISTRICTS = {7964375: 'Greater Mumbai', 7964376: 'Greater Mumbai'}
SUBDISTRICTS = {
    10350460: 'Vasai area', 10351344: 'Thane area', 10351345: 'Kalyan area', 10351346: 'Ulhasnagar area',
    10351347: 'Ambernath area', 10351350: 'Bhiwandi area', 10353552: 'Panvel area',
}


def overpass(cache: Path, name: str, query: str) -> dict:
    file = cache / f'{name}.json'
    if file.exists():
        return json.loads(file.read_text())
    for attempt in range(4):
        response = requests.post(OVERPASS, data={'data': query}, headers=UA, timeout=240)
        if response.status_code == 200:
            file.write_text(response.text)
            return response.json()
        print(f'overpass {name}: HTTP {response.status_code}, retrying')
        time.sleep(15 * (attempt + 1))
    raise SystemExit(f'overpass {name} failed')


def fetch_all(cache: Path) -> dict[str, dict]:
    cache.mkdir(parents=True, exist_ok=True)
    s, w, n, e = BBOX
    b = f'({s},{w},{n},{e})'
    ids = lambda m: ','.join(map(str, m))  # noqa: E731
    return {
        'adm': overpass(cache, 'adm_geom', f'[out:json][timeout:180];rel(id:{ids([*CORPORATIONS, *DISTRICTS])});out geom;'),
        'sub': overpass(cache, 'sub_geom', f'[out:json][timeout:180];rel(id:{ids(SUBDISTRICTS)});out geom;'),
        'coast': overpass(cache, 'coast', f'[out:json][timeout:180];way["natural"="coastline"]{b};out geom;'),
        'water': overpass(
            cache,
            'water',
            '[out:json][timeout:180];(way["natural"="water"]["water"~"lake|reservoir|river|lagoon|canal"]%s;'
            'rel["natural"="water"]["water"~"lake|reservoir|river|lagoon"]%s;way["waterway"="riverbank"]%s;);out geom;' % (b, b, b),
        ),
    }


def line(points: list[dict]) -> list[tuple[float, float]]:
    return [(p['lon'], p['lat']) for p in points]


def relation_polygon(element: dict) -> shapely.Geometry:
    """Assembles a multipolygon relation from its member ways (outer rings minus inner rings)."""
    def merged(role: str):
        lines = [shapely.LineString(line(m['geometry'])) for m in element.get('members', []) if m['type'] == 'way' and m['role'] == role and len(m.get('geometry', [])) > 1]
        return unary_union([Polygon(p.exterior) for p in polygonize(unary_union(lines))]) if lines else Polygon()
    outer = merged('outer')
    inner = merged('inner')
    return outer.difference(inner) if not inner.is_empty else outer


def land_polygon(coast: dict, bbox: Polygon) -> shapely.Geometry:
    """Land = the bbox faces that lie on the left of the coastline direction (OSM convention)."""
    lines = [shapely.LineString(line(e['geometry'])) for e in coast['elements'] if len(e.get('geometry', [])) > 1]
    all_lines = unary_union(lines)
    noded = unary_union([all_lines, bbox.boundary])
    land = []
    for face in polygonize(noded):
        if not face.intersects(bbox) or face.intersection(bbox).area < face.area * 0.5:
            continue
        side = face.boundary.intersection(all_lines)
        parts = [g for g in getattr(side, 'geoms', [side]) if g.geom_type == 'LineString' and g.length > 0]
        if not parts:
            continue
        seg = max(parts, key=lambda g: g.length)
        mid = seg.interpolate(0.5, normalized=True)
        # `intersection` does not keep the way direction: read it from the nearest original way.
        way = min(lines, key=lambda g: g.distance(mid))
        at = way.project(mid)
        a, b = way.interpolate(max(at - 1e-5, 0.0)), way.interpolate(min(at + 1e-5, way.length))
        dx, dy = b.x - a.x, b.y - a.y
        norm = math.hypot(dx, dy) or 1.0
        eps = 1e-5
        left = shapely.Point(mid.x - dy / norm * eps, mid.y + dx / norm * eps)
        if face.contains(left):
            land.append(face)
    return unary_union(land).intersection(bbox)


def water_polygons(water: dict) -> shapely.Geometry:
    polys = []
    for e in water['elements']:
        if e['type'] == 'way' and len(e.get('geometry', [])) > 3 and e['geometry'][0] == e['geometry'][-1]:
            polys.append(Polygon(line(e['geometry'])))
        elif e['type'] == 'relation':
            polys.append(relation_polygon(e))
    deg_km2 = 111.0 * 111.0 * math.cos(math.radians(19.0))
    return unary_union([p.buffer(0) for p in polys if not p.is_empty and p.area * deg_km2 >= MIN_WATER_KM2])


def named(elements: list[dict], names: dict[int, str]) -> list[tuple[str, shapely.Geometry]]:
    return [(names[e['id']], relation_polygon(e).buffer(0)) for e in elements if e['id'] in names]


def merc(lng: float, lat: float) -> tuple[float, float]:
    return R_EARTH * math.radians(lng), R_EARTH * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def unmerc(x: float, y: float) -> tuple[float, float]:
    return math.degrees(x / R_EARTH), math.degrees(2 * math.atan(math.exp(y / R_EARTH)) - math.pi / 2)


def hex_polygon(cx: float, cy: float, s: float) -> Polygon:
    return Polygon([unmerc(cx + s * math.cos(math.radians(60 * k - 30)), cy + s * math.sin(math.radians(60 * k - 30))) for k in range(6)])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', default='/tmp/mmr-osm-cache')
    args = parser.parse_args()
    data = fetch_all(Path(args.cache))

    south, west, north, east = BBOX
    bbox = box(west, south, east, north)
    land = land_polygon(data['coast'], bbox).simplify(SIMPLIFY_DEG)
    water = water_polygons(data['water'])
    corporations = named(data['adm']['elements'], CORPORATIONS)
    districts = named(data['adm']['elements'], DISTRICTS)
    subdistricts = named(data['sub']['elements'], SUBDISTRICTS)
    region = unary_union([g for _, g in [*corporations, *districts, *subdistricts]]).buffer(0.002).buffer(-0.002)
    usable = land.intersection(region).difference(water).simplify(SIMPLIFY_DEG)
    zones = json.loads(ZONES.read_text())
    covered = unary_union([shapely.geometry.shape(f['geometry']) for f in zones['features']]).buffer(0)
    km2 = 111.0 * 111.0 * math.cos(math.radians(19.0))
    print(f'land {land.area * km2:.0f} km2, usable {usable.area * km2:.0f} km2')

    prepared = shapely.prepared.prep(usable)
    minx, miny, maxx, maxy = usable.bounds
    x0, y0 = merc(minx, miny)
    x1, y1 = merc(maxx, maxy)
    s = CELL_RADIUS_M
    width = math.sqrt(3) * s
    origin = (x0 - 2 * width, y0 - 2 * s)
    cols = int((x1 - origin[0]) / width) + 3
    rows = int((y1 - origin[1]) / (1.5 * s)) + 3
    labels = list(dict.fromkeys([*CORPORATIONS.values(), 'Greater Mumbai', *SUBDISTRICTS.values()]))
    order = [*corporations, *districts, *subdistricts]

    kept: dict[int, list[tuple[int, int]]] = {}
    for row in range(rows):
        for col in range(cols):
            cx = origin[0] + col * width + (width / 2 if row % 2 else 0.0)
            cy = origin[1] + row * 1.5 * s
            centre = shapely.Point(*unmerc(cx, cy))
            if not prepared.contains(centre):
                continue
            cell = hex_polygon(cx, cy, s)
            if cell.intersection(usable).area < MIN_LAND_SHARE * cell.area:
                continue
            if cell.intersection(covered).area > 0.15 * cell.area or covered.contains(centre):
                continue
            name = next((n for n, g in order if g.contains(centre)), subdistricts[0][0])
            kept.setdefault(row, []).append((col, labels.index(name)))

    runs: list[list] = []
    total = 0
    for row in sorted(kept):
        cells = sorted(kept[row])
        total += len(cells)
        flat: list[int] = []
        start, length, label = cells[0][0], 1, cells[0][1]
        for col, lab in cells[1:]:
            if col == start + length and lab == label:
                length += 1
            else:
                flat += [start, length, label]
                start, length, label = col, 1, lab
        flat += [start, length, label]
        runs.append([row, flat])

    out = {
        'meta': {
            'what': 'Land-only hex lattice of the Mumbai Metropolitan Region outside the 24 covered BMC zones. Geometry only: the sales-vs-expected value on these cells is simulated by the console, display only, never a payout.',
            'source': 'OpenStreetMap (Overpass API): coastline, water, administrative boundaries. Covered wards excluded: DataMeet Municipal_Spatial_Data.',
            'licence': 'ODbL 1.0, (c) OpenStreetMap contributors (https://www.openstreetmap.org/copyright). Ward geometry: CC BY-SA 2.5 India (DataMeet).',
            'generated': date.today().isoformat(),
            'script': 'frontend/scripts/build_mmr_context.py',
            'cells': total,
        },
        'lattice': {'x0': round(origin[0], 1), 'y0': round(origin[1], 1), 'radius': s},
        'regions': labels,
        'rows': runs,
    }
    OUT.write_text(json.dumps(out, separators=(',', ':')) + '\n')
    print(f'{total} cells, {OUT.stat().st_size / 1024:.1f} KB -> {OUT}')


if __name__ == '__main__':
    main()
