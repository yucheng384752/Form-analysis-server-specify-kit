/**
 * useStationSchema — fetches and caches a station's active schema.
 *
 * Usage:
 *   const { schema, loading, error } = useStationSchema('P2');
 */

import { useEffect, useState } from 'react';
import type { StationSchema } from '../types/api';
import { fetchStationSchema } from '../services/stationApi';

// Simple in-memory cache keyed by station code.
const cache = new Map<string, StationSchema>();

export function useStationSchema(stationCode: string | undefined) {
  const [schema, setSchema] = useState<StationSchema | null>(
    stationCode ? cache.get(stationCode) ?? null : null
  );
  const [loading, setLoading] = useState(!schema && !!stationCode);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!stationCode) {
      setSchema(null);
      setLoading(false);
      return;
    }

    const cached = cache.get(stationCode);
    if (cached) {
      setSchema(cached);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchStationSchema(stationCode)
      .then((data) => {
        if (cancelled) return;
        cache.set(stationCode, data);
        setSchema(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message ?? 'Failed to fetch schema');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [stationCode]);

  return { schema, loading, error };
}
