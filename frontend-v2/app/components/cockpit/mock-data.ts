/**
 * Mock data for the Cockpit Dashboard (Phase 1)
 * Will be replaced with real API calls in Phase 2+
 */

export interface Position {
  symbol: string;
  company: string;
  qty: number;
  avgPrice: number;
  ltp: number;
  pnl: number;
  pnlPct: number;
  dayChange: number;
  dayChangePct: number;
  holdDays: number;
  stopLoss?: number;
  target?: number;
}

export interface WatchlistItem {
  symbol: string;
  company: string;
  ltp: number;
  change: number;
  changePct: number;
  volume: number;
  sparkline: number[];
  alertAbove?: number;
  alertBelow?: number;
}

export interface PortfolioSummary {
  totalValue: number;
  investedValue: number;
  availableCash: number;
  dayPnl: number;
  dayPnlPct: number;
  totalPnl: number;
  totalPnlPct: number;
  marginUsed: number;
  paperTrading: boolean;
}

export interface TradeRecord {
  id: string;
  symbol: string;
  direction: 'BUY' | 'SELL';
  qty: number;
  price: number;
  time: string;
  pnl?: number;
  status: 'completed' | 'pending' | 'cancelled';
}

export interface MarketIndex {
  name: string;
  value: number;
  change: number;
  changePct: number;
}

export interface DailyScorecard {
  trades: number;
  won: number;
  lost: number;
  winRate: number;
  avgWinner: number;
  avgLoser: number;
  biggestWin: number;
  biggestLoss: number;
  profitFactor: number;
  streak: number;
  streakType: 'win' | 'loss' | 'neutral';
}

// --- Mock Data ---

export const mockPortfolio: PortfolioSummary = {
  totalValue: 1043250,
  investedValue: 287500,
  availableCash: 755750,
  dayPnl: 4320,
  dayPnlPct: 0.42,
  totalPnl: 43250,
  totalPnlPct: 4.33,
  marginUsed: 28.75,
  paperTrading: true,
};

export const mockPositions: Position[] = [
  {
    symbol: 'RELIANCE',
    company: 'Reliance Industries',
    qty: 10,
    avgPrice: 2780,
    ltp: 2847.50,
    pnl: 675,
    pnlPct: 2.43,
    dayChange: 34.50,
    dayChangePct: 1.23,
    holdDays: 3,
    stopLoss: 2720,
    target: 2950,
  },
  {
    symbol: 'TCS',
    company: 'Tata Consultancy Services',
    qty: 15,
    avgPrice: 4150,
    ltp: 4220,
    pnl: 1050,
    pnlPct: 1.69,
    dayChange: -15,
    dayChangePct: -0.35,
    holdDays: 5,
    stopLoss: 4080,
    target: 4350,
  },
  {
    symbol: 'INFY',
    company: 'Infosys',
    qty: 20,
    avgPrice: 1780,
    ltp: 1755,
    pnl: -500,
    pnlPct: -1.40,
    dayChange: -22,
    dayChangePct: -1.24,
    holdDays: 7,
    stopLoss: 1730,
    target: 1850,
  },
  {
    symbol: 'HDFCBANK',
    company: 'HDFC Bank',
    qty: 12,
    avgPrice: 1685,
    ltp: 1712,
    pnl: 324,
    pnlPct: 1.60,
    dayChange: 8.50,
    dayChangePct: 0.50,
    holdDays: 2,
    stopLoss: 1660,
    target: 1780,
  },
  {
    symbol: 'SBIN',
    company: 'State Bank of India',
    qty: 25,
    avgPrice: 768,
    ltp: 782,
    pnl: 350,
    pnlPct: 1.82,
    dayChange: 12,
    dayChangePct: 1.56,
    holdDays: 1,
    stopLoss: 755,
    target: 810,
  },
];

export const mockHoldings: Position[] = [
  {
    symbol: 'BAJFINANCE',
    company: 'Bajaj Finance',
    qty: 5,
    avgPrice: 7200,
    ltp: 7485,
    pnl: 1425,
    pnlPct: 3.96,
    dayChange: 45,
    dayChangePct: 0.60,
    holdDays: 28,
  },
  {
    symbol: 'WIPRO',
    company: 'Wipro',
    qty: 30,
    avgPrice: 485,
    ltp: 512,
    pnl: 810,
    pnlPct: 5.57,
    dayChange: -3,
    dayChangePct: -0.58,
    holdDays: 45,
  },
];

