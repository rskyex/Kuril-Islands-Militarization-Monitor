# Kuril Islands Militarization Monitor

A public, continuously updating web tool that monitors military activity on the
southern Kuril chain — including the islands Japan claims as the **Northern
Territories** (北方領土) — using **only free satellite and sensor data**. It
tracks known military facilities, detects physical changes over time, surfaces
thermal and activity signals, and presents them on a map with per-facility
timelines.

The primary audience is Japanese-language policy researchers, journalists, and
analysts, so **all user-facing copy is in Japanese**. Code, comments, and docs
are in English.

> **This is an open-source intelligence (OSINT) tool.** It surfaces *candidate*
> signals derived from public data. It must never present an automated
> detection as confirmed military activity. Every flagged change is labeled
> **未確認 (unverified)** and links back to the raw imagery or data so a human
> can check it.

---

## Design principles (read first)

1. **Free data first.** The continuous monitoring layer runs entirely on free
   sources (NASA FIRMS, Sentinel-1/2 via Copernicus / Google Earth Engine).
   Commercial imagery (Maxar, Planet) is out of scope for v1 and appears only
   as an optional manual link field for human confirmation.
2. **Everything is a candidate.** Detections are never presented as confirmed.
   Each event carries `status: "unverified"` and a `source_url` back to the raw
   data so a human can verify it.
3. **Provenance on every event.** Source and retrieval time are recorded so
   results are reproducible and auditable.
4. **Idempotent, re-runnable pipeline.** Re-running over the same window
   replaces matching events (upsert by id) rather than duplicating them.
5. **No secrets in the repo.** All API keys come from environment variables.

---

## Project status

Built in phases. **Phase 1 is complete** (scaffold + FIRMS end to end).

| Phase | Scope | Status |
| ----- | ----- | ------ |
| 1 | Scaffold + NASA FIRMS thermal anomalies end to end (pipeline → store → Japanese map UI) | ✅ done |
| 2 | Sentinel-1 SAR backscatter change detection (construction / clearance) via Earth Engine | ✅ done (runnable locally with EE credentials; map renders change polygons) |
| 3 | Sentinel-2 optical confirmation + baseline-vs-recent swipe compare + verification UX | ✅ done (runnable locally with EE credentials; swipe compare + 確認手順 in the detail panel) |
| 4 | AIS naval-activity layer + manual commercial-image link field | ✅ done (runnable locally with an AISStream key; in-app confirmation links) |

---

## Architecture

```
data/
  aois.geojson          # single editable config of monitored sites (add new sites here)
  events.sample.json    # bundled sample events so the UI is demonstrable out of the box
  events.json           # live event store, written by the pipeline (git-ignored)
  imagery.sample.json   # bundled sample optical index (served from web/public/imagery-sample)
  imagery.json          # live optical imagery index, written by the pipeline (git-ignored)
  imagery/              # live Sentinel-2 thumbnails, written by the pipeline (git-ignored)

pipeline/               # Python ingestion + detection
  config.py             # loads AOIs + env-based settings (no secrets committed)
  models.py             # Event record shape (contract with the frontend)
  store.py              # JSON event store, upsert-by-id (PostGIS/SQLite swappable later)
  run.py                # orchestrator: iterate AOIs, run sources, write the store
  sources/
    base.py             # Source interface: fetch(aoi, since) + detect(aoi, window)
    firms.py            # NASA FIRMS thermal anomalies (implemented)
    sar.py              # Sentinel-1 SAR backscatter change detection (implemented; EE backend)
    optical.py          # Sentinel-2 clear-day imagery context (implemented; EE backend)
    ais.py              # AIS naval activity (implemented; AISStream.io backend)
  imagery_store.py      # writes Sentinel-2 thumbnails + data/imagery.json (upsert by AOI)
  tests/                # pytest unit tests (no network)

web/                    # Next.js (App Router) + React + TypeScript + MapLibre GL + D3
  src/app/              # layout (lang="ja") + page (server-loads data)
  src/components/       # MapView, FacilityList, EventFeed, FacilityPanel, Timeline, DateSlider, ImageCompare
  src/app/api/imagery/  # route that serves live Sentinel-2 thumbnails from data/imagery
  src/lib/              # types (event contract), i18n (Japanese strings), data loader, style
```

### Event record shape

The Python `Event` (`pipeline/models.py`) and the TypeScript `MonitorEvent`
(`web/src/lib/types.ts`) are kept in sync:

```jsonc
{
  "id": "firms-matua-airfield-2026-06-02",
  "aoi_id": "matua-airfield",
  "date": "2026-06-02",
  "type": "thermal",            // construction | thermal | clearance | naval | other
  "signal_strength": 0.58,       // 0..1 prioritization hint, NOT a probability of military activity
  "status": "unverified",
  "source_url": "https://firms.modaps.eosdis.nasa.gov/map/#d:2026-06-02;@153.24,48.08,10z",
  "geometry": { "type": "Point", "coordinates": [153.24, 48.08] },
  "notes": "…（日本語）…",
  "provenance": { "source": "firms", "dataset": "VIIRS_SNPP_NRT", "retrieved_at": "…Z", "query": "…" },
  "raw": { "detection_count": 2, "max_frp_mw": 31.4, "detections": [ … ] }
}
```

