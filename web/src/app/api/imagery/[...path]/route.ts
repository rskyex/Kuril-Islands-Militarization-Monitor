// Serves Sentinel-2 thumbnails written by the pipeline to ../data/imagery.
//
// Keeping generated imagery under data/ (alongside events.json / imagery.json)
// rather than web/public decouples the pipeline output from the web app's
// layout. The committed *sample* imagery is served statically from
// web/public/imagery-sample instead and does not go through this route.

import { promises as fs } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";

const IMAGERY_DIR = path.join(process.cwd(), "..", "data", "imagery");

const CONTENT_TYPES: Record<string, string> = {
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
};

export async function GET(
  _request: Request,
  { params }: { params: { path: string[] } },
) {
  // Resolve and confine the request strictly within IMAGERY_DIR to prevent
  // path traversal (e.g. ../../).
  const rel = (params.path ?? []).join("/");
  const target = path.normalize(path.join(IMAGERY_DIR, rel));
  if (target !== IMAGERY_DIR && !target.startsWith(IMAGERY_DIR + path.sep)) {
    return new NextResponse("Not found", { status: 404 });
  }

  const ext = path.extname(target).toLowerCase();
  const contentType = CONTENT_TYPES[ext];
  if (!contentType) {
    return new NextResponse("Unsupported media type", { status: 415 });
  }

  try {
    const data = await fs.readFile(target);
    return new NextResponse(data, {
      status: 200,
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=300",
      },
    });
  } catch {
    return new NextResponse("Not found", { status: 404 });
  }
}
