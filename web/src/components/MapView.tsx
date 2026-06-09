"use client";

import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";

import { ja } from "@/lib/i18n";
import {
  AOI_FILL,
  AOI_LINE,
  EVENT_COLORS,
  FACILITY_COLOR,
  INITIAL_VIEW,
  MAP_STYLE,
} from "@/lib/style";
import type { AoiFeatureCollection, EventType, MonitorEvent } from "@/lib/types";

interface Props {
  aois: AoiFeatureCollection;
  events: MonitorEvent[];
  selectedAoiId: string | null;
  onSelectAoi: (id: string | null) => void;
}

function eventProps(e: MonitorEvent) {
  return {
    id: e.id,
    aoi_id: e.aoi_id,
    type: e.type,
    color: EVENT_COLORS[e.type as EventType] ?? EVENT_COLORS.other,
    radius: 5 + Math.round(e.signal_strength * 9),
    date: e.date,
    notes: e.notes,
  };
}

// Point-geometry events (e.g. FIRMS thermal) -> circle markers.
function eventsToPointGeoJson(events: MonitorEvent[]) {
  return {
    type: "FeatureCollection" as const,
    features: events
      .filter((e) => e.geometry?.type === "Point")
      .map((e) => ({
        type: "Feature" as const,
        geometry: e.geometry,
        properties: eventProps(e),
      })),
  };
}

// Polygon-geometry events (e.g. Sentinel-1 change patches) -> filled regions.
function eventsToPolygonGeoJson(events: MonitorEvent[]) {
  return {
    type: "FeatureCollection" as const,
    features: events
      .filter(
        (e) =>
          e.geometry?.type === "Polygon" || e.geometry?.type === "MultiPolygon",
      )
      .map((e) => ({
        type: "Feature" as const,
        geometry: e.geometry,
        properties: eventProps(e),
      })),
  };
}

// Facility center points, for clickable markers.
function facilitiesToGeoJson(aois: AoiFeatureCollection) {
  return {
    type: "FeatureCollection" as const,
    features: aois.features.map((f) => ({
      type: "Feature" as const,
      geometry: {
        type: "Point" as const,
        coordinates: f.properties.center,
      },
      properties: {
        id: f.properties.id,
        name_ja: f.properties.name_ja,
        facility_type: f.properties.facility_type,
      },
    })),
  };
}

