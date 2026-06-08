"use client";

import { useMemo } from "react";

import { ja } from "@/lib/i18n";
import type { AoiFeatureCollection, MonitorEvent } from "@/lib/types";

interface Props {
  aois: AoiFeatureCollection;
  events: MonitorEvent[];
  selectedAoiId: string | null;
  onSelect: (id: string | null) => void;
}

export default function FacilityList({
  aois,
  events,
  selectedAoiId,
  onSelect,
}: Props) {
  const counts = useMemo(() => {
    const map = new Map<string, number>();
    for (const e of events) map.set(e.aoi_id, (map.get(e.aoi_id) ?? 0) + 1);
    return map;
  }, [events]);

  return (
    <div className="card">
      <div className="card__heading">
        {ja.facilitiesHeading}
        <small>{aois.features.length}</small>
      </div>
      <ul className="facility-list">
        {aois.features.map((f) => {
          const p = f.properties;
          const active = p.id === selectedAoiId;
          const count = counts.get(p.id) ?? 0;
          return (
            <li
              key={p.id}
              className={`facility-item${active ? " facility-item--active" : ""}`}
              onClick={() => onSelect(active ? null : p.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") onSelect(active ? null : p.id);
              }}
            >
              <div className="facility-item__name">{p.name_ja}</div>
              <div className="facility-item__meta">
                {p.island_ja ?? p.island} ・ {ja.facilityType(p.facility_type)} ・{" "}
                {ja.eventsCount(count)}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
