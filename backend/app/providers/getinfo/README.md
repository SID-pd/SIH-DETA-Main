# Get-info: Bulletproof Indian Railways Information Extraction Engine

High-reliability, fault-tolerant Python library and CLI tool for real-time train intelligence. Engineered with **multi-provider cascading failovers**, **circuit breakers**, **two-tier TTL caching**, and **deterministic offline heuristics** to ensure queries **work every single time**.

---

## 🚀 Capabilities

| Feature | Description | Primary Provider | Fallback Providers |
|---|---|---|---|
| **📍 Live Running Status** | Real-time station, next stop, delay in minutes, distance covered/remaining, progress percentage | ConfirmTkt Live Embedded Stream | CRIS NTES Live Telemetry ➡️ eRail Live |
| **🎫 PNR Status** | 10-digit PNR lookup with passenger booking vs current status, coach, berth, quota, chart status | ConfirmTkt Direct REST Gateway | RailYatri Gateway ➡️ Built-in Layout Enricher |
| **🚃 Coach Position & Rake** | Engine-to-guard rake sequence, coach categories, LHB vs ICF detection | ConfirmTkt Rake Sequence | eRail Coach Layout ➡️ Offline Rake Knowledge Base |
| **💺 Seat / Berth Calculator** | Exact mathematical layout mapping (LB, MB, UB, SL, SU, WS, AS, Cabin, Coupe) & ASCII bay diagrams | Offline Formulaic Engine (Deterministic) | All Indian Railways classes: 1A, 2A, 3A, 3E, SL, CC, EC, 2S |
| **⏱️ Complete Timeline** | Full scheduled vs actual stop-by-stop timetable with delays, halt times, and GPS coordinates | ConfirmTkt Rich Schedule | eRail Timetable |
| **⚠️ Operational Exceptions** | Official daily list of Rescheduled, Diverted (with skipped stops), and Cancelled trains | CRIS NTES Exception Gateway | Local Cached Feeds |

---

## 🛡️ "Works Every Time" Architecture

Typical scrapers break when external servers block IPs, return CAPTCHAs, or undergo midnight maintenance. `Get-info` overcomes this via:

1. **Provider Cascading**: Every query queries Provider A; if Provider A fails, it seamlessly and instantly falls back to Provider B, then Provider C.
2. **Circuit Breakers**: If a provider fails 3 consecutive times, it is tripped for 60s, failing fast so subsequent calls don't suffer timeout delays.
3. **Two-Tier TTL Caching**:
   - **Level 1**: Microsecond in-memory dictionary.
   - **Level 2**: Persistent SQLite database (`getinfo_cache.sqlite`).
   - Prevents IP bans, respects upstream rate limits, and returns instantaneous responses for frequent queries.
4. **Offline Rake Knowledge Base**: If all network scrapers fail, built-in deterministic templates for Rajdhani, Shatabdi, Vande Bharat, and standard 22-coach trains ensure coach layouts never return empty.

---

## 💻 Python Usage (SDK)

```python
from fetcher import InfoFetcher

fetcher = InfoFetcher()

# 1. Live Running Status
live = fetcher.get_live_status("12951")
print(f"Station: {live.current_station_name} | Delay: {live.delay_minutes} mins")

# 2. PNR Status
pnr = fetcher.get_pnr_status("1234567890")
for p in pnr.passengers:
    print(f"Passenger #{p.passenger_no}: {p.current_status} in Coach {p.coach}")

# 3. Coach Position & Rake
coach = fetcher.get_coach_position("12951")
print(f"Rake Type: {coach.rake_type} | Total: {coach.total_coaches}")

# 4. Exact Seat / Berth Layout
seat = fetcher.get_seat_layout("3A", 21)
print(f"{seat.berth_type} ({seat.berth_code}) in Bay #{seat.bay_number}")
print(seat.layout_diagram)

# 5. Full Journey Timeline
timeline = fetcher.get_timeline("12951")
for stop in timeline.stops[:5]:
    print(f"{stop.station_name} - Sch Arr: {stop.scheduled_arrival}, Dep: {stop.scheduled_departure}")

# 6. Operational Exceptions (Rescheduled / Diverted / Cancelled)
exceptions = fetcher.get_exceptions(date="today", exception_type="rescheduled")
for r in exceptions.rescheduled[:5]:
    print(f"Train {r.train_number}: New departure {r.rescheduled_departure} (Late: {r.delay_hours_mins})")
```

## 🎮 Interactive Menu Console

Run the continuous interactive terminal loop with numeric navigation:

```bash
cd experiment/Get-info

# Launch interactive console (exits on 0, 'q', or ESC)
python interactive.py
# or simply:
python cli.py
```

---

## 🖥️ Command-Line Interface (CLI)

```bash
cd experiment/Get-info

# Live status
python cli.py live 12951
python cli.py live 12951 --date yesterday

# PNR status
python cli.py pnr 1234567890

# Coach sequence and rake composition
python cli.py coach 12951

# Calculate berth type for any coach and seat
python cli.py seat 3A 21
python cli.py seat 2A 15
python cli.py seat 3E 8

# Full journey timeline
python cli.py timeline 12951

# Operational exceptions
python cli.py exceptions --type rescheduled
python cli.py exceptions --type diverted
python cli.py exceptions --type cancelled

# Visual all-in-one dashboard
python cli.py all 12951

# Raw JSON output for any command
python cli.py live 12951 --json
```

---

## 🧪 Testing

Run the test suite:
```bash
pytest tests/test_fetcher.py -v
```
