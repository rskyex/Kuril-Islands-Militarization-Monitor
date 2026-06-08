// Shared visual constants: event-type colors and a no-API-key MapLibre style.

import type { EventType } from "./types";

export const EVENT_COLORS: Record<EventType, string> = {
  thermal: "#ff6b35", // orange-red — heat
  construction: "#ffd23f", // amber
  clearance: "#c084fc", // violet
  naval: "#38bdf8", // sky
  other: "#94a3b8", // slate
};

export const FACILITY_COLOR = "#e2e8f0";
export const AOI_FILL = "rgba(56, 189, 248, 0.08)";
export const AOI_LINE = "#38bdf8";

// A minimal MapLibre raster style that needs no API key. OpenStreetMap raster
// tiles are fine for low-volume development; production should switch to a
// dedicated tile provider per OSMF tile usage policy. The dark-ish basemap
// keeps the high-latitude Kuril chain legible against bright event markers.
export const MAP_STYLE = {
  version: 8 as const,
  sources: {
    osm: {
      type: "raster" as const,
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
      maxzoom: 19,
    },
  },
  layers: [
    {
      id: "osm",
      type: "raster" as const,
      source: "osm",
    },
  ],
};

// Initial camera centered on the southern Kuril chain.
export const INITIAL_VIEW = {
  center: [148.5, 45.5] as [number, number],
  zoom: 5.2,
};
