// Small client-side presentation helpers shared by the ported components.
// Ported from mf-analyser/lib/client.ts's catColor (the only bit of that file
// the components actually need) — kept minimal rather than importing the old
// app's whole client SDK, which doesn't apply to this app's data-fetch pattern.

// Category colour assignment — stable per name, from the editorial palette
// defined in app/globals.css (--cat-1..--cat-8, already ported from the old app).
const CAT_VARS = ["--cat-1", "--cat-2", "--cat-3", "--cat-4", "--cat-5", "--cat-6", "--cat-7", "--cat-8"];

export function catColor(index: number, name?: string): string {
  if (name && /cash|treps|receivable/i.test(name)) return "var(--cat-8)";
  return `var(${CAT_VARS[index % CAT_VARS.length]})`;
}

// Some source parsers (e.g. tools/parse_ppfas_xlsx.py, unlike parse_ppfas.py)
// don't strip the "(DD/MM/YYYY)" maturity-date suffix or a trailing footnote
// "#" marker from a debt-paper holding's display name before it reaches the
// stored data. Splitting it out here keeps the maturity date visible (useful)
// without it reading as part of the company name (confusing — see
// InstrumentTag / task brief bug 3).
const MATURITY_SUFFIX_RE = /\s*\((?:MD\s*)?(\d{2}\/\d{2}\/\d{4})\)\s*#?\s*$/;
const TRAILING_HASH_RE = /\s*#\s*$/;

export function parseHoldingName(name: string): { displayName: string; maturityDate: string | null } {
  const m = name.match(MATURITY_SUFFIX_RE);
  if (m) {
    return { displayName: name.slice(0, m.index).trim(), maturityDate: m[1] };
  }
  return { displayName: name.replace(TRAILING_HASH_RE, "").trim(), maturityDate: null };
}
