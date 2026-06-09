// Mirror the committed seed/sample data from the repo-root data/ dir into
// web/src/seed/ so it can be imported (bundled) without the build depending on
// files outside the Vercel "Root Directory" (web/).
//
// Tolerant by design: if the repo-root data/ dir is not present (e.g. a Vercel
// build with Root Directory = web/ and "Include files outside the root
// directory" left unchecked), it silently skips and the already-committed
// copies in src/seed/ are used. Runs automatically before `dev` and `build`
// (predev/prebuild), or on demand via `npm run sync-seed`.

import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_DATA = path.join(__dirname, "..", "..", "data");
const SEED_DIR = path.join(__dirname, "..", "src", "seed");

const FILES = [
  "aois.geojson",
  "events.sample.json",
  "imagery.sample.json",
  "confirmations.json",
];

let copied = 0;
await fs.mkdir(SEED_DIR, { recursive: true });
for (const name of FILES) {
  const src = path.join(REPO_DATA, name);
  try {
    await fs.copyFile(src, path.join(SEED_DIR, name));
    copied += 1;
  } catch {
    // Source not available (e.g. on Vercel) — keep the committed copy.
  }
}
console.log(
  copied > 0
    ? `sync-seed: refreshed ${copied}/${FILES.length} seed file(s) from data/`
    : "sync-seed: repo-root data/ not available; using committed src/seed/ copies",
);
