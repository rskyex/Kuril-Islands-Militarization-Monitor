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

export interface MonitorData {
  aois: AoiFeatureCollection;
  events: MonitorEvent[];
  origin: DataOrigin;
}
