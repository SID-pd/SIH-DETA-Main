/**
 * Minimal data-fetching hooks.
 *
 * Deliberately dependency-free rather than pulling in TanStack Query: at five screens
 * the surface we need is abort-on-unmount, in-flight dedupe, manual refetch, and
 * optional polling. Swapping to TanStack later is a mechanical change because every
 * page consumes the same {data, meta, error, loading} shape.
 *
 * The `meta` passthrough is the point: pages render provenance, so a stale or
 * schedule-only answer looks different from a live one.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { Meta, Result } from '../lib/api';
import { ApiFailure } from '../lib/api';

export interface QueryState<T> {
  data: T | null;
  meta: Meta | null;
  error: ApiFailure | null;
  loading: boolean;
  /** True while re-fetching with data already on screen (avoids layout flicker). */
  refreshing: boolean;
  refetch: (forceFresh?: boolean | unknown) => void;
}

export function useQuery<T>(
  fetcher: ((signal: AbortSignal, opts?: { forceFresh?: boolean }) => Promise<Result<T>>) | null,
  deps: unknown[],
  opts: { pollMs?: number; enabled?: boolean } = {},
): QueryState<T> {
  const { pollMs, enabled = true } = opts;
  const [data, setData] = useState<T | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<ApiFailure | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [tick, setTick] = useState(0);
  const forceFreshRef = useRef(false);

  const abortRef = useRef<AbortController | null>(null);
  const hasData = useRef(false);

  const run = useCallback(async () => {
    if (!fetcher || !enabled) return;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    const isForceFresh = forceFreshRef.current;
    forceFreshRef.current = false;

    if (hasData.current) setRefreshing(true);
    else setLoading(true);

    try {
      const res = await fetcher(ctrl.signal, { forceFresh: isForceFresh });
      if (ctrl.signal.aborted) return;
      setData(res.data);
      setMeta(res.meta);
      setError(null);
      hasData.current = true;
    } catch (err) {
      if ((err as Error).name === 'AbortError') return;
      // Keep any previously-loaded data on screen and surface the error alongside it,
      // so a failed refresh degrades visibly instead of blanking the page.
      setError(err instanceof ApiFailure
        ? err
        : new ApiFailure('UNKNOWN', (err as Error).message, true, 0));
    } finally {
      if (!ctrl.signal.aborted) {
        setLoading(false);
        setRefreshing(false);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled, tick]);

  useEffect(() => {
    hasData.current = false;
    setData(null);
    setMeta(null);
    setError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    run();
    return () => abortRef.current?.abort();
  }, [run]);

  useEffect(() => {
    if (!pollMs || !enabled) return;
    const id = setInterval(() => setTick((t) => t + 1), pollMs);
    return () => clearInterval(id);
  }, [pollMs, enabled]);

  const refetch = useCallback((forceFresh: boolean | unknown = true) => {
    forceFreshRef.current = typeof forceFresh === 'boolean' ? forceFresh : true;
    setTick((t) => t + 1);
  }, []);

  return { data, meta, error, loading, refreshing, refetch };
}

/** Debounced value — used for search-as-you-type so we don't hammer the API. */
export function useDebounced<T>(value: T, ms = 250): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
}
