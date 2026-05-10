import {
  WalletIcon,
  TrendingUpIcon,
  TrendingDownIcon,
  PiggyBankIcon,
  CoinsIcon,
  GaugeIcon,
} from 'lucide-react';
import type { PortfolioSummary, FundsData } from './mock-data';

const fmtINR = (n: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);

const pct = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;

interface KPIProps {
  label: string;
  value: string;
  sub?: string;
  icon: React.ReactNode;
  tone?: 'neutral' | 'positive' | 'negative';
}

function KPI({ label, value, sub, icon, tone = 'neutral' }: KPIProps) {
  const valueColor =
    tone === 'positive'
      ? 'text-green-600 dark:text-green-400'
      : tone === 'negative'
        ? 'text-red-600 dark:text-red-400'
        : 'text-zinc-900 dark:text-zinc-100';
  const subColor =
    tone === 'positive'
      ? 'text-green-500/80 dark:text-green-400/70'
      : tone === 'negative'
        ? 'text-red-500/80 dark:text-red-400/70'
        : 'text-zinc-500 dark:text-zinc-400';

  return (
    <div className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg bg-white/60 dark:bg-zinc-900/60 border border-zinc-200/60 dark:border-zinc-800/60 backdrop-blur-sm min-w-0">
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400">
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-[10px] font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400 truncate">{label}</div>
        <div className={`text-sm font-bold tabular-nums truncate ${valueColor}`}>{value}</div>
        {sub && <div className={`text-[10px] tabular-nums truncate ${subColor}`}>{sub}</div>}
      </div>
    </div>
  );
}

interface PortfolioOverviewProps {
  portfolio: PortfolioSummary | null;
  funds: FundsData | null;
}

export default function PortfolioOverview({ portfolio, funds }: PortfolioOverviewProps) {
  if (!portfolio) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-2 px-3 py-3 border-b border-zinc-200/60 dark:border-zinc-800/60">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-14 rounded-lg bg-zinc-100 dark:bg-zinc-800/40 animate-pulse" />
        ))}
      </div>
    );
  }

  const availableMargin = funds?.equity?.available_margin ?? portfolio.availableCash;
  const usedMargin = funds?.equity?.used_margin ?? portfolio.marginUsed;

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-2 px-3 py-3 border-b border-zinc-200/60 dark:border-zinc-800/60">
      <KPI
        label="Total Value"
        value={fmtINR(portfolio.totalValue)}
        icon={<WalletIcon className="h-4 w-4" />}
      />
      <KPI
        label="Day P&L"
        value={fmtINR(portfolio.dayPnl)}
        sub={pct(portfolio.dayPnlPct)}
        icon={portfolio.dayPnl >= 0 ? <TrendingUpIcon className="h-4 w-4" /> : <TrendingDownIcon className="h-4 w-4" />}
        tone={portfolio.dayPnl >= 0 ? 'positive' : 'negative'}
      />
      <KPI
        label="Total P&L"
        value={fmtINR(portfolio.totalPnl)}
        sub={pct(portfolio.totalPnlPct)}
        icon={portfolio.totalPnl >= 0 ? <TrendingUpIcon className="h-4 w-4" /> : <TrendingDownIcon className="h-4 w-4" />}
        tone={portfolio.totalPnl >= 0 ? 'positive' : 'negative'}
      />
      <KPI
        label="Invested"
        value={fmtINR(portfolio.investedValue)}
        icon={<PiggyBankIcon className="h-4 w-4" />}
      />
      <KPI
        label="Available"
        value={fmtINR(availableMargin)}
        icon={<CoinsIcon className="h-4 w-4" />}
      />
      <KPI
        label="Margin Used"
        value={fmtINR(usedMargin)}
        icon={<GaugeIcon className="h-4 w-4" />}
      />
    </div>
  );
}
