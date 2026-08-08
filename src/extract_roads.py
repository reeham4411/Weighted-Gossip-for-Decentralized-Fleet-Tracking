"""
Extract a real NYC drivable street network for the road-constrained mobility
robustness check (see run_road_mobility_comparison in gwg_simulation.py).

Fetches OpenStreetMap road geometry directly from the Overpass API (standard
library only -- no geopandas/shapely/osmnx dependency chain), projects it to
local planar metres with a flat-earth approximation (accurate to centimetres
over a 1km box, which is all this needs), and rescales it to fill exactly the
same AREA_M x AREA_M service area the rest of the simulation already uses (see
GRID_SIZE/REGION_SIZE in gwg_simulation.py) -- so region assignment, radio
range, and the congestion field all keep meaning unchanged; only how vehicles
move through that square changes.

Cached output is plain JSON (node id -> [x, y], edge list of [u, v, length_m])
so gwg_simulation.py and the tests can load it with the standard library only.

Simplification: every OSM way tagged as one of the driveable highway classes
below is treated as a two-way street regardless of its real oneway tag. That
matches this simulation's existing level of stylization (the congestion field
is already a synthetic centre-slow/edge-fast function of position, not real
per-street data) and keeps the graph a plain undirected one.

USAGE (from repo root, needs network access — run once, result is cached):
    python3 src/extract_roads.py
"""

import json
import math
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

import certifi

# The public Overpass instances are shared infrastructure and occasionally
# answer a well-formed query with a 504 under load; a mirror list plus retry
# with backoff is the standard way to fetch from them reliably.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
]
MAX_ATTEMPTS_PER_URL = 3
RETRY_BACKOFF_S = 15

# A real, densely-gridded Manhattan block (Flatiron/NoMad) -- dense enough that
# a 1km box contains a well-connected street mesh rather than a handful of
# arterial roads. The choice of neighbourhood doesn't matter to the model (the
# congestion field is already a stylized centre-slow/edge-fast function of
# position, not of any real traffic data here); what matters is a realistic
# block/intersection topology to move vehicles through.
CENTER_LAT, CENTER_LON = 40.7429, -73.9903

# Matches GRID_SIZE * REGION_SIZE in gwg_simulation.py (10 * 100m = 1000m).
# Keep these in sync — a mismatch would silently change vehicle density.
AREA_M = 1000.0
FETCH_HALF_WIDTH_M = AREA_M / 2

# The same highway classes osmnx's "drive" network_type keeps.
DRIVABLE_HIGHWAYS = (
    "motorway", "trunk", "primary", "secondary", "tertiary", "unclassified",
    "residential", "living_street", "service",
    "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link",
)

OUTPUT_PATH = "data/processed/road_network.json"


def _meters_per_degree(lat_deg):
    lat = math.radians(lat_deg)
    m_per_deg_lat = 111_132.92 - 559.82 * math.cos(2 * lat) + 1.175 * math.cos(4 * lat)
    m_per_deg_lon = 111_412.84 * math.cos(lat) - 93.5 * math.cos(3 * lat)
    return m_per_deg_lat, m_per_deg_lon


def fetch_overpass_json():
    m_per_deg_lat, m_per_deg_lon = _meters_per_degree(CENTER_LAT)
    d_lat = FETCH_HALF_WIDTH_M / m_per_deg_lat
    d_lon = FETCH_HALF_WIDTH_M / m_per_deg_lon
    south, north = CENTER_LAT - d_lat, CENTER_LAT + d_lat
    west, east = CENTER_LON - d_lon, CENTER_LON + d_lon

    highway_filter = "|".join(DRIVABLE_HIGHWAYS)
    query = (
        "[out:json][timeout:90];"
        f'(way["highway"~"^({highway_filter})$"]({south},{west},{north},{east}););'
        "(._;>;);"
        "out body;"
    )
    print(f"Querying Overpass for the drivable network at ({CENTER_LAT}, {CENTER_LON}), "
          f"+/-{FETCH_HALF_WIDTH_M:.0f}m bbox...")
    body = urllib.parse.urlencode({"data": query}).encode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "adaptive-gwg-research/1.0",
        "Accept": "application/json",
    }
    ctx = ssl.create_default_context(cafile=certifi.where())

    last_error = None
    for url in OVERPASS_URLS:
        for attempt in range(1, MAX_ATTEMPTS_PER_URL + 1):
            try:
                req = urllib.request.Request(url, data=body, headers=headers)
                with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
                    return json.load(resp)
            except (urllib.error.HTTPError, urllib.error.URLError) as exc:
                last_error = exc
                print(f"  {url} attempt {attempt}/{MAX_ATTEMPTS_PER_URL} failed "
                      f"({exc}); retrying in {RETRY_BACKOFF_S}s...")
                time.sleep(RETRY_BACKOFF_S)
    raise RuntimeError(
        f"Overpass API unreachable after trying {len(OVERPASS_URLS)} mirrors "
        f"x {MAX_ATTEMPTS_PER_URL} attempts each. Last error: {last_error}"
    )


