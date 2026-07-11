'use client';

// Shared debounced /api/search wiring — used by both SearchView (full-page
// home screen) and FundContextBar's compact docked fund-switcher, so the two
// don't duplicate the debounce/race-guard logic.
import { useCallback, useEffect, useRef, useState } from 'react';
import type { SearchResult } from '@/lib/types';

async function apiSearch(q: string, token: string): Promise<SearchResult> {
  const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`, { headers: { 'x-embed-token': token } });
  if (!res.ok) throw new Error((await res.json().catch(() => ({ error: res.statusText }))).error ?? res.statusText);
  return res.json() as Promise<SearchResult>;
}

export function useFundSearch(token: string | null, debounceMs = 250) {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<SearchResult>({ type: 'empty' });
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reqId = useRef(0);

  const runSearch = useCallback(
    (q: string) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (!q.trim() || !token) {
        reqId.current += 1;
        setResult({ type: 'empty' });
        setLoading(false);
        setFailed(false);
        return;
      }
      setLoading(true);
      setFailed(false);
      debounceRef.current = setTimeout(async () => {
        const id = ++reqId.current;
        try {
          const data = await apiSearch(q, token);
          if (id !== reqId.current) return;
          setResult(data);
          setLoading(false);
        } catch {
          if (id !== reqId.current) return;
          setResult({ type: 'empty' });
          setLoading(false);
          setFailed(true);
        }
      }, debounceMs);
    },
    [token, debounceMs],
  );

  useEffect(() => {
    runSearch(query);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, runSearch]);

  return { query, setQuery, result, loading, failed };
}
