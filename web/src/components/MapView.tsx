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

// Build a GeoJSON FeatureCollection of event points for the map source.
function eventsToGeoJson(events: MonitorEvent[]) {
  return {
    type: "FeatureCollection" as const,
    features: events
      .filter((e) => e.geometry?.type === "Point")
      .map((e) => ({
        type: "Feature" as const,
        geometry: e.geometry,
        properties: {
          id: e.id,
          aoi_id: e.aoi_id,
          type: e.type,
          color: EVENT_COLORS[e.type as EventType] ?? EVENT_COLORS.other,
          radius: 5 + Math.round(e.signal_strength * 9),
          date: e.date,
          notes: e.notes,
        },
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
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");

    map.on("load", () => {
      map.addSource("aois", { type: "geojson", data: aois as never });
      map.addSource("facilities", {
        type: "geojson",
        data: facilitiesToGeoJson(aois) as never,
      });
      map.addSource("events", {
        type: "geojson",
        data: eventsToGeoJson(events) as never,
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
      map.on("click", "facility-points", selectFromFeature);
      map.on("click", "facility-labels", selectFromFeature);
      map.on("click", "event-points", (e) => {
        const aoiId = e.features?.[0]?.properties?.aoi_id;
        if (typeof aoiId === "string") onSelectRef.current(aoiId);
      });

      // Clicking empty map clears the selection.
      map.on("click", (e) => {
        const hits = map.queryRenderedFeatures(e.point, {
          layers: ["facility-points", "facility-labels", "event-points"],
        });
        if (hits.length === 0) onSelectRef.current(null);
      });

      for (const layer of ["facility-points", "facility-labels", "event-points"]) {
        map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
      }
    });

    return () => {
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
      const src = map.getSource("events") as maplibregl.GeoJSONSource | undefined;
      src?.setData(eventsToGeoJson(events) as never);
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
