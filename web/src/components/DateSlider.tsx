"use client";

import { ja } from "@/lib/i18n";

interface Props {
  dates: string[]; // ascending unique dates
  value: string; // current window-start date
  onChange: (date: string) => void;
  shownCount: number;
}

export default function DateSlider({ dates, value, onChange, shownCount }: Props) {
  const index = Math.max(0, dates.indexOf(value));
  const last = dates.length - 1;

  return (
    <div className="card controls">
      <div className="card__heading">
        {ja.dateRangeLabel}
        <small>{ja.eventsCount(shownCount)}</small>
      </div>
      <input
        type="range"
        min={0}
        max={last}
        step={1}
        value={index}
        onChange={(e) => onChange(dates[Number(e.target.value)] ?? dates[0]!)}
        aria-label={ja.dateRangeLabel}
      />
      <div className="controls__row">
        <span>{value || dates[0]}</span>
        <span>{dates[last]}</span>
      </div>
    </div>
  );
}
