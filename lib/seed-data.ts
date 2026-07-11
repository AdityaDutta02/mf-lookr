// Loads a seed bundle for one AMC, transparently supporting either a single
// ./data.json (small AAMCs, under GitHub's ~100MB hard file-size cap) or a
// chunked ./data-0.json, ./data-1.json, ... series (full-history bundles that
// exceed it — GitHub outright rejects a >100MB file, not just warns). Chunks
// are produced by tools/split_bundle.py and merged back here at request time.
import fs from "node:fs";
import path from "node:path";

export interface Bundle {
  amcs: Record<string, unknown>[];
  funds: Record<string, unknown>[];
  disclosures: Record<string, unknown>[];
}

export function loadBundle(amcDir: string): Bundle {
  const base = path.join(process.cwd(), "app/api/admin", amcDir);
  const singlePath = path.join(base, "data.json");
  if (fs.existsSync(singlePath)) {
    return JSON.parse(fs.readFileSync(singlePath, "utf8")) as Bundle;
  }

  // Each chunk file (see tools/split_bundle.py) repeats the full amcs/funds
  // identity rows for convenience — dedupe them back down here rather than
  // spamming unique_violation errors from every chunk-after-the-first.
  const amcsBySlug = new Map<string, Record<string, unknown>>();
  const fundsByCode = new Map<string, Record<string, unknown>>();
  const disclosures: Record<string, unknown>[] = [];
  let i = 0;
  while (fs.existsSync(path.join(base, `data-${i}.json`))) {
    const part = JSON.parse(fs.readFileSync(path.join(base, `data-${i}.json`), "utf8")) as Partial<Bundle>;
    for (const a of part.amcs ?? []) amcsBySlug.set(String((a as { slug?: string }).slug), a);
    for (const f of part.funds ?? []) fundsByCode.set(String((f as { amfi_code?: string }).amfi_code), f);
    disclosures.push(...(part.disclosures ?? []));
    i++;
  }
  if (i === 0) {
    throw new Error(`No data.json or data-N.json found under app/api/admin/${amcDir}`);
  }
  return { amcs: [...amcsBySlug.values()], funds: [...fundsByCode.values()], disclosures };
}
