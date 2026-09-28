# UI Structure — Dynamic ETA Pipeline (SIH26028)

## 1. Core interaction model: one search box, three input types

There's no separate "search train" / "search station" / "search PNR" screen. One universal search bar
on the home screen figures out what was typed and routes to the right view:

| User types | Detected as | Goes to |
|---|---|---|
| `12951` or `Mumbai Rajdhani` | Train number / name | **Train Detail** screen |
| `NDLS` or `New Delhi` | Station code / name | **Station Board** screen |
| 10-digit PNR | PNR | **PNR Status** screen (embeds Train Detail for that journey) |
| Two stations (`From: NDLS` → `To: BCT`) | Station pair | **Trains Between Stations** — a list, tap one → Train Detail |

If the text is ambiguous (e.g. "Howrah" matches a station and several train names), show a small
disambiguation list before committing to a screen — don't guess wrong and dead-end the user.

## 2. The flagship screen: Train Detail

This is the one query you described — everything about a train's *right now* in a single view, no
tab-switching. Layout, top to bottom:

```
┌─────────────────────────────────────────────────────────┐
│  12951  Mumbai Rajdhani                    [● DELAYED]   │  ← train id/name + status pill
│  NDLS → BCT · today                                       │
├─────────────────────────────────────────────────────────┤
│                                                           │
│              [ live map: route line +                   │  ← RouteMap component
│                current position marker ]                 │     (Leaflet, datameet geometry)
│                                                           │
├─────────────────────────────────────────────────────────┤
│  Last seen: Kota Jn · 6 min ago · running 42 min late    │  ← current position strip
├─────────────────────────────────────────────────────────┤
│  ⚠ Why is it late?                                        │  ← ONLY rendered if delayed
│  Heavy fog near Kota this morning pushed back the         │     (RAG assistant, one-shot
│  outbound slot; the train is also carrying a late         │      generated explanation,
│  incoming rake from yesterday's Delhi–Kota service.       │      no chat needed for MVP)
│  [fog↑] [late incoming rake↑] [zone congestion: NR]       │  ← same explanation as tags
│  Ask a follow-up →                                        │  ← optional expand to chat
├─────────────────────────────────────────────────────────┤
│  Upcoming stations                                        │  ← RouteMap + StationRow list
│  Kota Jn        ✓ arrived · was +38 min                   │
│  Sawai M. Jn    ETA 14:52 (sched 14:10) · +42 min          │
│  Jaipur         ETA 16:30 (sched 15:48) · +42 min          │
│  ...                                                       │
└─────────────────────────────────────────────────────────┘
```

Rules that keep this screen honest instead of decorative:
- The "Why is it late?" block **only renders when `delay_minutes > threshold`** — an on-time train
  shows a plain green "Running on time" strip and nothing else. Don't manufacture an explanation for
  a 3-minute variance.
- The delay-cause tags come from the same feature vector the model used (`fog_risk_score`,
  `late_incoming_rake`, `zone_congestion_index`) — the RAG text and the tags must agree, since a
  judge will click both.
- ETA per upcoming station updates from the same `eta_engine` push that updates the map marker —
  one data source, no risk of the map and the list disagreeing.

## 3. Other screens

**Station Board** (`/station/:code`) — like a departure board: live arrivals/departures at that
station in the next few hours, each row showing scheduled vs. current ETA and a delay pill. Tapping
a row opens that train's Train Detail screen.

**PNR Status** (`/pnr/:number`) — booking/chart/seat info up top (existing IRCTC-style data), then
the *same* Train Detail block underneath for that specific train, so a passenger checking their PNR
also sees exactly when their train will actually arrive.

**Trains Between Stations** (`/between?from=&to=`) — a results list (train name, departure/arrival,
current status pill per train) sorted by departure time; tap through to Train Detail.

**Control Room view** (`/control-room`, staff-facing, not in the passenger nav) — the aggregate
version of the same data: a zone map colored by congestion, a table of currently-delayed trains
sorted by severity, and the same RAG box but scoped to "why is this *zone* struggling today,"
matching the PS's ask for a controller-facing dashboard.

