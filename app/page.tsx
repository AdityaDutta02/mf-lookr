'use client';

// Thin composing shell — the monolithic version of this file (raw fetches to
// /api/amcs, /api/funds, /api/periods, /api/changes, /api/admin/seed-ppfas
// inline, no components/ directory) has been replaced by the ported/rebuilt
// component set. FundContextBar is docked at top; below it is either
// SearchView (home screen — no fund+period selected yet) or the full analyse
// content once a fund+period is selected, mirroring mf-analyser's
// AnalyseView.tsx layout.
import { useEffect, useState } from 'react';
import { FundProvider, useFund } from '@/components/FundProvider';
import { FundContextBar } from '@/components/FundContextBar';
import { SearchView } from '@/components/SearchView';
import { AnalyseContent } from '@/components/AnalyseContent';
import { Footer } from '@/components/Footer';

async function api<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { ...init, headers: { ...(init?.headers ?? {}), 'x-embed-token': token } });
  if (!res.ok) throw new Error((await res.json().catch(() => ({ error: res.statusText }))).error ?? res.statusText);
  return res.json() as Promise<T>;
}

// Takes getToken() (not a static token string) — a full-history AMC's seed
// runs long enough that the embed token can be refreshed by the viewer
// shell mid-operation (see FundProvider's getToken doc comment); calling
// getToken() fresh before every single step, instead of once up front,
// means the loop never gets stuck holding a token the shell has already
// rotated away from.
async function seedAction<T>(
  slug: string,
  getToken: () => string | null,
  action: string,
  body?: Record<string, unknown>,
): Promise<T> {
  const token = getToken();
  if (!token) throw new Error('lost embed token mid-seed — reload and retry');
  return api<T>(`/api/admin/seed-${slug}`, token, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, ...body }),
  });
}

// Each entry needs a deployed app/api/admin/seed-<slug>/route.ts + bundled
// data.json (built by tools/build_dataset_<slug>.py) — this list only grows
// as each fund house's local parse-and-verify pass is done, never before.
const SEED_TARGETS = [
  { slug: 'ppfas', label: 'PPFAS' },
  { slug: 'hdfc', label: 'HDFC' },
  { slug: 'invesco', label: 'Invesco' },
  { slug: 'nippon', label: 'Nippon India' },
  { slug: 'helios', label: 'Helios' },
  { slug: 'mirae', label: 'Mirae Asset' },
  { slug: 'motilal', label: 'Motilal Oswal' },
  { slug: 'navi', label: 'Navi' },
  { slug: 'sbi', label: 'SBI' },
  { slug: 'icici', label: 'ICICI Prudential' },
  { slug: 'axis', label: 'Axis' },
];

function PageBody() {
  const { fund, period, token, getToken } = useFund();
  const [seedTarget, setSeedTarget] = useState(SEED_TARGETS[1].slug); // default to HDFC — PPFAS is already loaded
  const [seeding, setSeeding] = useState(false);
  const [seedStatus, setSeedStatus] = useState<string | null>(null);
  const [showSeed, setShowSeed] = useState(false);

  useEffect(() => {
    // Server-read flag (see app/api/admin/show-seed/route.ts) — deliberately
    // NOT a NEXT_PUBLIC_ build-time constant, so toggling it via set_env_var
    // + redeploy actually takes effect without a rebuild.
    fetch('/api/admin/show-seed')
      .then((r) => r.json())
      .then((d: { showSeed: boolean }) => setShowSeed(d.showSeed))
      .catch(() => {});
  }, []);

  if (!token) {
    return <main className="min-h-[100dvh] flex items-center justify-center text-fg-secondary text-sm">Connecting…</main>;
  }

  // Seeding is driven step-by-step from here rather than one big server
  // request — a full-history AMC's scrub-then-reload (1000+ deletes,
  // thousands of inserts) took long enough in a single request that the
  // platform gateway's own timeout killed the connection with a 502 before
  // the route could respond, even though the work was succeeding
  // server-side. Each step below is small and fast; see lib/seed-actions.ts.
  async function seed() {
    if (!token) return;
    setSeeding(true);
    setSeedStatus(null);
    try {
      // window.alert() is silently swallowed inside the embedded viewer iframe
      // (no "allow-modals" permission) — surface progress in-page instead.
      // Scrub old rows PER FUND, not AMC-wide — an AMC-wide list pulls every
      // matching row's full holdings JSONB just to read its id, and that
      // response was itself large enough to 502 even for a modest existing
      // window (see lib/seed-actions.ts). Per-fund keeps every call tiny.
      const { amfiCodes } = await seedAction<{ amfiCodes: string[] }>(seedTarget, getToken, 'list-funds');
      let cleared = 0;
      for (let i = 0; i < amfiCodes.length; i++) {
        const res = await seedAction<{ cleared: number }>(seedTarget, getToken, 'clear-fund', {
          amfiCode: amfiCodes[i],
        });
        cleared += res.cleared;
        setSeedStatus(`Seeding ${seedTarget}: clearing old data ${i + 1}/${amfiCodes.length} funds…`);
      }

      const identity = await seedAction<{
        amcs: { inserted: number; errors: unknown[] };
        funds: { inserted: number; errors: unknown[] };
      }>(seedTarget, getToken, 'insert-identity');

      let offset = 0;
      let total = 0;
      let inserted = 0;
      for (;;) {
        const res = await seedAction<{ inserted: number; nextOffset: number; total: number; done: boolean }>(
          seedTarget,
          getToken,
          'insert-disclosures-batch',
          { offset },
        );
        inserted += res.inserted;
        offset = res.nextOffset;
        total = res.total;
        setSeedStatus(`Seeding ${seedTarget}: ${offset}/${total} disclosures…`);
        if (res.done) break;
      }

      setSeedStatus(
        `Seeded ${seedTarget}: amcs=${identity.amcs.inserted}, funds=${identity.funds.inserted}, disclosures=${inserted}/${total} (cleared ${cleared} old rows)`,
      );
    } catch (e) {
      setSeedStatus(`Seed failed (${seedTarget}): ${(e as Error).message}`);
    } finally {
      setSeeding(false);
    }
  }

  return (
    <div className="min-h-[100dvh] flex flex-col">
      <FundContextBar
        showSeed={showSeed}
        seedTargets={SEED_TARGETS}
        seedTarget={seedTarget}
        onSeedTargetChange={setSeedTarget}
        seeding={seeding}
        seedStatus={seedStatus}
        onSeed={seed}
      />
      <main className="flex-1 max-w-screen-2xl mx-auto w-full px-4 sm:px-6 py-6">
        {fund && period ? <AnalyseContent /> : <SearchView />}
      </main>
      <Footer />
    </div>
  );
}

export default function HomePage() {
  return (
    <FundProvider>
      <PageBody />
    </FundProvider>
  );
}
