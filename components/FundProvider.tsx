'use client';

// Ported from mf-analyser/components/FundProvider.tsx, adapted to this app's
// data model: a fund is identified by amfi_code (FundSummary), not the old
// app's synthetic scheme id, and there's no curated deep-link list here —
// any fund resolved via /api/search or /api/funds can be selected. Holds the
// selected fund + period and shares them between FundContextBar, SearchView
// and the analyse content, same structure as the old app.
import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { useEmbedToken } from '@/hooks/use-embed-token';
import type { FundSummary } from '@/lib/types';

interface PeriodRow {
  period: string;
}

async function api<T>(path: string, token: string): Promise<T> {
  const res = await fetch(path, { headers: { 'x-embed-token': token } });
  if (!res.ok) throw new Error((await res.json().catch(() => ({ error: res.statusText }))).error ?? res.statusText);
  return res.json() as Promise<T>;
}

interface FundCtx {
  fund: FundSummary | null;
  period: string | null;
  selectFund: (f: FundSummary) => void;
  selectPeriod: (p: string) => void;
  /** Set fund + period together (e.g. from a deep search result that already knows the period). */
  selectFundAndPeriod: (f: FundSummary, p: string) => void;
  token: string | null;
}

const FundContext = createContext<FundCtx | null>(null);

export function useFund(): FundCtx {
  const ctx = useContext(FundContext);
  if (!ctx) throw new Error('useFund must be used within FundProvider');
  return ctx;
}

export function FundProvider({ children }: { children: React.ReactNode }) {
  const token = useEmbedToken();
  const [fund, setFund] = useState<FundSummary | null>(null);
  const [period, setPeriod] = useState<string | null>(null);
  // When set, the next fund-change effect uses this period instead of auto-picking the latest.
  const lockedPeriod = useRef<string | null>(null);

  // On fund (or token) change, default to the latest stored period — unless an
  // explicit period was locked in by selectFundAndPeriod.
  useEffect(() => {
    if (!fund || !token) {
      setPeriod(null);
      return;
    }
    if (lockedPeriod.current) {
      setPeriod(lockedPeriod.current);
      lockedPeriod.current = null;
      return;
    }
    let cancelled = false;
    api<PeriodRow[]>(`/api/periods?fund=${fund.amfi_code}`, token)
      .then((periods) => {
        if (cancelled) return;
        // /api/periods already sorts newest-first.
        setPeriod(periods[0] ? periods[0].period : null);
      })
      .catch(() => {
        /* leave period as-is */
      });
    return () => {
      cancelled = true;
    };
  }, [fund, token]);

  function selectFund(f: FundSummary) {
    setFund(f);
  }
  function selectPeriod(p: string) {
    setPeriod(p);
  }
  function selectFundAndPeriod(f: FundSummary, p: string) {
    lockedPeriod.current = p;
    setFund(f);
    setPeriod(p);
  }

  return (
    <FundContext.Provider value={{ fund, period, selectFund, selectPeriod, selectFundAndPeriod, token }}>
      {children}
    </FundContext.Provider>
  );
}
