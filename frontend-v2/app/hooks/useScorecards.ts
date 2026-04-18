import { useState, useEffect, useCallback, useRef } from 'react';

export interface DailyScorecardRow {
  date: string;
  trades: number;
  wins: number;
  losses: number;
  winRate: number;
  netPnl: number;
  grossProfit: number;
  grossLoss: number;
  biggestWin: number;
  biggestLoss: number;
  profitFactor: number;
  totalBuyValue: number;
  totalSellValue: number;
}

export interface ScorecardsData {
  days: number;
  start: string;
  end: string;
  scorecards: DailyScorecardRow[];
}

export function useScorecards(authToken: string, days = 30) {
  const [data, setData] = useState<ScorecardsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    if (!authToken) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/cockpit/scorecards?days=${days}`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setIsLoading(false);
    }
  }, [authToken, days]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (authToken) {
      // Report is T+1 — refresh every 15 min is plenty
      intervalRef.current = setInterval(refresh, 15 * 60_000);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [authToken, refresh]);

  return { data, isLoading, error, refresh };
}