### Areas of interest

All monitored sites live in **`data/aois.geojson`** — a single editable config.
Add a new facility by appending a GeoJSON `Feature` with the right properties;
no code changes are needed. Centers were verified against open sources
(airfield centers are precise to the runway; mobile coastal-defense systems use
broad-area boxes). Seed sites:

- **Etorofu (Iturup / 択捉島):** Burevestnik airbase (44.920/147.622); Yasny airbase / Iturup Airport (45.256/147.955); Kasatka (Hitokappu) Bay coastal-defense area (44.965/147.672)
- **Kunashiri (Kunashir / 国後島):** Yuzhno-Kurilsk garrison & Mendeleyevo airport (43.961/145.684)
- **Shikotan (色丹島):** Malokurilskoye coastal-defense area (43.871/146.828)
- **Matua (松輪島, central chain):** reconstructed airfield & base (48.051/153.255)

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 20+

### 1. Pipeline (Python)

```bash
python3 -m pip install -r pipeline/requirements.txt

# Get a free FIRMS map key: https://firms.modaps.eosdis.nasa.gov/api/map_key/
cp .env.example .env        # then edit and set FIRMS_MAP_KEY
export FIRMS_MAP_KEY=...     # or use your shell's env mechanism

# Run the pipeline (FIRMS, last 7 days, all AOIs) -> writes data/events.json
python3 -m pipeline.run

# Useful flags:
python3 -m pipeline.run --days 3                 # shorter lookback
python3 -m pipeline.run --aoi matua-airfield     # one site (repeatable)
python3 -m pipeline.run --dry-run                # fetch + detect, do not write

# Tests (no network needed):
python3 -m pytest pipeline/tests -q
```

The pipeline is idempotent: re-running replaces matching events rather than
duplicating them. Without `FIRMS_MAP_KEY` set, the FIRMS source degrades
gracefully (logs a warning, writes no events) instead of crashing.

### 1b. Sentinel-1 SAR change detection (Phase 2, optional)

The SAR source compares a recent Sentinel-1 backscatter composite against an
earlier baseline over each AOI and flags significant change as unverified
`construction` (backscatter increase) / `clearance` (decrease) candidates, each
linked to the underlying scene in the Copernicus EO Browser. It runs on Google
Earth Engine, which needs Google credentials (not available in CI), so it is
**opt-in** via `--source sentinel-1`.

```bash
pip install -r pipeline/requirements.txt -r pipeline/requirements-sar.txt
earthengine authenticate          # one-time, opens a browser
export EE_PROJECT=your-gcp-project-id

# 240-day lookback so the baseline window has Sentinel-1 coverage:
python3 -m pipeline.run --source sentinel-1 --days 240
# Run both sources together:
python3 -m pipeline.run --source firms --source sentinel-1 --days 240
```

Service-account auth is also supported: set `GOOGLE_APPLICATION_CREDENTIALS`
(JSON key path) and `EE_SERVICE_ACCOUNT` (its email). All Earth Engine access
is isolated behind a `SarBackend` interface (`pipeline/sources/sar.py`), so the
detection logic is unit-tested with a fake backend and the module imports fine
without `earthengine-api` installed. Detection parameters (polarization, orbit
pass, change threshold, smoothing, min area) live in `SarParams`.

### 1c. Sentinel-2 clear-day imagery (Phase 3, optional)

The optical source provides *visual confirmation context* — not detections. For
each AOI it picks the least-cloudy Sentinel-2 scene in a baseline window and a
recent window, renders true-color thumbnails, and writes them to
`data/imagery/<aoi>/{baseline,recent}.png` indexed in `data/imagery.json`. The
detail panel shows them as a **baseline-vs-recent swipe compare** beside the SAR
signal, with a verification checklist (確認手順). Also Earth Engine, so opt-in:

```bash
pip install -r pipeline/requirements.txt -r pipeline/requirements-ee.txt
earthengine authenticate && export EE_PROJECT=your-gcp-project-id

python3 -m pipeline.run --imagery --days 540        # imagery only (wide window for clear days)
python3 -m pipeline.run --source sentinel-1 --imagery --days 540   # SAR events + imagery
```

Selection / thumbnail parameters (max cloud %, thumbnail size, true-color
stretch) live in `OpticalParams`; the Earth Engine calls sit behind the
`OpticalBackend` interface and are unit-tested with a fake backend.

### 1d. AIS naval activity (Phase 4 stretch, optional)