export default function MapView({
  aois,
  events,
  selectedAoiId,
  onSelectAoi,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const onSelectRef = useRef(onSelectAoi);
  onSelectRef.current = onSelectAoi;

  // Initialize the map once.
  useEffect(() => {
    if (mapRef.current || !containerRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: INITIAL_VIEW.center,
      zoom: INITIAL_VIEW.zoom,
      attributionControl: { compact: true },
      // Render Japanese (CJK) label glyphs from local browser fonts instead of
      // downloading them from the glyph server — the facility names are in
      // Japanese, so this is what makes their labels appear.
      localIdeographFontFamily:
        "'Hiragino Kaku Gothic ProN', 'Noto Sans JP', 'Yu Gothic', sans-serif",
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");

    // Surface (rather than swallow) tile/glyph errors, and make sure one bad
    // resource doesn't leave the whole map blank.
    map.on("error", (e) => {
      // eslint-disable-next-line no-console
      console.warn("[map] resource error:", e?.error?.message ?? e);
    });

    map.on("load", () => {
      map.addSource("aois", { type: "geojson", data: aois as never });
      map.addSource("facilities", {
        type: "geojson",
        data: facilitiesToGeoJson(aois) as never,
      });
      map.addSource("events", {
        type: "geojson",
        data: eventsToPointGeoJson(events) as never,
      });
      map.addSource("event-polys", {
        type: "geojson",
        data: eventsToPolygonGeoJson(events) as never,
      });

      // AOI polygons.
      map.addLayer({
        id: "aoi-fill",
        type: "fill",
        source: "aois",
        paint: { "fill-color": AOI_FILL },
      });
      map.addLayer({
        id: "aoi-line",
        type: "line",
        source: "aois",
        paint: {
          "line-color": AOI_LINE,
          "line-width": [
            "case",
            ["==", ["get", "id"], selectedAoiId ?? "__none__"],
            3,
            1.2,
          ],
        },
      });

      // Polygon change-events (e.g. Sentinel-1 backscatter change patches).
      map.addLayer({
        id: "event-poly-fill",
        type: "fill",
        source: "event-polys",
        paint: { "fill-color": ["get", "color"], "fill-opacity": 0.28 },
      });
      map.addLayer({
        id: "event-poly-line",
        type: "line",
        source: "event-polys",
        paint: { "line-color": ["get", "color"], "line-width": 1.5 },
      });

      // Event points (sized by signal strength, colored by type).
      map.addLayer({
        id: "event-points",
        type: "circle",
        source: "events",
        paint: {
          "circle-radius": ["get", "radius"],
          "circle-color": ["get", "color"],
          "circle-opacity": 0.75,
          "circle-stroke-width": 1,
          "circle-stroke-color": "#0b1220",
        },
      });

      // Facility markers.
      map.addLayer({
        id: "facility-points",
        type: "circle",
        source: "facilities",
        paint: {
          "circle-radius": 6,
          "circle-color": FACILITY_COLOR,
          "circle-stroke-width": 2,
          "circle-stroke-color": AOI_LINE,
        },
      });
      map.addLayer({
        id: "facility-labels",
        type: "symbol",
        source: "facilities",
        layout: {
          "text-field": ["get", "name_ja"],
          // Latin fallback font from the glyphs endpoint; the Japanese glyphs
          // come from local fonts (localIdeographFontFamily).
          "text-font": ["Noto Sans Regular"],
          "text-size": 11,
          "text-offset": [0, 1.4],
          "text-anchor": "top",
        },
        paint: {
          "text-color": "#e6edf6",
          "text-halo-color": "#0b1220",
          "text-halo-width": 1.4,
        },
      });

      const selectFromFeature = (e: maplibregl.MapLayerMouseEvent) => {
        const id = e.features?.[0]?.properties?.id;
        if (typeof id === "string") onSelectRef.current(id);
      };
      const selectFromAoiId = (e: maplibregl.MapLayerMouseEvent) => {
        const aoiId = e.features?.[0]?.properties?.aoi_id;
        if (typeof aoiId === "string") onSelectRef.current(aoiId);
      };
      map.on("click", "facility-points", selectFromFeature);
      map.on("click", "facility-labels", selectFromFeature);
      map.on("click", "event-points", selectFromAoiId);
      map.on("click", "event-poly-fill", selectFromAoiId);

      const interactiveLayers = [
        "facility-points",
        "facility-labels",
        "event-points",
        "event-poly-fill",
      ];

      // Clicking empty map clears the selection.
      map.on("click", (e) => {
        const hits = map.queryRenderedFeatures(e.point, {
          layers: interactiveLayers,
        });
        if (hits.length === 0) onSelectRef.current(null);
      });

      for (const layer of interactiveLayers) {
        map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
      }

      // If the container wasn't fully sized when the map initialized (common
      // with dynamic import + fl/grid layout), this paints it correctly.
      map.resize();
    });

    // Keep the GL canvas sized to its container — a 0-sized container at init
    // is a classic cause of a blank map.
    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      map.remove();
      mapRef.current = null;
    };
    // Initialize once; data updates are handled by the effects below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update event points when the date-filtered events change.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      const pts = map.getSource("events") as maplibregl.GeoJSONSource | undefined;
      pts?.setData(eventsToPointGeoJson(events) as never);
      const polys = map.getSource("event-polys") as
        | maplibregl.GeoJSONSource
        | undefined;
      polys?.setData(eventsToPolygonGeoJson(events) as never);
    };
    if (map.isStyleLoaded()) apply();
    else map.once("idle", apply);
  }, [events]);

  // Highlight the selected AOI outline and fly to it.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      if (!map.getLayer("aoi-line")) return;
      map.setPaintProperty("aoi-line", "line-width", [
        "case",
        ["==", ["get", "id"], selectedAoiId ?? "__none__"],
        3,
        1.2,
      ]);
    };
    if (map.isStyleLoaded()) apply();
    else map.once("idle", apply);

    if (selectedAoiId) {
      const f = aois.features.find((x) => x.properties.id === selectedAoiId);
      if (f) map.flyTo({ center: f.properties.center, zoom: 9, speed: 0.8 });
    }
  }, [selectedAoiId, aois]);

  return (
    <div
      ref={containerRef}
      className="map-pane__canvas"
      role="region"
      aria-label={ja.facilitiesHeading}
    />
  );
}
