# Weather & Environmental Factors Module ⛅

## Purpose
Integrates atmospheric and meteorological features that physically throttle train speeds and cause severe seasonal delays across Indian Railways corridors.

## Key Meteorological Factors & Operational Rules

### 1. Dense Fog & Winter Visibility (The Northern Corridor Bottleneck)
- **Period:** December 10 – February 15.
- **Affected Zones:** Northern Railway (NR), North Central (NCR), North Eastern (NER), East Central (ECR).
- **Indian Railways G&SR Rule:**
  - When visibility drops below **600 meters**, loco pilots must not exceed **60 km/h** (standard rule).
  - If the locomotive is fitted with a functional GPS **FOG-PASS** device, the speed limit is relaxed to **75 km/h**.
  - Detonator / audible warning fog signals must be placed at signal approaches.
  - Trains with nominal 130 km/h MPS run at 60–75 km/h, creating massive 4–12 hour delays.

### 2. Monsoon, Flash Floods & Waterlogging
- **Affected Areas:** Mumbai Suburban (WR/CR), Konkan Railway, Assam / Northeast Frontier (NFR), Kerala.
- **Rules:**
  - Water above rail flange: Max speed **10 km/h** or traffic halted completely.
  - **Konkan Railway Monsoon Timetable:** Speed slashed from 110 km/h to 75–90 km/h across the entire 741 km line from June 10 to October 31.

### 3. Summer Heat Waves & Track Buckling Risk
- **Period:** April – June (>45°C ambient temperature).
- **Physics:** Continuous Welded Rails (CWR) expand under thermal stress, risking explosive track buckling.
- **Rule:** Hot weather patrolling deployed; speed capped during peak sun hours (12:00 PM – 5:00 PM) if rail temperature exceeds $T_d + 20^\circ\text{C}$.

## Target Data Schema (`weather_features.csv`)
| Column | Type | Description |
|---|---|---|
| `station_code` | TEXT | Nearest weather observation station |
| `timestamp` | TIMESTAMP | Observation time |
| `visibility_meters`| FLOAT | Atmospheric visibility (meters) |
| `is_foggy` | BOOLEAN | True if visibility < 600m |
| `fog_speed_limit` | INTEGER | Imposed G&SR cap (60 or 75 km/h) |
| `rainfall_mm` | FLOAT | Precipitation in last hour |
| `rail_temperature` | FLOAT | Estimated/measured rail surface temp (°C) |
| `monsoon_flag` | BOOLEAN | True if operating under monsoon timetable rules |
