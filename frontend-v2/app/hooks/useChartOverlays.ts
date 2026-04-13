import { useState, useEffect, useRef } from 'react';

export interface OverlayLinePoint {
  time: string | number;
  value: number;
}

export interface OverlayMarker {
  time: string | number;
  type: 'buy' | 'sell';
  text?: string;
}

export interface ChartOverlays {
  lines: Record<string, OverlayLinePoint[]>;
  markers: OverlayMarker[];
}

export function useChartOverlays(
  authToken: string,
  symbol: string,
  days: number,
  interval: string,
  indicators: string[],
  utbotPeriod: number = 10,
  utbotSensitivity: number = 1.0,
): { overlays: ChartOverlays; isLoading: boolean; error: string | null } {
  const [overlays, setOverlays] = useState<ChartOverlays>({ lines: {}, markers: [] });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const indicatorsKey = indicators.join(',');

  useEffect(() => {
    if (!authToken || !symbol || indicators.length === 0) {
      setOverlays({ lines: {}, markers: [] });
      return;
    }

    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setError(null);

    const qs = new URLSearchParams({
      days: String(days),
      interval,
      indicators: indicatorsKey,
      utbot_period: String(utbotPeriod),
      utbot_sensitivity: String(utbotSensitivity),
    });

    fetch(`/api/cockpit/chart/${encodeURIComponent(symbol)}/overlays?${qs}`, {
      headers: { Authorization: `Bearer ${authToken}` },
      signal: controller.signal,
    })
      .then((res) => {
        if (!res.ok) throw new Error(`Overlay fetch failed: ${res.status}`);
        return res.json();
      })
      .then((json) => {
        if (!controller.signal.aborted) {
          setOverlays(json);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        console.warn(`Overlay error for ${symbol}:`, err);
        setOverlays({ lines: {}, markers: [] });
        setError(err.message);
        setIsLoading(false);
      });

    return () => controller.abort();
  }, [authToken, symbol, days, interval, indicatorsKey, utbotPeriod, utbotSensitivity]);

  return { overlays, isLoading, error };
}
