// Persists human-added commercial-image confirmation links to
// ../data/confirmations.json (upsert by event id). This is the only place
// commercial imagery enters the tool — as an optional manual link a human
// attaches for verification. It does NOT change an event's automated
// `status`, which stays "unverified".
//
// POST { event_id, url, note? }  -> upsert
// The file is human-curated and persistent (not pipeline output), so it is
// committed to the repo and edited here or by hand.

import { promises as fs } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";

const CONFIRMATIONS_PATH = path.join(
  process.cwd(),
  "..",
  "data",
  "confirmations.json",
);

interface Confirmation {
  url: string;
  note?: string;
  added_at: string;
}

interface ConfirmationsFile {
  schema_version: number;
  byEventId: Record<string, Confirmation>;
  // Preserve any other human-authored top-level fields (e.g. _note).
  [key: string]: unknown;
}

function isHttpUrl(value: unknown): value is string {
  if (typeof value !== "string") return false;
  try {
    const u = new URL(value);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}

async function readFile(): Promise<ConfirmationsFile> {
  try {
    const raw = await fs.readFile(CONFIRMATIONS_PATH, "utf-8");
    const parsed = JSON.parse(raw) as Partial<ConfirmationsFile>;
    // Preserve all existing top-level fields (e.g. _note); just ensure the
    // required keys are present.
    return {
      schema_version: 1,
      ...parsed,
      byEventId: parsed.byEventId ?? {},
    };
  } catch {
    return { schema_version: 1, byEventId: {} };
  }
}

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON" }, { status: 400 });
  }

  const { event_id, url, note } = (body ?? {}) as Record<string, unknown>;
  if (typeof event_id !== "string" || !event_id.trim()) {
    return NextResponse.json({ error: "event_id is required" }, { status: 400 });
  }
  if (!isHttpUrl(url)) {
    return NextResponse.json(
      { error: "url must be a valid http(s) URL" },
      { status: 400 },
    );
  }

  const confirmation: Confirmation = {
    url,
    ...(typeof note === "string" && note.trim() ? { note: note.trim() } : {}),
    added_at: new Date().toISOString(),
  };

  try {
    const file = await readFile();
    file.byEventId[event_id] = confirmation;
    await fs.writeFile(
      CONFIRMATIONS_PATH,
      JSON.stringify(file, null, 2),
      "utf-8",
    );
  } catch (err) {
    // E.g. read-only deploy — surface a clear message rather than 500-ing blind.
    return NextResponse.json(
      { error: `could not persist confirmation: ${(err as Error).message}` },
      { status: 500 },
    );
  }

  return NextResponse.json({ ok: true, event_id, confirmation });
}
