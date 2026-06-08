// Server-side data loading.
//
// The AOI config and event store live in ../data at the repo root (outside
// the web app). This module reads them at request time. If the live event
// store (data/events.json) is missing or empty, it falls back to the bundled
// sample (data/events.sample.json) so the UI is demonstrable out of the box,
// and reports which origin was used so the UI can be transparent.

import "server-only";
import { promises as fs } from "node:fs";
import path from "node:path";

import type {
  AoiFeatureCollection,
  AoiImagery,
  DataOrigin,
  MonitorData,
  MonitorEvent,
} from "./types";

// Resolve the repo-root data directory relative to the Next.js cwd (web/).
const DATA_DIR = path.join(process.cwd(), "..", "data");
const AOIS_PATH = path.join(DATA_DIR, "aois.geojson");
const EVENTS_PATH = path.join(DATA_DIR, "events.json");
const EVENTS_SAMPLE_PATH = path.join(DATA_DIR, "events.sample.json");
const IMAGERY_PATH = path.join(DATA_DIR, "imagery.json");
const IMAGERY_SAMPLE_PATH = path.join(DATA_DIR, "imagery.sample.json");

async function readJson<T>(filePath: string): Promise<T | null> {
  try {
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function normalizeEvents(parsed: unknown): MonitorEvent[] {
  if (Array.isArray(parsed)) return parsed as MonitorEvent[];
  if (parsed && typeof parsed === "object" && "events" in parsed) {
    const events = (parsed as { events: unknown }).events;
    if (Array.isArray(events)) return events as MonitorEvent[];
  }
  return [];
}

export async function loadMonitorData(): Promise<MonitorData> {
  const aois = await readJson<AoiFeatureCollection>(AOIS_PATH);
  if (!aois) {
    throw new Error(
      `Could not read AOI config at ${AOIS_PATH}. Ensure data/aois.geojson exists.`,
    );
  }

  let events = normalizeEvents(await readJson(EVENTS_PATH));
  let origin: DataOrigin = "live";

  if (events.length === 0) {
    const sample = normalizeEvents(await readJson(EVENTS_SAMPLE_PATH));
    if (sample.length > 0) {
      events = sample;
      origin = "sample";
    } else {
      origin = "empty";
    }
  }

  // Stable order: newest first for feeds.
  events.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));

  const { imagery, imageryOrigin } = await loadImagery();

  return { aois, events, origin, imagery, imageryOrigin };
}

function normalizeImagery(parsed: unknown): Record<string, AoiImagery> {
  if (parsed && typeof parsed === "object" && "aois" in parsed) {
    const aois = (parsed as { aois: unknown }).aois;
    if (aois && typeof aois === "object") {
      return aois as Record<string, AoiImagery>;
    }
  }
  return {};
}

async function loadImagery(): Promise<{
  imagery: Record<string, AoiImagery>;
  imageryOrigin: DataOrigin;
}> {
  let imagery = normalizeImagery(await readJson(IMAGERY_PATH));
  let imageryOrigin: DataOrigin = "live";
  if (Object.keys(imagery).length === 0) {
    const sample = normalizeImagery(await readJson(IMAGERY_SAMPLE_PATH));
    if (Object.keys(sample).length > 0) {
      imagery = sample;
      imageryOrigin = "sample";
    } else {
      imageryOrigin = "empty";
    }
  }
  return { imagery, imageryOrigin };
}
