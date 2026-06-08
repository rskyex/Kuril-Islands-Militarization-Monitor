"use client";

import { ja } from "@/lib/i18n";
import type { AoiFeature, MonitorEvent } from "@/lib/types";

interface Props {
  aoi: AoiFeature;
  events: MonitorEvent[];
  onClear: () => void;
}

export default function FacilityPanel({ aoi, events, onClear }: Props) {
  const p = aoi.properties;
  // Events for this facility, newest first (parent already date-filters).
  const sorted = [...events].sort((a, b) => (a.date < b.date ? 1 : -1));

  return (
    <div className="card detail">
      <div className="card__heading">
        {ja.detailHeading}
        <button className="btn" onClick={onClear}>
          {ja.resetSelection}
        </button>
      </div>

      <h3 style={{ margin: "2px 0 8px", fontSize: 15 }}>{p.name_ja}</h3>
      <dl>
        <dt>{p.island_ja ? "島" : "Island"}</dt>
        <dd>{p.island_ja ?? p.island}</dd>
        <dt>{ja.eventType}</dt>
        <dd>{ja.facilityType(p.facility_type)}</dd>
      </dl>
      {p.notes && <p className="muted" style={{ marginTop: 8 }}>{p.notes}</p>}

      <div className="card__heading" style={{ marginTop: 12 }}>
        {ja.eventFeedHeading}
        <small>{ja.eventsCount(sorted.length)}</small>
      </div>
      {sorted.length === 0 ? (
        <p className="muted">{ja.noEventsForFacility}</p>
      ) : (
        <ul className="event-list">
          {sorted.map((e) => (
            <li key={e.id} className="event-item" style={{ cursor: "default" }}>
              <div className="event-item__top">
                <span className="event-item__date">{e.date}</span>
                <span className="type-pill">{ja.eventTypeLabel(e.type)}</span>
                <span className="badge">{ja.unverifiedBadge}</span>
              </div>
              <p className="muted" style={{ margin: "4px 0" }}>{e.notes}</p>
              <div className="event-item__meta">
                {ja.signalStrength}: {e.signal_strength}
                {e.provenance?.retrieved_at && (
                  <>
                    {" ・ "}
                    {ja.retrievedAt}: {e.provenance.retrieved_at}
                  </>
                )}
              </div>
              <a href={e.source_url} target="_blank" rel="noopener noreferrer">
                {ja.viewSource} ↗
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
