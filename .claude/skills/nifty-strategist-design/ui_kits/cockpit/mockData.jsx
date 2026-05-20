// Mock data for the Cockpit kit. Mirrors the shape used by
// frontend-v2/app/components/cockpit/mock-data.ts.

const mockPortfolio = {
  totalValue: 1043250,
  investedValue: 287500,
  availableCash: 755750,
  dayPnl: 4320,
  dayPnlPct: 0.42,
  totalPnl: 43250,
  totalPnlPct: 4.33,
  marginUsed: 28750,
};

const mockPositions = [
  { symbol: 'RELIANCE', company: 'Reliance Industries', qty: 10, avgPrice: 2780, ltp: 2847.50, pnl: 675, pnlPct: 2.43, dayChangePct: 1.23, holdDays: 3, stopLoss: 2720, target: 2950 },
  { symbol: 'TCS',      company: 'Tata Consultancy Services', qty: 15, avgPrice: 4150, ltp: 4220, pnl: 1050, pnlPct: 1.69, dayChangePct: -0.35, holdDays: 5, stopLoss: 4080, target: 4350 },
  { symbol: 'INFY',     company: 'Infosys', qty: 20, avgPrice: 1780, ltp: 1755, pnl: -500, pnlPct: -1.40, dayChangePct: -1.24, holdDays: 7, stopLoss: 1730, target: 1850 },
  { symbol: 'HDFCBANK', company: 'HDFC Bank', qty: 12, avgPrice: 1685, ltp: 1712, pnl: 324, pnlPct: 1.60, dayChangePct: 0.50, holdDays: 2, stopLoss: 1660, target: 1780 },
  { symbol: 'SBIN',     company: 'State Bank of India', qty: 25, avgPrice: 768, ltp: 782, pnl: 350, pnlPct: 1.82, dayChangePct: 1.56, holdDays: 1, stopLoss: 755, target: 810 },
];

const mockHoldings = [
  { symbol: 'BAJFINANCE', company: 'Bajaj Finance', qty: 5, avgPrice: 7200, ltp: 7485, pnl: 1425, pnlPct: 3.96, dayChangePct: 0.60, holdDays: 28 },
  { symbol: 'WIPRO',      company: 'Wipro', qty: 30, avgPrice: 485, ltp: 512, pnl: 810, pnlPct: 5.57, dayChangePct: -0.58, holdDays: 45 },
];

const mockWatchlists = {
  Momentum: [
    { symbol: 'TATAMOTORS', company: 'Tata Motors',          ltp: 952,   changePct: 1.98,  spark: [920, 925, 935, 940, 928, 945, 952], alert: true },
    { symbol: 'M&M',        company: 'Mahindra & Mahindra',  ltp: 2680,  changePct: -0.45, spark: [2710, 2695, 2700, 2685, 2690, 2675, 2680] },
    { symbol: 'ADANIENT',   company: 'Adani Enterprises',    ltp: 3150,  changePct: 2.77,  spark: [3020, 3050, 3080, 3100, 3120, 3135, 3150] },
    { symbol: 'JSWSTEEL',   company: 'JSW Steel',            ltp: 892,   changePct: 0.85,  spark: [878, 882, 888, 885, 890, 888, 892] },
    { symbol: 'SUNPHARMA',  company: 'Sun Pharma',           ltp: 1724,  changePct: -0.46, spark: [1740, 1735, 1730, 1728, 1725, 1722, 1724] },
    { symbol: 'BHARTIARTL', company: 'Bharti Airtel',        ltp: 1582,  changePct: 1.54,  spark: [1550, 1555, 1560, 1568, 1572, 1578, 1582] },
    { symbol: 'MARUTI',     company: 'Maruti Suzuki',        ltp: 12450, changePct: 1.47,  spark: [12200, 12250, 12300, 12350, 12380, 12420, 12450] },
  ],
  Swing: [
    { symbol: 'ICICIBANK',  company: 'ICICI Bank',           ltp: 1245,  changePct: 0.40,  spark: [1230, 1235, 1238, 1240, 1242, 1243, 1245], alert: true },
    { symbol: 'KOTAKBANK',  company: 'Kotak Mahindra Bank',  ltp: 1890,  changePct: -0.79, spark: [1910, 1905, 1900, 1895, 1892, 1888, 1890] },
    { symbol: 'AXISBANK',   company: 'Axis Bank',            ltp: 1156,  changePct: 0.70,  spark: [1140, 1142, 1148, 1150, 1152, 1154, 1156] },
    { symbol: 'ITC',        company: 'ITC',                  ltp: 468,   changePct: 0.54,  spark: [462, 463, 465, 466, 467, 467, 468] },
    { symbol: 'HINDUNILVR', company: 'Hindustan Unilever',   ltp: 2580,  changePct: -0.69, spark: [2610, 2605, 2600, 2595, 2588, 2582, 2580] },
  ],
};

const mockIndices = [
  { name: 'NIFTY 50',    value: 23456.70, change: 187.45,  changePct: 0.81 },
  { name: 'BANK NIFTY',  value: 49823.15, change: -124.30, changePct: -0.25 },
  { name: 'INDIA VIX',   value: 13.42,    change: -0.58,   changePct: -4.14 },
];

const mockScorecard = {
  trades: 5, won: 3, lost: 1, winRate: 75,
  avgWinner: 480.83, avgLoser: 500, biggestWin: 675, biggestLoss: 500,
  profitFactor: 2.89, streak: 3, streakType: 'win', netPnl: 1442.49,
};

const fmtINR = (n) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);
const fmtINRdec = (n) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(n);
const fmtPct = (n) => `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
const fmtMoneySigned = (n) => `${n >= 0 ? '+' : '−'}${new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(Math.abs(n))}`;

Object.assign(window, {
  mockPortfolio, mockPositions, mockHoldings, mockWatchlists, mockIndices, mockScorecard,
  fmtINR, fmtINRdec, fmtPct, fmtMoneySigned,
});