The AIS source listens to a free real-time feed (AISStream.io) over each AOI's
bounding box for a short window and emits one unverified `naval` candidate event
per vessel (MMSI), scored by persistence + low speed (loitering). The
verification link points to a public vessel-tracking page by MMSI.

```bash
pip install -r pipeline/requirements.txt -r pipeline/requirements-ais.txt
export AISSTREAM_API_KEY=...        # free key from https://aisstream.io/
python3 -m pipeline.run --source ais
```

The WebSocket I/O sits behind the `AisBackend` interface (lazy `websockets`
import), so the module imports and is unit-tested without the dependency.

### Commercial-image confirmation links (Phase 4, manual)

Per the free-data positioning, commercial imagery (Maxar / Planet) only ever
appears as an **optional manual link** a human attaches to confirm a candidate.
In the detail panel each event has a "+ 商用画像による確認リンク" control;
saving it `POST`s to `/api/confirmations`, which persists to the committed,
human-curated `data/confirmations.json` (keyed by event id). This does **not**
change the event's automated `status`, which stays `unverified`.

### 2. Web app (Next.js)

```bash
cd web
npm install
npm run dev        # http://localhost:3000

# Production:
npm run build && npm run start

# Quality gates:
npm run typecheck  # TypeScript strict mode
npm run lint
```

Data loading has two layers (`web/src/lib/data.ts`):

1. **Live pipeline output** — read from the repo-root `data/` dir at request
   time (`events.json`, `imagery.json`, and an edited `aois.geojson` /
   `confirmations.json`), so a fresh pipeline run shows up without a rebuild.
   Override the location with `KURIL_DATA_DIR`.
2. **Bundled seed/sample data** — `data/{aois.geojson, events.sample.json,
   imagery.sample.json, confirmations.json}` are **imported** (compiled into the
   server bundle) and used as the fallback when the live files are absent. This
   is what makes the app render out of the box, and is what a serverless host
   (Vercel) serves, since the repo-root `data/` dir is not part of that
   deployment. The UI shows a banner stating which data origin is in use.

Selecting a facility opens the detail panel with the optical baseline-vs-recent
swipe compare and the verification checklist.

The default basemap uses OpenStreetMap raster tiles (no API key) for
development. For production deployment, switch to a dedicated tile provider per
the OSMF tile usage policy (`web/src/lib/style.ts`).

### Deploying to Vercel

This is a **monorepo**: the Next.js app is in `web/`, with the Python pipeline
and data at the repo root. When importing the project into Vercel:

- **Set the Root Directory to `web`** (Project → Settings → Build & Deployment →
  Root Directory). This is required so Vercel finds the Next.js app; without it
  the build fails with “No Next.js version detected”.
- No environment variables are required — the app ships with bundled sample data
  and renders immediately.
- The deployed site is **read-only**: it shows the bundled sample (or whatever
  was committed). The live pipeline (FIRMS / SAR / optical / AIS) and the
  “save commercial-image link” action need a writable filesystem, so they run on
  a self-hosted Node server (`next start`) or a host with persistent storage —
  on a read-only serverless function the save action fails gracefully with a
  notice. To publish real monitoring data to a Vercel deploy, run the pipeline
  elsewhere and commit/publish the resulting `data/*.json`, or point
  `KURIL_DATA_DIR` at a mounted volume.

---

## Data sources (all free)

| Source | Sensor | Role | Phase |
| ------ | ------ | ---- | ----- |
| **NASA FIRMS** (VIIRS + MODIS) | Thermal anomalies / active fire | Near-real-time thermal events inside each AOI | 1 ✅ |
| **Sentinel-1** (C-band SAR) | Radar (all-weather, day/night) | Primary: backscatter change → construction/clearance candidates | 2 ✅ |
| **Sentinel-2** (optical, 10 m) | Optical | Clear-day visual confirmation of SAR-flagged change (baseline-vs-recent compare) | 3 ✅ |
| **AIS** (satellite-relayed) | Vessel positions | Naval activity in adjacent bays (one event per vessel/listening window) | 4 ✅ |

SAR is the primary sensor because it sees through cloud and polar night, which
matters at these high, frequently-overcast latitudes.

> Always verify the current API surface before relying on a source — product
> names and quotas change.

---

## Verification workflow

Because nothing here is confirmed, the intended human-in-the-loop flow is:

1. The pipeline flags a **candidate** event and stores it as `unverified`.
2. The UI surfaces it with an **未確認** badge and a **元データを確認** (view
   source) link.
3. A human opens the source (e.g. the FIRMS fire map for that AOI and date),
   inspects the raw data, and corroborates a SAR change signal against the
   Sentinel-2 baseline-vs-recent swipe compare in the detail panel.
4. (Phase 4) Optionally attach a commercial high-resolution image link as
   confirmation.

The detail panel renders this as an in-app checklist (確認手順). It is a
prioritization aid for analysts, not an automated verdict.
