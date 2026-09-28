/**
 * Dual-tier Session Cache Manager for DARPAN
 *
 * Tier 1: In-Memory Map (0ms access for active component renders)
 * Tier 2: window.sessionStorage (persists across page/tab switching and unmounts)
 *
 * Prevents redundant network refetches for static routes, schedules, and recent live data.
 */

import type { Meta, Result } from './api';

interface CacheEntry<T> {
  data: T;
  meta: Meta;
  timestamp: number;
  ttlMs: number;
}

const STORAGE_PREFIX = 'darpan_scache:';

// Default TTLs by endpoint pattern
function getTtlForPath(path: string): number {
  if (path.includes('/route.geojson')) {
    // Route geometries are immutable — keep for full session / 24 hours
    return 24 * 60 * 60 * 1000;
  }
  if (path.includes('/composition')) {
    return 30 * 60 * 1000; // 30 minutes
  }
  if (path.includes('/trains/') && !path.includes('/live')) {
    // Train schedule & metadata
    return 60 * 60 * 1000; // 1 hour
  }
  if (path.includes('/stations') && !path.includes('/board')) {
    return 30 * 60 * 1000; // 30 minutes
  }
  if (path.includes('/live')) {
    // Live running position — 60 seconds (matches poll interval)
    return 60 * 1000;
  }
  if (path.includes('/board') || path.includes('/pnr')) {
    return 60 * 1000; // 60 seconds
  }
  return 60 * 1000; // Default 1 minute
}

class SessionCacheManager {
  private memoryCache = new Map<string, CacheEntry<any>>();

  public get<T>(path: string): Result<T> | null {
    const now = Date.now();

    // 1. Check L1 Memory Cache
    const mem = this.memoryCache.get(path);
    if (mem) {
      if (now - mem.timestamp < mem.ttlMs) {
        return { data: mem.data, meta: { ...mem.meta, source: 'cache' } };
      }
      this.memoryCache.delete(path);
    }

    // 2. Check L2 sessionStorage
    try {
      if (typeof window === 'undefined' || !window.sessionStorage) return null;
      const raw = window.sessionStorage.getItem(`${STORAGE_PREFIX}${path}`);
      if (!raw) return null;

      const entry: CacheEntry<T> = JSON.parse(raw);
      if (now - entry.timestamp < entry.ttlMs) {
        // Populate L1 for future instant access
        this.memoryCache.set(path, entry);
        return { data: entry.data, meta: { ...entry.meta, source: 'cache' } };
      }

      // Expired — remove
      window.sessionStorage.removeItem(`${STORAGE_PREFIX}${path}`);
    } catch {
      // Storage unavailable or parse error — ignore
    }

    return null;
  }

  public set<T>(path: string, result: Result<T>, customTtlMs?: number): void {
    const ttlMs = customTtlMs ?? getTtlForPath(path);
    const entry: CacheEntry<T> = {
      data: result.data,
      meta: result.meta,
      timestamp: Date.now(),
      ttlMs,
    };

    // Store in L1 Memory
    this.memoryCache.set(path, entry);

    // Store in L2 sessionStorage
    try {
      if (typeof window !== 'undefined' && window.sessionStorage) {
        window.sessionStorage.setItem(`${STORAGE_PREFIX}${path}`, JSON.stringify(entry));
      }
    } catch (e) {
      // Quota exceeded: clear older darpan cache entries
      this.evictOldSessionEntries();
    }
  }

  public invalidate(path: string): void {
    this.memoryCache.delete(path);
    try {
      if (typeof window !== 'undefined' && window.sessionStorage) {
        window.sessionStorage.removeItem(`${STORAGE_PREFIX}${path}`);
      }
    } catch {}
  }

  public clear(): void {
    this.memoryCache.clear();
    try {
      if (typeof window !== 'undefined' && window.sessionStorage) {
        const keysToRemove: string[] = [];
        for (let i = 0; i < window.sessionStorage.length; i++) {
          const k = window.sessionStorage.key(i);
          if (k && k.startsWith(STORAGE_PREFIX)) {
            keysToRemove.push(k);
          }
        }
        keysToRemove.forEach((k) => window.sessionStorage.removeItem(k));
      }
    } catch {}
  }

  private evictOldSessionEntries(): void {
    try {
      if (typeof window === 'undefined' || !window.sessionStorage) return;
      const keys: string[] = [];
      for (let i = 0; i < window.sessionStorage.length; i++) {
        const k = window.sessionStorage.key(i);
        if (k && k.startsWith(STORAGE_PREFIX)) {
          keys.push(k);
        }
      }
      // Remove half of oldest session cache entries
      keys.slice(0, Math.ceil(keys.length / 2)).forEach((k) => {
        window.sessionStorage.removeItem(k);
      });
    } catch {}
  }
}

export const sessionCache = new SessionCacheManager();
