"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";

import { ja } from "@/lib/i18n";
import { EVENT_COLORS } from "@/lib/style";
import type { EventType, MonitorData, MonitorEvent } from "@/lib/types";
import EventFeed from "./EventFeed";
import FacilityList from "./FacilityList";
import FacilityPanel from "./FacilityPanel";
import Timeline from "./Timeline";
import DateSlider from "./DateSlider";

// MapLibre touches `window`, so the map must be client-only.
const MapView = dynamic(() => import("./MapView"), {
  ssr: false,
  loading: () => <div className="map-pane__canvas" />,
});

function uniqueSortedDates(events: MonitorEvent[]): string[] {
  return Array.from(new Set(events.map((e) => e.date))).sort();
}

export default function Dashboard({ data }: { data: MonitorData }) {
  const { aois, events, origin } = data;

  const dates = useMemo(() => uniqueSortedDates(events), [events]);
  // Window start = the date from which events are shown. Defaults to earliest.
  const [windowStart, setWindowStart] = useState<string>(dates[0] ?? "");
  const [selectedAoiId, setSelectedAoiId] = useState<string | null>(null);

  const dateFilteredEvents = useMemo(
    () => (windowStart ? events.filter((e) => e.date >= windowStart) : events),
    [events, windowStart],
  );

  const selectedAoi = useMemo(
    () => aois.features.find((f) => f.properties.id === selectedAoiId) ?? null,
    [aois, selectedAoiId],
  );

  // Sidebar feed/timeline narrow to the selected facility when one is chosen.
  const focusedEvents = useMemo(
    () =>
      selectedAoiId
        ? dateFilteredEvents.filter((e) => e.aoi_id === selectedAoiId)
        : dateFilteredEvents,
    [dateFilteredEvents, selectedAoiId],
  );

  const presentTypes = useMemo(() => {
    const set = new Set<EventType>();
    events.forEach((e) => set.add(e.type));
    return Array.from(set);
  }, [events]);

  return (
    <div className="app__main">
      <div className="map-pane">
        <MapView
          aois={aois}
          events={dateFilteredEvents}
          selectedAoiId={selectedAoiId}
          onSelectAoi={setSelectedAoiId}
        />
      </div>

      <aside className="sidebar">
        {origin === "sample" && (
          <div className="banner banner--warn">{ja.sampleDataBanner}</div>
        )}
        {origin === "empty" && (
          <div className="banner banner--warn">{ja.emptyDataBanner}</div>
        )}
        <div className="banner banner--info">{ja.unverifiedNotice}</div>

        {dates.length > 0 && (
          <DateSlider
            dates={dates}
            value={windowStart}
            onChange={setWindowStart}
            shownCount={dateFilteredEvents.length}
          />
        )}

        <Legend types={presentTypes} />

        <FacilityList
          aois={aois}
          events={dateFilteredEvents}
          selectedAoiId={selectedAoiId}
          onSelect={setSelectedAoiId}
        />

        {selectedAoi && (
          <FacilityPanel
            aoi={selectedAoi}
            events={focusedEvents}
            onClear={() => setSelectedAoiId(null)}
          />
        )}

        <EventFeed
          events={focusedEvents}
          aois={aois}
          onSelectAoi={setSelectedAoiId}
        />

        <Timeline events={focusedEvents} />
      </aside>
    </div>
  );
}

function Legend({ types }: { types: EventType[] }) {
  return (
    <div className="card">
      <div className="card__heading">{ja.legendHeading}</div>
      <div className="legend">
        {types.map((t) => (
          <span className="legend__item" key={t}>
            <span
              className="dot"
              style={{ background: EVENT_COLORS[t] }}
              aria-hidden
            />
            {ja.eventTypeLabel(t)}
          </span>
        ))}
        <span className="legend__item">
          <span className="badge">{ja.unverifiedBadge}</span>
        </span>
      </div>
    </div>
  );
}
