// Server-side data loading.
//
// Two data sources, in priority order:
//
//  1. LIVE files written by the pipeline to the repo-root data/ dir (events.json,
//     imagery.json, and optionally an edited aois.geojson / confirmations.json).
//     These are read from the filesystem and are picked up without a rebuild.
//     Available when running a self-hosted Node server (`next start`) from web/,
//     or via the KURIL_DATA_DIR override.
//
//  2. BUNDLED seed/sample data, imported below so it is compiled into the
//     server bundle. This is the fallback and is ALWAYS available — including
//     on serverless hosts like Vercel, where the repo-root data/ dir is NOT
//     part of the deployment and the filesystem reads in (1) simply return null.
//
// This makes the app deploy cleanly to Vercel (it renders the bundled sample
// data) while still showing live pipeline output when self-hosted.

import "server-only";
import { promises as fs } from "node:fs";
import path from "node:path";

// Bundled seed/sample data. These live INSIDE web/ (src/seed/) — mirrored from
// the repo-root data/ dir by `npm run sync-seed` — so the build never depends
// on files outside the Vercel "Root Directory" (web/). They are imported here
// (compiled into the server bundle) and used as the fallback when no live
// pipeline output is present.
import aoisSeed from "@/seed/aois.geojson";
import confirmationsSeed from "@/seed/confirmations.json";
import eventsSample from "@/seed/events.sample.json";
import imagerySample from "@/seed/imagery.sample.json";

import type {
  AoiFeatureCollection,
  AoiImagery,
  DataOrigin,
  EventConfirmation,
  MonitorData,
  MonitorEvent,
} from "./types";

// Live pipeline-output directory. Defaults to the repo-root data/ dir (works
// for local dev / self-hosted `next start`); override with KURIL_DATA_DIR. On
// Vercel this path is outside the function bundle, so reads return null and the
// bundled seed data is used instead.
const DATA_DIR = process.env.KURIL_DATA_DIR ?? path.join(process.cwd(), "..", "data");

async function readLiveJson(name: string): Promise<unknown | null> {
  try {
    const raw = await fs.readFile(path.join(DATA_DIR, name), "utf-8");
    return JSON.parse(raw);
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

function normalizeImagery(parsed: unknown): Record<string, AoiImagery> {
  if (parsed && typeof parsed === "object" && "aois" in parsed) {
    const aois = (parsed as { aois: unknown }).aois;
    if (aois && typeof aois === "object") {
      return aois as Record<string, AoiImagery>;
    }
  }
  return {};
}

function normalizeConfirmations(parsed: unknown): Record<string, EventConfirmation> {
  if (parsed && typeof parsed === "object" && "byEventId" in parsed) {
    const map = (parsed as { byEventId: unknown }).byEventId;
    if (map && typeof map === "object") {
      return map as Record<string, EventConfirmation>;
    }
  }
  return {};
}

export async function loadMonitorData(): Promise<MonitorData> {
  // AOIs: a live (edited) config overrides the bundled seed; the seed is always
  // present so this never throws.
  const liveAois = await readLiveJson("aois.geojson");
  const aois = (liveAois as AoiFeatureCollection | null) ?? (aoisSeed as AoiFeatureCollection);

  // Events: live store -> bundled sample.
  let events = normalizeEvents(await readLiveJson("events.json"));
  let origin: DataOrigin = "live";
  if (events.length === 0) {
    events = normalizeEvents(eventsSample);
    origin = events.length > 0 ? "sample" : "empty";
  }

  // Confirmations: live file -> bundled seed.
  const confParsed = (await readLiveJson("confirmations.json")) ?? confirmationsSeed;
  const confirmations = normalizeConfirmations(confParsed);
  for (const ev of events) {
    const c = confirmations[ev.id];
    if (c) ev.confirmation = c;
  }

  // Stable order: newest first for feeds.
  events.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));

  // Imagery: live index -> bundled sample.
  let imagery = normalizeImagery(await readLiveJson("imagery.json"));
  let imageryOrigin: DataOrigin = "live";
  if (Object.keys(imagery).length === 0) {
    imagery = normalizeImagery(imagerySample);
    imageryOrigin = Object.keys(imagery).length > 0 ? "sample" : "empty";
  }

  return { aois, events, origin, imagery, imageryOrigin };
}
