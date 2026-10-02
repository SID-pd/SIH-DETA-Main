# SIH 2026 Introductory Pitch Video Script — Problem Statement ID: 26028

- **Problem Statement ID**: `26028`
- **Problem Statement Title**: *Dynamic Forecast of Expected Time of Arrival (ETA) for Coaching Trains*
- **Organization / Department**: Ministry of Railways
- **Category**: Software | **Theme**: Smart Automation
- **System Name**: **DARPAN (SIH-DETA / RailPulse)** — *Dynamic Arrival & Railway Predictive Analytics Network*
- **Target Video Duration**: **2 Minutes 45 Seconds – 3 Minutes 00 Seconds** *(Ideal SIH Jury Evaluation Length)*

---

## Director's Overview & Why This Script Gets Selected

SIH Ministry of Railways evaluators look for **four specific signals** in the first 60 seconds of a screening video:
1. **Domain Authenticity**: Do you understand real Indian Railways operations (*Section MPS, G&SR Fog Rules, Timetable Slack Padding, COA 6-Tier Priority, Outer Home Signal Starvation, NSG 1–6 Station Tiers*), or did you just train a generic regression model on CSV data?
2. **Why Pure Static Math & Pure Black-Box ML Both Fail**: Static apps use $\text{ETA} = \text{STA} + \text{Current Delay}$ (ignoring slack recovery and cascading congestion), while pure black-box ML has zero awareness of railway interlocking physics (predicting two trains arriving on Platform 1 at the exact same minute).
3. **Working Proof Over Slides**: Showing our **1.68 GB 6-Database Indian Railways Data Lake** (`13,114` network nodes, `15,802` coaching runs, `417,080` schedule stops, `1.51M` historical delay records, `3.19M` weather rows) and live UI (`https://doorpost-smashing-regime.ngrok-free.dev` / `http://localhost:5173`) in action.
4. **Actionable Ecosystem**: Serving all three stakeholders demanded by PS 26028 — **Passengers** ($P_{10}/P_{50}/P_{90}$ confidence bands), **Station Masters** (IntervalTree Platform Allocation & Surge Dwell Dilation), and **Section Controllers / Control Rooms** (Black Swan Circuit Breaker & Yen's 25kV AC Electrified Bypass Rerouting).

---

## Full Scene-by-Scene Script (Audio Narration + Screen Recording Cues)

### SCENE 1: The Hook & Problem Reality (`0:00 – 0:30`)

> **[VISUAL / SCREEN CUE]**
> - **0:00–0:10**: Open with a clean title card: **SIH 2026 | Problem Statement ID: 26028 | Ministry of Railways | Theme: Smart Automation** — *"Dynamic Forecast of Expected Time of Arrival (ETA) for Coaching Trains"*.
> - **0:10–0:20**: Cut to [`HomePage.tsx`](../frontend/src/pages/HomePage.tsx) (`Home` tab on `http://localhost:5173`). Scroll slowly into the **3D Live Fleet Satellite Radar** and the **"Traditional Rail Apps vs DARPAN" Algorithmic Benchmark Table**.
> - **0:20–0:30**: Highlight the graphic contrasting **Naive Linear Extrapolation ($\text{ETA} = \text{STA} + \text{Current Delay}$)** vs **Real Railway Physics**.

**🎙️ NARRATION (Speaker 1 — Confident, crisp pace):**
> "Every single day, over 23 million passengers and thousands of station controllers across Indian Railways ask one critical question: *When will this coaching train actually arrive?*
>
> Today, existing passenger apps and station boards rely on a flawed static formula: **Scheduled Arrival plus Current Delay, minus fixed recovery time**.
>
> If the *Howrah Rajdhani* is 35 minutes late at Etawah, legacy systems blindly assume it stays 35 minutes late—or worse, expect it to exceed the section's Maximum Permissible Speed. They ignore real-world ground realities: **Dense North Indian fog restrictions, precedent overtaking by Vande Bharat trains, festival crowd dwell surges, and outer-home signal starvation** when all junction platforms are occupied.
>
> To solve **Smart India Hackathon Problem Statement 26028** for the **Ministry of Railways**, we present **DARPAN (SIH-DETA)**—India's first **3-Layer Hybrid Machine Learning and Discrete-Event Railway Physics Engine** for real-time dynamic ETA forecasting."

---

### SCENE 2: The 1.68 GB Indian Railways Data Lake (`0:30 – 0:55`)

> **[VISUAL / SCREEN CUE]**
> - Switch to the **`About` / `6-DB Data Lake & Audit`** view ([`AboutPage.tsx`](../frontend/src/pages/AboutPage.tsx)).
> - Zoom in on the **6 Production SQLite Databases Grid (`1.68 GB` total)** and the **Audit Remediation Matrix**.
> - On-screen callouts:
>   - **`13,114` Network Nodes / `8,990` Geocoded Stations** (`stations.db` & `darpan.sqlite`)
>   - **`15,802` Coaching Runs / `417,080` Schedule Stops / `19,875` Track Segments**
>   - **`1.51 Million` Historical Delay Records & `73,342` Empirical Slack Profiles** (`historical.db`)
>   - **`3.19 Million` Weather Grid Observations across `180` Hex Cells** (`weather.db`)
>   - **`704` Approach Cabins (`telemetry.db`) & `39,754` Mined Network Anomalies (`anomalies.db`)**

**🎙️ NARRATION (Speaker 1):**
> "Instead of training on synthetic toy data, DARPAN is built on a **1.68 Gigabyte, 6-database Indian Railways production data lake**.
>
> We cataloged **8,990 geocoded stations and 704 intermediate approach cabins**, **417,080 schedule stops**, **1.51 million historical station delay records**, **73,342 empirical sectional slack profiles**, and **3.19 million weather observations**.
>
> Crucially, when stations like *Allahabad* and *Mughalsarai* were officially renamed to *Prayagraj (`PRYJ`)* and *Pt. DD Upadhyaya (`DDU`)*, legacy datasets broke foreign-key links across India's busiest trunk corridors. Our **Canonical Station Alias Engine** automatically bridges legacy and modern CRIS codes—recovering **72,508 lost sectional delay records** across **1,148 block sections**."

---

### SCENE 3: The Core Innovation — 3-Layer Hybrid ML + Discrete DSA Engine (`0:55 – 1:40`)

> **[VISUAL / SCREEN CUE]**
> - Click **`Live`** in the top navigation bar ([`LivePage.tsx`](../frontend/src/pages/LivePage.tsx)) and select **`12301` Howrah – New Delhi Rajdhani Express**.
> - **0:55–1:15**: Highlight the **SIH-DETA Hybrid ML + Discrete DSA Engine** header showing **`Tier 1: Rajdhani Express`** and **`8 Nodes LOCKED`**. Point to the **5 Quantile Cards**:
>   - **$P_{10}$ Optimistic (`11:32`)** | **$P_{50}$ Median ETA (`11:41`)** | **$P_{90}$ Worst-Case (`11:58`)** | Crossed-out **Naive Static App (`11:55`)** | **Slack Absorbed (`-14m`)**.
> - **1:15–1:28**: Toggle from **Mode 1: O(1) Section DAG** to **Mode 2: Halt-by-Halt Micro-Nodes**, showing intermediate wayside halts (*Rooma*, *Bindki Road River-Basin Fog Halt*, *Outer Home Signal Cabin*).
> - **1:28–1:40**: Adjust the **G&SR Visibility slider** to `Dense Fog (380m)` and **Festival Surge Preset** to `Maha Kumbh Mela (S = 3.2x)`—watch the $P_{10}/P_{50}/P_{90}$ arrival cones dynamically recalculate in real time!

**🎙️ NARRATION (Speaker 2 — Technical & authoritative):**
> "Why do pure Machine Learning models fail in railway operations? Because a black-box neural network has no understanding of railway interlocking—it will happily predict two trains arriving on Platform 1 at the exact same minute.
>
> DARPAN solves this through a **2-Pass Decoupled Hybrid Architecture**: **Machine Learning predicts transit drift; Discrete Algorithms enforce railway physics.**
>
> - **In Layer 1 (Spatio-Temporal & G&SR Fusion)**, we extract a **31-feature operational vector** combining upstream delay velocity, empirical slack absorption, **Indian Railways G&SR Rule 3.61 fog speed caps** (75 km/h with Fog-Pass GPS devices, 30 km/h under 100m visibility), CWR rail-heat buckling limits, and **NSG 1-to-6 station crowd surge dwell inflation**.
> - **In Layer 2 (Probabilistic Quantile ML)**, our **Gradient Boosted Quantile Regressors** trained with Pinball Loss output calibrated **$P_{10}$ Optimistic, $P_{50}$ Expected, and $P_{90}$ Worst-Case arrival bounds**, paired with a live Delay-Jump Risk Classifier achieving an **ROC-AUC of 0.85 to 0.92**.
> - **In Layer 3 (Unidirectional Space-Time DAG)**, a **2-Pass Discrete Event Resolver** locks downstream departure times monotonically, switching automatically between **$O(1)$ Aggregate Section traversal** and **Mode-2 Micro-Node Halt Inspection** down to individual river-basin fog zones and approach cabins."

---

### SCENE 4: Station Operations, Outer-Signal Starvation & Platform IntervalTree (`1:40 – 2:10`)

> **[VISUAL / SCREEN CUE]**
> - Click **`Station`** in the top navbar ([`StationPage.tsx`](../frontend/src/pages/StationPage.tsx)) and select **`CNB (Kanpur Central)`** or **`PRYJ (Prayagraj Jn)`**.
> - Highlight the **NSG-1 Crowd Surge Dwell Dilation Card** (`Scheduled Halt: 5m` $\to$ `Dilated Surge Halt: 19m (+14m)` with the live mathematical trace) and **M/M/c Platform Load $\rho$**.
> - Scroll down to the **IntervalTree Mutual-Exclusion Platform Schedule**, highlighting green **`PF LOCKED`** badges alongside amber **`OUTER HOLD +12m at Juhi Outer Cabin`** alerts.
> - Briefly click the **`Live Provider Board`** tab to show the airport-style station PIDS display.

**🎙️ NARRATION (Speaker 2):**
> "The problem statement highlights how inaccurate ETAs disrupt platform allocation, crew scheduling, and feeder transport.
>
> Every Indian rail passenger has experienced their train arriving on time within two kilometers of a major junction—only to be held at the **Outer Home Signal for 30 minutes** because all platforms are occupied.
>
> In our **Station Radar**, an **IntervalTree Mutual-Exclusion Scheduler** enforces a mandatory 5-minute safety headway across every physical platform. When festival surges like *Maha Kumbh* or *Chhath Puja* dilate dwell times at **NSG-1 junctions**, our engine detects platform contention in advance, holds lower-priority trains at our **704 cataloged Approach Cabins**, and broadcasts the exact outer-signal wait time to both Station Masters and passengers."

---

### SCENE 5: Control Room Dispatch Cockpit, Black Swan Breaker & GIS Ecosystem (`2:10 – 2:45`)

> **[VISUAL / SCREEN CUE]**
> - **2:10–2:30**: Click **`Control`** in the top navbar ([`RadarPage.tsx`](../frontend/src/pages/RadarPage.tsx)).
>   - Select block section **`Kanpur Central (CNB) ➔ Prayagraj Jn (PRYJ)`**.
>   - Click the **`TRACK_BLOCK` (Rail Fracture / Mega Block, +95m)** or **`OHE_SNAP`** override button.
>   - Show the **Circuit Breaker Banner** switching to **`LEVEL_3_BLACK_SWAN`**, the **FIFO Block Headway Queue** cascading delays across trailing trains, and the **Yen's K-Shortest Electrified Bypass** panel computing the exact **25kV AC detour** (`CNB ➔ LKO ➔ PRYJ`)!
> - **2:30–2:40**: Cut quickly to **`Map`** ([`MapPage.tsx`](../frontend/src/pages/MapPage.tsx)) showing the **8,990-station National GIS Map** with live locomotive sonar and LHB/ICF coach rake composition, and **`PNR`** ([`PnrPage.tsx`](../frontend/src/pages/PnrPage.tsx)) showing **SHA-256 privacy-hardened PNR tracking**.
> - **2:40–2:45**: Close on the **REST API Gateway & Pacing Telemetry Strip** (`1,042 Active Running Window Trains Polled`, `-79.9% Network Load`, `3.8 RPS`, FastAPI `/v1/deta/*` endpoints).

**🎙️ NARRATION (Speaker 1):**
> "For Divisional Control Rooms, DARPAN provides a real-time **Section Controller Dispatch Cockpit**.
>
> When a severe disruption occurs—such as a **Cattle Run-Over, Alarm Chain Pulling, OHE Catenary Snap, or Rail Fracture**—controllers inject the incident in one click.
>
> If a mainline track is severed, pure ML models hallucinate impossible ETAs. DARPAN automatically trips a **Level-3 Black Swan Circuit Breaker**, propagates FIFO headway delays across trailing coaching rakes according to **COA 6-Tier priority**, and executes **Yen's K-Shortest Path algorithm** over 8,990 stations to recommend a verified **25kV AC electrified bypass chord** in milliseconds.
>
> Powered by an **Adaptive Schedule-Aware Token-Bucket Pacing Engine** that cuts upstream polling load by **79.9%** and weather API calls by **98%**, DARPAN exposes sub-50-millisecond REST APIs ready to plug directly into **NTES, CRIS Control Offices, Station PIDS Displays, and third-party mobility apps**.
>
> **DARPAN**: Where Machine Learning meets Indian Railways Physics. Thank you!"

---

## Quick Production Checklist for Recording

1. **Keep the App Running Locally (`http://localhost:5173`)**:
   - Start your screen recording at `1920x1080` (60 fps) in Chrome/Edge with browser zoom at `100%`.
2. **Pre-Open Tabs for Zero-Lag Transitions**:
   - **Tab 1**: `Home` (`HomePage.tsx`) — positioned at the Hero & 3D Fleet Radar.
   - **Tab 2**: `About` (`AboutPage.tsx`) — opened to the **6-DB Data Lake & Audit** tab.
   - **Tab 3**: `Live` (`LivePage.tsx`) — pre-loaded with **`12301` Howrah Rajdhani** so the $P_{10}/P_{50}/P_{90}$ cards and Mode 1 / Mode 2 toggle are immediately visible.
   - **Tab 4**: `Station` (`StationPage.tsx`) — pre-loaded with **`CNB` (Kanpur Central)**.
   - **Tab 5**: `Control` (`RadarPage.tsx`) — ready to click **`TRACK_BLOCK`** or **`CRO`** on screen so judges see the live state transition to `LEVEL_3_BLACK_SWAN` and Yen's 25kV AC bypass route.
   - **Tab 6**: `Map` (`MapPage.tsx`) — showing the full-screen route trajectory and coach rake strip.