## 4. Frontend structure

```
web/src/
├── routes/
│   ├── Home.tsx                 # universal search
│   ├── TrainDetail.tsx           # the flagship screen
│   ├── StationBoard.tsx
│   ├── PnrStatus.tsx
│   ├── TrainsBetween.tsx
│   └── ControlRoom.tsx           # staff view
├── components/
│   ├── SearchBar.tsx              # detects input type, routes
│   ├── RouteMap.tsx                # Leaflet + datameet geometry + live marker
│   ├── DelayBadge.tsx              # on-time / delayed pill, shared everywhere
│   ├── WhyLateBox.tsx              # renders RAG explanation + cause tags
│   ├── StationRow.tsx              # one row in board/upcoming-stations list
│   └── TrainCard.tsx               # one row in a search-results list
└── api/
    └── client.ts                  # thin wrapper around the FastAPI endpoints
```

Endpoints this consumes (already planned in `api/`): `GET /trains/:id`, `GET /stations/:code/board`,
`GET /pnr/:number`, `GET /trains/between?from=&to=`, `POST /trains/:id/why-late`.

## 5. Roadmap — making it publicly useful, past the hackathon MVP

The MVP above answers "where is my train and why is it late." A real public tool needs to answer
more of the questions people actually have. Roughly in the order they'd add value:

**Quick wins (weeks, not months)**
- **Alerts** — "notify me 30 min before arrival" / "notify if delay crosses 20 min," via push
  notification (PWA) or SMS for passengers without a smartphone. This is the single highest-value
  addition — most people don't want to keep a tab open, they want to be told.
- **Save a journey** — bookmark a PNR/train so it's one tap away next time, no re-typing.
- **Historical reliability score** — "this train has run on time 61% of the time this monsoon" on
  the Train Detail screen, computed from the same `live_events` table you're already collecting.
  Builds trust by being honest about a train's track record, not just today's status.

**Public-utility features**
- **Feeder transport suggestion** — once ETA is known, surface nearby auto/cab/bus options at the
  destination station (the original PS explicitly calls this out). Even a static "these stands are
  at Exit 2" note is useful before any live integration.
- **Alternate-route nudge** — if a passenger's connecting train is likely to be missed given the
  current delay, proactively suggest the next available connection.
- **Crowdsourced ground reports** — let passengers/station staff flag "train has arrived," "wrong
  platform," "AC not working" for a specific journey. Cheap to build (a form + a table), and it
  patches the gaps in NTES coverage (GPS lag, remote sections with weak signal).
- **Voice + regional language input** — type or speak a train name in Hindi/regional script; matches
  the accessibility language most SIH health/education PS statements assume, and Railways serves an
  audience where this genuinely matters.
- **Low-data mode** — a text-only fallback view (no map tiles) for 2G/patchy rural connections, or an
  SMS-keyword query path (`SEND STATUS 12951 to XXXXX`) for feature-phone users.

**Ecosystem / integration (this is what turns it from "our hackathon project" into infrastructure)**
- **Public API** — expose `/trains/:id`, `/stations/:code/board` etc. as a documented public API,
  exactly as the PS asks for ("APIs for integration with mobile apps, station displays, control room
  dashboards"). Other apps and even station digital signage could consume it directly.
- **Station display board integration** — the same board data feeding a physical/kiosk display.
- **Zone-level analytics for Railways staff** — expand the Control Room view into a proper ops
  dashboard: recurring bottleneck routes, seasonal delay patterns, per-zone congestion trends —
  turns the project from a passenger tool into something Railways itself would want to keep running.

Sequence these roughly as: **alerts + reliability score first** (cheap, highest passenger value,
reuses data you already have) → **feeder transport + alternate-route nudges** (differentiates from
every other "just shows a map" ETA project) → **API + station-board integration** (the "this could
actually ship" pitch for judges) → crowdsourcing and low-data mode as stretch goals if time allows.
