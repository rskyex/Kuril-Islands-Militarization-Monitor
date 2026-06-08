"use client";

import { useRef, useState } from "react";

import { ja } from "@/lib/i18n";
import type { AoiImageRef } from "@/lib/types";

interface Props {
  baseline: AoiImageRef | null;
  recent: AoiImageRef | null;
  isSample: boolean;
}

// A before/after swipe: the recent image is overlaid on the baseline and
// clipped by a draggable divider. Falls back gracefully when only one of the
// two scenes is available.
export default function ImageCompare({ baseline, recent, isSample }: Props) {
  const [pos, setPos] = useState(50); // divider position, percent
  const frameRef = useRef<HTMLDivElement | null>(null);

  // With only one image, just show it labeled.
  if (!baseline || !recent) {
    const only = recent ?? baseline;
    if (!only) return <p className="muted">{ja.opticalNone}</p>;
    const label = recent ? ja.opticalRecent : ja.opticalBaseline;
    return (
      <figure className="compare compare--single">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={only.image_url} alt={`${label} ${only.date}`} />
        <figcaption className="muted">
          {label}: {only.date}
          {only.cloud_pct != null && ` ・ ${ja.opticalCloud} ${only.cloud_pct}%`}
        </figcaption>
      </figure>
    );
  }

  const move = (clientX: number) => {
    const el = frameRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const next = ((clientX - rect.left) / rect.width) * 100;
    setPos(Math.max(0, Math.min(100, next)));
  };

  return (
    <div className="compare">
      <div
        ref={frameRef}
        className="compare__frame"
        onMouseMove={(e) => e.buttons === 1 && move(e.clientX)}
        onClick={(e) => move(e.clientX)}
        onTouchMove={(e) => e.touches[0] && move(e.touches[0].clientX)}
        role="slider"
        aria-label={ja.opticalCompareHint}
        aria-valuenow={Math.round(pos)}
        aria-valuemin={0}
        aria-valuemax={100}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft") setPos((p) => Math.max(0, p - 5));
          if (e.key === "ArrowRight") setPos((p) => Math.min(100, p + 5));
        }}
      >
        {/* Baseline (bottom layer) */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          className="compare__img"
          src={baseline.image_url}
          alt={`${ja.opticalBaseline} ${baseline.date}`}
          draggable={false}
        />
        {/* Recent (top layer, clipped to the left of the divider) */}
        <div
          className="compare__overlay"
          style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            className="compare__img"
            src={recent.image_url}
            alt={`${ja.opticalRecent} ${recent.date}`}
            draggable={false}
          />
        </div>
        <div className="compare__divider" style={{ left: `${pos}%` }} />
        <span className="compare__tag compare__tag--left">{ja.opticalRecent}</span>
        <span className="compare__tag compare__tag--right">{ja.opticalBaseline}</span>
      </div>

      <div className="compare__meta muted">
        <span>
          {ja.opticalRecent}: {recent.date}
          {recent.cloud_pct != null && ` (${ja.opticalCloud} ${recent.cloud_pct}%)`}{" "}
          <a href={recent.source_url} target="_blank" rel="noopener noreferrer">
            ↗
          </a>
        </span>
        <span>
          {ja.opticalBaseline}: {baseline.date}
          {baseline.cloud_pct != null &&
            ` (${ja.opticalCloud} ${baseline.cloud_pct}%)`}{" "}
          <a href={baseline.source_url} target="_blank" rel="noopener noreferrer">
            ↗
          </a>
        </span>
      </div>
      <p className="muted">{ja.opticalCompareHint}</p>
      {isSample && <p className="muted">{ja.opticalSampleNote}</p>}
    </div>
  );
}