export const mockWatchlists: Record<string, WatchlistItem[]> = {
  Momentum: [
    { symbol: 'TATAMOTORS', company: 'Tata Motors', ltp: 952, change: 18.5, changePct: 1.98, volume: 12500000, sparkline: [920, 925, 935, 940, 928, 945, 952], alertAbove: 970 },
    { symbol: 'M&M', company: 'Mahindra & Mahindra', ltp: 2680, change: -12, changePct: -0.45, volume: 3200000, sparkline: [2710, 2695, 2700, 2685, 2690, 2675, 2680] },
    { symbol: 'ADANIENT', company: 'Adani Enterprises', ltp: 3150, change: 85, changePct: 2.77, volume: 8900000, sparkline: [3020, 3050, 3080, 3100, 3120, 3135, 3150] },
    { symbol: 'JSWSTEEL', company: 'JSW Steel', ltp: 892, change: 7.5, changePct: 0.85, volume: 5600000, sparkline: [878, 882, 888, 885, 890, 888, 892] },
    { symbol: 'SUNPHARMA', company: 'Sun Pharma', ltp: 1724, change: -8, changePct: -0.46, volume: 2100000, sparkline: [1740, 1735, 1730, 1728, 1725, 1722, 1724] },
    { symbol: 'BHARTIARTL', company: 'Bharti Airtel', ltp: 1582, change: 24, changePct: 1.54, volume: 4300000, sparkline: [1550, 1555, 1560, 1568, 1572, 1578, 1582] },
    { symbol: 'LTIM', company: 'LTIMindtree', ltp: 5420, change: -35, changePct: -0.64, volume: 1800000, sparkline: [5480, 5465, 5450, 5440, 5435, 5425, 5420] },
    { symbol: 'MARUTI', company: 'Maruti Suzuki', ltp: 12450, change: 180, changePct: 1.47, volume: 980000, sparkline: [12200, 12250, 12300, 12350, 12380, 12420, 12450] },
  ],
  Swing: [
    { symbol: 'ICICIBANK', company: 'ICICI Bank', ltp: 1245, change: 5, changePct: 0.40, volume: 7800000, sparkline: [1230, 1235, 1238, 1240, 1242, 1243, 1245], alertBelow: 1220 },
    { symbol: 'KOTAKBANK', company: 'Kotak Mahindra Bank', ltp: 1890, change: -15, changePct: -0.79, volume: 2400000, sparkline: [1910, 1905, 1900, 1895, 1892, 1888, 1890] },
    { symbol: 'AXISBANK', company: 'Axis Bank', ltp: 1156, change: 8, changePct: 0.70, volume: 6100000, sparkline: [1140, 1142, 1148, 1150, 1152, 1154, 1156] },
    { symbol: 'ITC', company: 'ITC', ltp: 468, change: 2.5, changePct: 0.54, volume: 15000000, sparkline: [462, 463, 465, 466, 467, 467, 468] },
    { symbol: 'HINDUNILVR', company: 'Hindustan Unilever', ltp: 2580, change: -18, changePct: -0.69, volume: 1900000, sparkline: [2610, 2605, 2600, 2595, 2588, 2582, 2580] },
  ],
};

export const mockIndices: MarketIndex[] = [
  { name: 'NIFTY 50', value: 23456.70, change: 187.45, changePct: 0.81 },
  { name: 'BANK NIFTY', value: 49823.15, change: -124.30, changePct: -0.25 },
  { name: 'INDIA VIX', value: 13.42, change: -0.58, changePct: -4.14 },
];

export const mockTodayTrades: TradeRecord[] = [
  { id: 't1', symbol: 'SBIN', direction: 'BUY', qty: 25, price: 770, time: '09:32', status: 'completed' },
  { id: 't2', symbol: 'RELIANCE', direction: 'BUY', qty: 5, price: 2815, time: '10:15', pnl: 162.50, status: 'completed' },
  { id: 't3', symbol: 'HDFCBANK', direction: 'BUY', qty: 12, price: 1685, time: '11:02', status: 'completed' },
  { id: 't4', symbol: 'TATAMOTORS', direction: 'SELL', qty: 10, price: 945, time: '13:45', pnl: 280, status: 'completed' },
  { id: 't5', symbol: 'INFY', direction: 'BUY', qty: 10, price: 1762, time: '14:20', status: 'completed' },
];

export const mockScorecard: DailyScorecard = {
  trades: 5,
  won: 3,
  lost: 1,
  winRate: 75,
  avgWinner: 480.83,
  avgLoser: 500,
  biggestWin: 675,
  biggestLoss: 500,
  profitFactor: 2.89,
  streak: 3,
  streakType: 'win',
};

export const mockChatMessages = [
  {
    id: '1',
    role: 'assistant' as const,
    content: `## Good Morning, Pranav! Trading Day - Feb 7, 2026\n\n### Your Positions\n- **RELIANCE** +2.43% (3 days) — approaching target at 2,950\n- **INFY** -1.40% (7 days) — watch stop loss at 1,730\n- **TCS** +1.69% — steady, holding well\n\n### Watchlist Alerts\n- TATAMOTORS nearing alert at 970 (currently 952)\n\n### Today's Focus\n1. Monitor INFY — close to stop loss\n2. RELIANCE approaching target zone`,
    timestamp: '09:00',
  },
  {
    id: '2',
    role: 'user' as const,
    content: 'Should I exit INFY? It\'s been dropping for a week.',
    timestamp: '10:30',
  },
  {
    id: '3',
    role: 'assistant' as const,
    content: `INFY is at 1,755 — just 25 points (1.4%) above your stop loss at 1,730.\n\n**Technical picture:**\n- RSI: 38 (approaching oversold)\n- Below 20-day SMA (bearish)\n- Support at 1,730-1,740 zone\n\n**My take:** The stop loss is doing its job. Rather than panic-exit, let it play out. If it hits 1,730, the stop triggers automatically. If it bounces from here, you catch the reversal.\n\n**But** — your hold is already 7 days, longer than your typical 2-5 day swing. Consider tightening your stop to 1,745 to protect more capital.`,
    timestamp: '10:31',
  },
];

// Generate OHLCV data for chart
export function generateMockOHLCV(days: number = 90): { time: string; open: number; high: number; low: number; close: number; }[] {
  const data = [];
  let price = 2700;
  const now = new Date();

  for (let i = days; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);

    // Skip weekends
    if (date.getDay() === 0 || date.getDay() === 6) continue;

    const volatility = 0.02;
    const change = (Math.random() - 0.48) * volatility * price;
    const open = price;
    const close = price + change;
    const high = Math.max(open, close) + Math.random() * volatility * price * 0.5;
    const low = Math.min(open, close) - Math.random() * volatility * price * 0.5;

    data.push({
      time: date.toISOString().split('T')[0],
      open: Math.round(open * 100) / 100,
      high: Math.round(high * 100) / 100,
      low: Math.round(low * 100) / 100,
      close: Math.round(close * 100) / 100,
    });

    price = close;
  }

  return data;
}
