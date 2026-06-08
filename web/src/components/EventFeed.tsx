"use client";

import { ja } from "@/lib/i18n";
import { EVENT_COLORS } from "@/lib/style";
import type { AoiFeatureCollection, EventType, MonitorEvent } from "@/lib/types";

interface Props {
  events: MonitorEvent[];
  aois: AoiFeatureCollection;
  onSelectAoi: (id: string) => void;
}

function aoiName(aois: AoiFeatureCollection, aoiId: string): string {
  return (
    aois.features.find((f) => f.properties.id === aoiId)?.properties.name_ja ??
    aoiId
  );
}

export default function EventFeed({ events, aois, onSelectAoi }: Props) {
  return (
    <div className="card">
      <div className="card__heading">
        {ja.eventFeedHeading}
        <small>{ja.eventsCount(events.length)}</small>
      </div>
      {events.length === 0 ? (
        <p className="muted">{ja.noEventsForFacility}</p>
      ) : (
        <ul className="event-list">
          {events.map((e) => {
            const color = EVENT_COLORS[e.type as EventType] ?? EVENT_COLORS.other;
            return (
              <li
                key={e.id}
                className="event-item"
                onClick={() => onSelectAoi(e.aoi_id)}
                role="button"
                tabIndex={0}
                onKeyDown={(ev) => {
                  if (ev.key === "Enter" || ev.key === " ") onSelectAoi(e.aoi_id);
                }}
              >
                <div className="event-item__top">
                  <span className="dot" style={{ background: color }} aria-hidden />
                  <span className="event-item__date">{e.date}</span>
                  <span className="type-pill">{ja.eventTypeLabel(e.type)}</span>
                  <span className="badge">{ja.unverifiedBadge}</span>
                </div>
                <div className="event-item__meta">{aoiName(aois, e.aoi_id)}</div>
                <div
                  className="strength-bar"
                  title={`${ja.signalStrength}: ${e.signal_strength}`}
                >
                  <div
                    className="strength-bar__fill"
                    style={{
                      width: `${Math.round(e.signal_strength * 100)}%`,
                      background: color,
                    }}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
