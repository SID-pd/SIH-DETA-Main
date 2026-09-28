# Network Anomalies & Operational Incidents 🚨

## Purpose
Tracks and models non-nominal, stochastic operational disruptions that derail deterministic timetable schedules.

## Categories of Anomalies in Indian Railways

### 1. Signal & Telecom (S&T) Failures
- **Track Circuit Failures & Red Signal Locking:**
  - In an Automatic Block section, when a signal fails, trains must proceed under "Stop and Proceed" rules (stop for 1–2 minutes, then proceed at **10–15 km/h** with extreme caution).
  - In Absolute Block, stations revert to manual **Paper Line Clear Ticket (PLCT)**, causing 1-to-2 hour backlogs per section.

### 2. Overhead Equipment (OHE) & Traction Failures
- Pantograph entanglement, bird-hits, or grid feeder tripping cutting electric power.
- Trains coast to a halt; diesel rescue locos must be dispatched.

### 3. Alarm Chain Pulling (ACP) & Brake Binding
- Occurs on passenger trains when passengers pull the emergency chain.
- Requires the train crew to walk along the 24 coaches, locate the clack valve, reset it, and wait for brake pipe pressure to rebuild to $5.0 \text{ kg/cm}^2$.
- Average unpredicted detention: **15 to 25 minutes**.

### 4. Cattle Run-Over (CRO) & Track Obstructions
- Highly frequent on semi-high-speed corridors (e.g., Vande Bharat on Delhi–Varanasi or Mumbai–Ahmedabad).
- Requires emergency braking inspection, brake pipe leak check, and clearance of track before restarting (**15 to 40 minutes delay**).

### 5. Junction Outer Signal Queuing
- Platform starvation: Trains reach the outer home signal of major junctions (Kanpur, Prayagraj, Itarsi, Vijayawada) on time, but halt for **20 to 45 minutes** waiting for an empty platform or interlocking clearance.

## Target Data Schema (`anomalies.csv`)
| Column | Type | Description |
|---|---|---|
| `incident_id` | TEXT | Unique incident hash |
| `timestamp` | TIMESTAMP | Time incident began |
| `train_number` | TEXT | Affected train (or "SECTION" if track-wide) |
| `section_id` | TEXT | Block section (e.g., `CNB-PRYJ`) |
| `category` | TEXT | `SIGNAL_FAILURE`, `ACP`, `CRO`, `OHE_BREAKDOWN`, `OUTER_WAIT` |
| `detention_mins` | INTEGER | Total minutes lost |
| `status` | TEXT | `ACTIVE` or `RESOLVED` |
