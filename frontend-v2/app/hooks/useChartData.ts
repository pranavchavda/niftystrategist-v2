import { useState, useEffect, useRef } from 'react';

interface OHLCV {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

export function useChartData(
  authToken: string,
  symbol: string,
  days: number = 90,
): { data: OHLCV[]; isLoading: boolean; error: string | null } {
  const [data, setData] = useState<OHLCV[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!authToken || !symbol) return;

    // Cancel previous in-flight request
    if (abortRef.current) {
      abortRef.current.abort();
    }

    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setError(null);

    fetch(`/api/cockpit/chart/${encodeURIComponent(symbol)}?days=${days}`, {
      headers: { Authorization: `Bearer ${authToken}` },
      signal: controller.signal,
    })
      .then((res) => {
        if (!res.ok) throw new Error(`Chart fetch failed: ${res.status}`);
        return res.json();
      })
      .then((json) => {
        if (!controller.signal.aborted) {
          setData(json);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        console.warn(`Chart error for ${symbol}:`, err);
        setData([]);
        setError(err.message);
        setIsLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [authToken, symbol, days]);

  return { data, isLoading, error };
}
