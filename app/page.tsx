'use client';

// Thin composing shell — the monolithic version of this file (raw fetches to
// /api/amcs, /api/funds, /api/periods, /api/changes, /api/admin/seed-ppfas
// inline, no components/ directory) has been replaced by the ported/rebuilt
// component set. FundContextBar is docked at top; below it is either
// SearchView (home screen — no fund+period selected yet) or the full analyse
// content once a fund+period is selected, mirroring mf-analyser's
// AnalyseView.tsx layout.
import { useState } from 'react';
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

function PageBody() {
  const { fund, period, token } = useFund();
  const [seeding, setSeeding] = useState(false);
  const [seedStatus, setSeedStatus] = useState<string | null>(null);

  if (!token) {
    return <main className="min-h-[100dvh] flex items-center justify-center text-fg-secondary text-sm">Connecting…</main>;
  }

  async function seed() {
    if (!token) return;
    setSeeding(true);
    setSeedStatus(null);
    try {
      // window.alert() is silently swallowed inside the embedded viewer iframe
      // (no "allow-modals" permission) — surface the result in-page instead.
      const res = await api<Record<string, { inserted: number; errors: unknown[] }>>('/api/admin/seed-ppfas', token, {
        method: 'POST',
      });
      setSeedStatus(`Seeded: ${Object.entries(res).map(([k, v]) => `${k}=${v.inserted ?? v}`).join(', ')}`);
    } catch (e) {
      setSeedStatus(`Seed failed: ${(e as Error).message}`);
    } finally {
      setSeeding(false);
    }
  }

  return (
    <div className="min-h-[100dvh] flex flex-col">
      <FundContextBar seeding={seeding} seedStatus={seedStatus} onSeed={seed} />
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
