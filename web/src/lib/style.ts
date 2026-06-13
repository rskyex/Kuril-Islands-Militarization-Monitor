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
  // Glyphs are REQUIRED for the facility-label (symbol) layer to render; a
  // style without this makes MapLibre error and can blank the map. This is a
  // free, no-key public font endpoint. Japanese (CJK) glyphs are rendered from
  // local browser fonts via `localIdeographFontFamily` (see MapView), so this
  // endpoint is only needed for Latin glyphs.
  glyphs: "https://fonts.openmaptiles.org/{fontstack}/{range}.pbf",
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
    // Solid background so the AOI polygons and facility markers stay visible
    // even when the raster tiles are slow or blocked on the deployed host.
    {
      id: "background",
      // Deliberately distinct from the page background (#0b1220) so it's
      // obvious whether MapLibre is painting at all.
      type: "background" as const,
      paint: { "background-color": "#16384f" },
    },
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