def build_graph(osm):
    """Local planar (x, y) in metres, centred on CENTER_LAT/LON, plus an edge
    list from consecutive nodes along each fetched way."""
    m_per_deg_lat, m_per_deg_lon = _meters_per_degree(CENTER_LAT)

    node_ll = {}
    ways = []
    for el in osm["elements"]:
        if el["type"] == "node":
            node_ll[el["id"]] = (el["lat"], el["lon"])
        elif el["type"] == "way":
            ways.append(el["nodes"])

    positions = {
        node_id: ((lon - CENTER_LON) * m_per_deg_lon, (lat - CENTER_LAT) * m_per_deg_lat)
        for node_id, (lat, lon) in node_ll.items()
    }

    edges = []
    seen = set()
    for nodes in ways:
        for u, v in zip(nodes, nodes[1:]):
            if u not in positions or v not in positions or u == v:
                continue
            key = (u, v) if u < v else (v, u)
            if key in seen:
                continue
            seen.add(key)
            (x1, y1), (x2, y2) = positions[u], positions[v]
            length = math.hypot(x2 - x1, y2 - y1)
            if length > 0:
                edges.append((u, v, length))

    return positions, edges


def largest_connected_component(positions, edges):
    """A bbox cut can sever a road from the main mesh; keep only the piece a
    vehicle can actually traverse in full, rather than risk a stranded fleet."""
    adjacency = {n: [] for n in positions}
    for u, v, _ in edges:
        adjacency[u].append(v)
        adjacency[v].append(u)

    seen = set()
    best = set()
    for start in positions:
        if start in seen:
            continue
        component = {start}
        frontier = [start]
        while frontier:
            node = frontier.pop()
            for neighbour in adjacency[node]:
                if neighbour not in component:
                    component.add(neighbour)
                    frontier.append(neighbour)
        seen |= component
        if len(component) > len(best):
            best = component

    kept_positions = {n: positions[n] for n in best}
    kept_edges = [(u, v, length) for u, v, length in edges if u in best and v in best]
    return kept_positions, kept_edges


def rescale_to_service_area(positions):
    """
    Fit the graph exactly into [0, AREA_M] x [0, AREA_M], preserving aspect
    ratio (a single scale factor for both axes) so street angles and block
    shapes aren't distorted -- only translated and uniformly scaled.
    """
    xs = [p[0] for p in positions.values()]
    ys = [p[1] for p in positions.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    extent = max(max_x - min_x, max_y - min_y)
    scale = AREA_M / extent

    width = (max_x - min_x) * scale
    height = (max_y - min_y) * scale
    pad_x = (AREA_M - width) / 2
    pad_y = (AREA_M - height) / 2

    rescaled = {
        n: (round((x - min_x) * scale + pad_x, 3), round((y - min_y) * scale + pad_y, 3))
        for n, (x, y) in positions.items()
    }
    return rescaled, scale


def main():
    osm = fetch_overpass_json()
    positions, edges = build_graph(osm)
    if not positions or not edges:
        raise RuntimeError(
            "Overpass returned no drivable ways for this bbox -- pick a "
            "different CENTER_LAT/CENTER_LON."
        )

    positions, edges = largest_connected_component(positions, edges)
    positions, scale = rescale_to_service_area(positions)

    cache = {
        "nodes": {str(n): list(xy) for n, xy in positions.items()},
        "edges": [[str(u), str(v), round(length * scale, 3)] for u, v, length in edges],
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(cache, f)

    size_kb = os.path.getsize(OUTPUT_PATH) / 1024
    print(f"Saved {len(cache['nodes'])} nodes, {len(cache['edges'])} edges "
          f"to {OUTPUT_PATH} ({size_kb:.1f} KB)")
    print(f"Rescaled to fit a {AREA_M:.0f}m x {AREA_M:.0f}m service area "
          f"(source scale factor: {scale:.4f})")


if __name__ == "__main__":
    main()
