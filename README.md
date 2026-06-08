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
| 2 | Sentinel-1 SAR backscatter change detection (construction / clearance) | ⛔ stub (`pipeline/sources/sar.py`) |
| 3 | Sentinel-2 optical confirmation + baseline-vs-recent compare + verification UX | ⛔ stub (`pipeline/sources/optical.py`) |
| 4 | AIS naval-activity layer + manual commercial-image link field | ⛔ stub (`pipeline/sources/ais.py`) |

---

## Architecture

```
data/
  aois.geojson          # single editable config of monitored sites (add new sites here)
  events.sample.json    # bundled sample events so the UI is demonstrable out of the box
  events.json           # live event store, written by the pipeline (git-ignored)

pipeline/               # Python ingestion + detection
  config.py             # loads AOIs + env-based settings (no secrets committed)
  models.py             # Event record shape (contract with the frontend)
  store.py              # JSON event store, upsert-by-id (PostGIS/SQLite swappable later)
  run.py                # orchestrator: iterate AOIs, run sources, write the store
  sources/
    base.py             # Source interface: fetch(aoi, since) + detect(aoi, window)
    firms.py            # NASA FIRMS thermal anomalies (fully implemented)
    sar.py              # Sentinel-1 SAR     (Phase 2 stub)
    optical.py          # Sentinel-2 optical (Phase 3 stub)
    ais.py              # AIS naval activity (Phase 4 stub)
  tests/                # pytest unit tests (no network)

web/                    # Next.js (App Router) + React + TypeScript + MapLibre GL + D3
  src/app/              # layout (lang="ja") + page (server-loads data)
  src/components/       # MapView, FacilityList, EventFeed, FacilityPanel, Timeline, DateSlider
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
no code changes are needed. Seed sites (coordinates approximate, verify/refine):

- **Etorofu (Iturup / 択捉島):** Burevestnik/Yasny airbase; Kasatka (Hitokappu) Bay coastal defense
- **Kunashiri (Kunashir / 国後島):** Yuzhno-Kurilsk garrison & Mendeleyevo airport
- **Shikotan (色丹島):** Malokurilskoye coastal defense
- **Matua (松輪島, central chain):** reconstructed airfield & base

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

The web app reads `data/aois.geojson` and `data/events.json` at request time.
**If `data/events.json` is missing or empty, it falls back to the bundled
`data/events.sample.json`** (clearly labeled 【サンプルデータ／SAMPLE】) so the
UI is demonstrable before you run the pipeline. The UI shows a banner stating
which data origin is in use.

The default basemap uses OpenStreetMap raster tiles (no API key) for
development. For production deployment, switch to a dedicated tile provider per
the OSMF tile usage policy (`web/src/lib/style.ts`).

---

## Data sources (all free)

| Source | Sensor | Role | Phase |
| ------ | ------ | ---- | ----- |
| **NASA FIRMS** (VIIRS + MODIS) | Thermal anomalies / active fire | Near-real-time thermal events inside each AOI | 1 ✅ |
| **Sentinel-1** (C-band SAR) | Radar (all-weather, day/night) | Primary: backscatter change → construction/clearance candidates | 2 |
| **Sentinel-2** (optical, 10 m) | Optical | Clear-day visual confirmation of SAR-flagged change | 3 |
| **AIS** (satellite-relayed) | Vessel positions | Naval activity in adjacent bays | 4 (stretch) |

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
   inspects the raw data, and corroborates with SAR/optical context.
4. (Phase 3+) Optionally attach a commercial high-resolution image link as
   confirmation.

This is a prioritization aid for analysts, not an automated verdict.
