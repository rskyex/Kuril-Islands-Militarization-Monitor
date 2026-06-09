"use client";

import { ja } from "@/lib/i18n";
import type { AoiFeature, AoiImagery, MonitorEvent } from "@/lib/types";
import ConfirmationControl from "./ConfirmationControl";
import ImageCompare from "./ImageCompare";

interface Props {
  aoi: AoiFeature;
  events: MonitorEvent[];
  imagery: AoiImagery | null;
  imageryIsSample: boolean;
  onClear: () => void;
}

export default function FacilityPanel({
  aoi,
  events,
  imagery,
  imageryIsSample,
  onClear,
}: Props) {
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
        {ja.opticalHeading}
      </div>
      {imagery && (imagery.baseline || imagery.recent) ? (
        <ImageCompare
          baseline={imagery.baseline}
          recent={imagery.recent}
          isSample={imageryIsSample}
        />
      ) : (
        <p className="muted">{ja.opticalNone}</p>
      )}

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
              <ConfirmationControl
                eventId={e.id}
                confirmation={e.confirmation}
              />
            </li>
          ))}
        </ul>
      )}
      <p className="muted" style={{ marginTop: 6 }}>
        {ja.confirmationNote}
      </p>

      <div className="card__heading" style={{ marginTop: 12 }}>
        {ja.verificationHeading}
        <span className="badge">{ja.unverifiedBadge}</span>
      </div>
      <ol className="verify-steps muted">
        {ja.verificationSteps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
    </div>
  );
}
