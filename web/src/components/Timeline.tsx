"use client";

import { extent, scaleLinear, scaleTime, timeFormat } from "d3";
import { useMemo } from "react";

import { ja } from "@/lib/i18n";
import { EVENT_COLORS } from "@/lib/style";
import type { EventType, MonitorEvent } from "@/lib/types";

// Small D3-scaled scatter of events over time (x = date, y = signal strength,
// color = type). Rendered declaratively as SVG so React owns the DOM.
const W = 360;
const H = 130;
const M = { top: 10, right: 12, bottom: 22, left: 28 };
const fmt = timeFormat("%m/%d");

export default function Timeline({ events }: { events: MonitorEvent[] }) {
  const points = useMemo(
    () =>
      events
        .map((e) => ({ ...e, t: new Date(e.date) }))
        .filter((e) => !Number.isNaN(e.t.getTime())),
    [events],
  );

  const innerW = W - M.left - M.right;
  const innerH = H - M.top - M.bottom;

  const x = useMemo(() => {
    const [lo, hi] = extent(points, (d) => d.t) as [Date?, Date?];
    const min = lo ?? new Date();
    const max = hi ?? new Date();
    // Pad a single-day domain so the point isn't on the axis edge.
    const domain =
      min.getTime() === max.getTime()
        ? [new Date(min.getTime() - 86400000), new Date(max.getTime() + 86400000)]
        : [min, max];
    return scaleTime().domain(domain).range([0, innerW]);
  }, [points, innerW]);

  const y = useMemo(
    () => scaleLinear().domain([0, 1]).range([innerH, 0]),
    [innerH],
  );

  const xTicks = x.ticks(4);
  const yTicks = [0, 0.5, 1];

  return (
    <div className="card">
      <div className="card__heading">{ja.timelineHeading}</div>
      {points.length === 0 ? (
        <p className="muted">{ja.noEventsForFacility}</p>
      ) : (
        <svg
          viewBox={`0 0 ${W} ${H}`}
          width="100%"
          role="img"
          aria-label={ja.timelineHeading}
        >
          <g transform={`translate(${M.left},${M.top})`}>
            {/* y grid + labels */}
            {yTicks.map((t) => (
              <g key={t} transform={`translate(0,${y(t)})`}>
                <line x1={0} x2={innerW} stroke="#233149" strokeWidth={1} />
                <text x={-6} y={3} fontSize={9} fill="#9fb0c7" textAnchor="end">
                  {t}
                </text>
              </g>
            ))}
            {/* x labels */}
            {xTicks.map((t, i) => (
              <text
                key={i}
                x={x(t)}
                y={innerH + 14}
                fontSize={9}
                fill="#9fb0c7"
                textAnchor="middle"
              >
                {fmt(t)}
              </text>
            ))}
            {/* event points */}
            {points.map((d) => (
              <circle
                key={d.id}
                cx={x(d.t)}
                cy={y(d.signal_strength)}
                r={3 + d.signal_strength * 4}
                fill={EVENT_COLORS[d.type as EventType] ?? EVENT_COLORS.other}
                fillOpacity={0.8}
                stroke="#0b1220"
                strokeWidth={0.8}
              >
                <title>{`${d.date} ・ ${ja.eventTypeLabel(d.type)} ・ ${d.signal_strength}`}</title>
              </circle>
            ))}
          </g>
        </svg>
      )}
      <p className="muted" style={{ marginTop: 4 }}>
        {ja.signalStrength}（縦軸） × {ja.eventDate}（横軸）
      </p>
    </div>
  );
}
