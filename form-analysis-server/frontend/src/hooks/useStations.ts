/**
 * useStations — fetches the list of stations for the current tenant.
 */

import { useEffect, useState } from 'react';
import type { StationInfo } from '../types/api';
import { fetchStations } from '../services/stationApi';

let cached: StationInfo[] | null = null;

export function useStations() {
  const [stations, setStations] = useState<StationInfo[]>(cached ?? []);
  const [loading, setLoading] = useState(!cached);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (cached) {
      setStations(cached);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);

    fetchStations()
      .then((data) => {
        if (cancelled) return;
        cached = data;
        setStations(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message ?? 'Failed to fetch stations');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { stations, loading, error };
}
