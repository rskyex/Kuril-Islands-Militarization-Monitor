// Shared types for the Kuril monitor frontend.
//
// The MonitorEvent shape is the contract with the Python pipeline
// (see pipeline/models.py). Keep the two in sync.

export type EventType =
  | "construction"
  | "thermal"
  | "clearance"
  | "naval"
  | "other";

// Events are always candidates surfaced from public data — never presented as
// confirmed activity, hence the single allowed status.
export type EventStatus = "unverified";

export type GeoJsonGeometry = {
  type: string;
  coordinates: unknown;
};

export interface Provenance {
  source: string;
  dataset: string;
  retrieved_at: string;
  query?: string | null;
}

// A human-added link to a commercial high-resolution image used to confirm a
// candidate. Per the free-data positioning, commercial imagery only ever
// appears as this optional manual link — it does NOT change the automated
// `status`, which stays "unverified".
export interface EventConfirmation {
  url: string;
  note?: string;
  added_at: string;
}

export interface MonitorEvent {
  id: string;
  aoi_id: string;
  date: string;
  type: EventType;
  signal_strength: number;
  status: EventStatus;
  source_url: string;
  geometry: GeoJsonGeometry;
  notes: string;
  provenance?: Provenance | null;
  raw?: Record<string, unknown>;
  // Merged in by the loader from data/confirmations.json (not pipeline output).
  confirmation?: EventConfirmation | null;
}

export interface AoiProperties {
  id: string;
  name: string;
  name_ja: string;
  island: string;
  island_ja?: string;
  facility_type: string;
  center: [number, number];
  notes?: string;
}

export interface AoiFeature {
  type: "Feature";
  properties: AoiProperties;
  geometry: {
    type: "Polygon" | "MultiPolygon";
    coordinates: number[][][] | number[][][][];
  };
}

export interface AoiFeatureCollection {
  type: "FeatureCollection";
  metadata?: Record<string, unknown>;
  features: AoiFeature[];
}

// Whether the events being shown came from the live store or the bundled
// sample, so the UI can be transparent about it.
export type DataOrigin = "live" | "sample" | "empty";

// --- Sentinel-2 optical imagery (Phase 3) ---

export interface AoiImageRef {
  date: string;
  cloud_pct: number | null;
  image_url: string;
  scene_id?: string | null;
  source_url: string;
}

export interface AoiImagery {
  aoi_id: string;
  baseline: AoiImageRef | null;
  recent: AoiImageRef | null;
  provenance?: Provenance | null;
}

export interface MonitorData {
  aois: AoiFeatureCollection;
  events: MonitorEvent[];
  origin: DataOrigin;
  // Per-AOI optical imagery context, keyed by aoi_id (may be empty).
  imagery: Record<string, AoiImagery>;
  imageryOrigin: DataOrigin;
}
