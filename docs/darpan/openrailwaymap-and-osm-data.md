# OpenRailwayMap + OpenStreetMap — railway infrastructure data

Unlike the live/scraped sources in the main research (NTES, ETrain, datameet/railways — which cover
*trains and schedules*), this set covers the **track infrastructure itself**: individual tracks,
switches, signals, electrification, gauge, speed limits. Useful if the ETA model or the route map
needs real topology instead of a straight line between stations.

## 1. OpenRailwayMap — best starting point

[OpenRailwayMap](https://openrailwaymap.app/) is built on OpenStreetMap and focuses specifically on
railway infrastructure. It shows:

- Exact-ish track geometry / individual tracks
- Stations and yards
- Switches / points
- Track numbers/references
- Signals and signalling infrastructure
- Level crossings
- Electrification
- Track gauge
- Maximum speeds
- Bridges/tunnels
- Historical/abandoned railway infrastructure

The underlying OSM model represents a switch as a node with `railway=switch`, which can carry a
reference number and whether it's locally operated. (See the [tagging documentation](https://wiki.openstreetmap.org/wiki/ORM/T) below.)

## 2. The important part — it's not just a picture, it's queryable data

The map is a rendering of real OpenStreetMap objects, so the underlying geographic data can be
queried/downloaded directly. Conceptually:

```text
Track A
  ├── geometry: [lat/lon, lat/lon, ...]
  ├── gauge: 1676
  ├── electrified: yes
  ├── maxspeed: ...
  └── connected_to: ...

Switch 123
  ├── location: lat/lon
  ├── ref: 123
  └── connected tracks: A, B

Track B
  └── geometry: [...]
```

This matters because it's **railway topology**, not just a route line between two stations — the
switches and connections are modeled explicitly.

## 3. OpenRailwayMap GitHub + extraction tooling

- [OpenRailwayMap](https://github.com/OpenRailwayMap/OpenRailwayMap) — the main open-source project:
  map rendering code, tagging presets, validation rules.
- [OpenRailwayMap Exporter](https://github.com/chriamue/openrailwaymap-exporter) — downloads railway
  data via the Overpass API and extracts:
  - track length
  - GPS geometry
  - OSM IDs
  - connected elements
  - switches
  - bounding-box based extraction
  - JSON output
  - graph/SVG output

  Directly useful if building a custom railway graph rather than relying on a pre-made one.

## 4. Modeling it as a graph (not a linear route)

Instead of a flat route:

```text
Delhi → Lucknow → Gorakhpur
```

a proper railway graph looks like:

```text
             Track 102
                 |
                 |
             [Switch 7]
                / \
               /   \
              /     \
       Track 101     Track 103
          |             |
          |             |
      [Station A]   [Yard B]
```

Node/edge shape:

```text
Node
 ├── coordinates
 ├── station?
 ├── switch?
 ├── signal?
 └── other railway infrastructure

Edge
 ├── geometry
 ├── length
 ├── gauge
 ├── electrification
 ├── max speed
 ├── track reference
 └── direction
```

**[OpenRailRouting](https://github.com/geofabrik/OpenRailRouting)** — uses OSM railway data with a
GraphHopper-derived routing engine; supports railway routing, gauges, electrification, direction,
turn angles, and railway crossings. Good reference for turning OSM railway infrastructure into an
actual routable graph.

## 5. Tagging documentation (bookmark this)

[OpenRailwayMap OSM tagging documentation](https://wiki.openstreetmap.org/wiki/ORM/T) — explains
what each railway tag means, e.g.:

```text
railway=rail
railway=switch
railway=station
railway=signal
railway=level_crossing
railway=milestone
```

plus properties such as:

```text
gauge=
maxspeed=
electrified=
railway:local_operated=
ref=
```

`railway=switch` is specifically defined as a connection point between railway tracks.

## 6. Dataset directory

[Railway Data Sources — RailToolkit](https://github.com/railtoolkit/data-sources) — a
community-maintained list of railway datasets worldwide: tracks, stations, bridges, tunnels,
gauges, etc.

## Recommended pipeline, if building on this

```text
                    OpenStreetMap
                          │
                          ▼
                    Overpass API
                          │
                          ▼
                 Railway OSM objects
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
           Tracks                  Switches
              │                       │
              └───────────┬───────────┘
                          ▼
                   Railway Graph
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
           Routing     Analysis    Visualization
```

## Caveat

OSM/OpenRailwayMap is crowd-sourced. Completeness and accuracy of individual switches, signals,
track connections, and operational details varies by country/region — excellent as an open global
starting point, but not something to treat as authoritative for every switch or operational
attribute. The project itself is explicit about this: it's crowdsourced and updated daily, not an
official Indian Railways data feed.

## Where this fits our stack

- **Doesn't replace** `datameet/railways` (station list + train routes + schedules) — that's still
  the base schedule/topology layer for the ETA engine.
- **Adds** real track-level geometry (actual curve of the rails, not a straight line between
  stations) if the live map needs to look accurate rather than schematic, and switch/junction data
  if a more precise "how does this train physically get from A to B" model is ever needed.
- Lowest-effort use: pull Overpass API output for the specific route(s) being demoed, convert to
  GeoJSON, and use it to draw a more accurate route line under the live position marker instead of
  the straight-line/simplified geometry from `datameet/railways`.
