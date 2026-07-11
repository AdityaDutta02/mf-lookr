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
