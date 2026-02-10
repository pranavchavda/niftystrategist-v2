import { useState, useEffect, useCallback, useRef } from 'react';
import type {
  PortfolioSummary,
  Position,
  WatchlistItem,
  MarketIndex,
  DailyScorecard,
} from '../components/cockpit/mock-data';

interface MarketStatus {
  status: string;
  reason?: string;
  closes_in?: string;
  next_open?: string;
  next_open_in?: string;
  next_event?: string;
  next_event_in?: string;
  current_time_ist?: string;
}

export interface CockpitData {
  portfolio: PortfolioSummary | null;
  positions: Position[];
  holdings: Position[];
  watchlists: Record<string, WatchlistItem[]>;
  indices: MarketIndex[];
  scorecard: DailyScorecard | null;
  marketStatus: MarketStatus | null;
  isLoading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  refresh: () => void;
}

const API_BASE = '/api/cockpit';

async function fetchJSON(url: string, authToken: string) {
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${authToken}` },
  });
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  return res.json();
}

export function useCockpitData(authToken: string, autoRefresh: boolean): CockpitData {
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [holdings, setHoldings] = useState<Position[]>([]);
  const [watchlists, setWatchlists] = useState<Record<string, WatchlistItem[]>>({});
  const [indices, setIndices] = useState<MarketIndex[]>([]);
  const [scorecard, setScorecard] = useState<DailyScorecard | null>(null);
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    if (!authToken) return;
    setIsLoading(true);
    setError(null);

    // Fetch all endpoints in parallel — each is independent
    const results = await Promise.allSettled([
      fetch(`${API_BASE}/market-status`).then(r => r.ok ? r.json() : null),
      fetchJSON(`${API_BASE}/portfolio`, authToken),
      fetchJSON(`${API_BASE}/positions`, authToken),
      fetchJSON(`${API_BASE}/indices`, authToken),
      fetchJSON(`${API_BASE}/watchlist`, authToken),
      fetchJSON(`${API_BASE}/scorecard`, authToken),
    ]);

    // Market status (no auth)
    if (results[0].status === 'fulfilled' && results[0].value) {
      setMarketStatus(results[0].value);
    }

    // Portfolio
    if (results[1].status === 'fulfilled') {
      setPortfolio(results[1].value);
    } else {
      console.warn('Portfolio fetch failed:', results[1]);
    }

    // Positions
    if (results[2].status === 'fulfilled') {
      setPositions(results[2].value.positions || []);
      setHoldings(results[2].value.holdings || []);
    }

    // Indices
    if (results[3].status === 'fulfilled') {
      setIndices(results[3].value || []);
    }

    // Watchlist
    if (results[4].status === 'fulfilled') {
      setWatchlists(results[4].value || {});
    }

    // Scorecard
    if (results[5].status === 'fulfilled') {
      setScorecard(results[5].value);
    }

    // Check if all failed
    const allFailed = results.every(r => r.status === 'rejected');
    if (allFailed) {
      setError('Failed to load cockpit data. Check your connection.');
    }

    setIsLoading(false);
    setLastUpdated(new Date());
  }, [authToken]);

  // Initial fetch
  useEffect(() => {
    refresh();
  }, [refresh]);

  // Auto-refresh interval
  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (autoRefresh && authToken) {
      intervalRef.current = setInterval(refresh, 30_000);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [autoRefresh, authToken, refresh]);

  return {
    portfolio,
    positions,
    holdings,
    watchlists,
    indices,
    scorecard,
    marketStatus,
    isLoading,
    error,
    lastUpdated,
    refresh,
  };
}
