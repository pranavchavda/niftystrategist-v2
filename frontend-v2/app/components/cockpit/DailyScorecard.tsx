import { useState } from 'react';
import {
  ChevronDownIcon,
  TrophyIcon,
  FlameIcon,
  TargetIcon,
  ZapIcon,
} from 'lucide-react';
import type { DailyScorecard as ScorecardType } from './mock-data';

const fmt = (n: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);

interface DailyScorecardProps {
  scorecard: ScorecardType;
}

function StarRating({ value, onChange, label }: { value: number; onChange: (v: number) => void; label: string }) {
  const [hover, setHover] = useState(0);

  return (
    <div className="flex items-center justify-between">
      <span className="text-[11px] text-zinc-600 dark:text-zinc-400">{label}</span>
      <div className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            onMouseEnter={() => setHover(star)}
            onMouseLeave={() => setHover(0)}
            onClick={() => onChange(star)}
            className="transition-colors"
          >
            <svg
              className={`h-3.5 w-3.5 ${
                star <= (hover || value)
                  ? star <= 2
                    ? 'text-red-400'
                    : star <= 3
                      ? 'text-amber-400'
                      : 'text-green-400'
                  : 'text-zinc-300 dark:text-zinc-600'
              }`}
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
          </button>
        ))}
      </div>
    </div>
  );
}

export default function DailyScorecard({ scorecard }: DailyScorecardProps) {
  const [expanded, setExpanded] = useState(false);
  const [ratings, setRatings] = useState({
    planAdherence: 0,
    riskManagement: 0,
    emotionalDiscipline: 0,
    entryQuality: 0,
    exitQuality: 0,
  });

  const updateRating = (key: keyof typeof ratings, value: number) => {
    setRatings((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="border-t border-zinc-200/50 dark:border-zinc-800/50">
      {/* Collapsed Summary Bar */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-zinc-50/50 dark:hover:bg-zinc-800/30 transition-colors"
      >
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5">
            <TargetIcon className="h-3.5 w-3.5 text-amber-500" />
            <span className="font-semibold text-zinc-700 dark:text-zinc-300">Daily Scorecard</span>
          </div>

          <div className="flex items-center gap-3 text-zinc-500">
            <span>
              <span className="font-bold text-zinc-700 dark:text-zinc-300 tabular-nums">{scorecard.trades}</span> trades
            </span>
            <span className="text-zinc-300 dark:text-zinc-700">|</span>
            <span>
              Win Rate: <span className={`font-bold tabular-nums ${scorecard.winRate >= 50 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>{scorecard.winRate}%</span>
            </span>
            <span className="hidden lg:inline text-zinc-300 dark:text-zinc-700">|</span>
            <span className="hidden lg:inline">
              PF: <span className={`font-bold tabular-nums ${scorecard.profitFactor >= 1.5 ? 'text-green-600 dark:text-green-400' : scorecard.profitFactor >= 1 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400'}`}>
                {scorecard.profitFactor.toFixed(2)}
              </span>
            </span>
            <span className="hidden xl:inline text-zinc-300 dark:text-zinc-700">|</span>
            <span className="hidden xl:inline-flex items-center gap-1">
              <FlameIcon className={`h-3 w-3 ${scorecard.streakType === 'win' ? 'text-green-500' : scorecard.streakType === 'loss' ? 'text-red-500' : 'text-zinc-400'}`} />
              <span className={`font-bold tabular-nums ${scorecard.streakType === 'win' ? 'text-green-600 dark:text-green-400' : scorecard.streakType === 'loss' ? 'text-red-600 dark:text-red-400' : 'text-zinc-500'}`}>
                {scorecard.streak} day {scorecard.streakType} streak
              </span>
            </span>
          </div>
        </div>

        <ChevronDownIcon className={`h-4 w-4 text-zinc-400 transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>

      {/* Expanded Detail */}
      {expanded && (
        <div className="px-3 pb-3 animate-slide-in-bottom">
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {/* Trade Stats */}
            <div className="space-y-2">
              <h4 className="text-[10px] font-bold text-zinc-400 dark:text-zinc-500 tracking-[0.15em] uppercase">Trade Stats</h4>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-zinc-50 dark:bg-zinc-800/50 rounded-lg p-2">
                  <div className="text-[10px] text-zinc-500">Won / Lost</div>
                  <div className="text-sm font-bold">
                    <span className="text-green-600 dark:text-green-400 tabular-nums">{scorecard.won}</span>
                    <span className="text-zinc-400 mx-1">/</span>
                    <span className="text-red-600 dark:text-red-400 tabular-nums">{scorecard.lost}</span>
                  </div>
                </div>
                <div className="bg-zinc-50 dark:bg-zinc-800/50 rounded-lg p-2">
                  <div className="text-[10px] text-zinc-500">Avg Win / Loss</div>
                  <div className="text-[11px] font-bold">
                    <span className="text-green-600 dark:text-green-400 tabular-nums">{fmt(scorecard.avgWinner)}</span>
                    <span className="text-zinc-400 mx-1">/</span>
                    <span className="text-red-600 dark:text-red-400 tabular-nums">{fmt(scorecard.avgLoser)}</span>
                  </div>
                </div>
                <div className="bg-zinc-50 dark:bg-zinc-800/50 rounded-lg p-2">
                  <div className="text-[10px] text-zinc-500">Biggest Win</div>
                  <div className="text-sm font-bold text-green-600 dark:text-green-400 tabular-nums">
                    <TrophyIcon className="h-3 w-3 inline mr-1 text-amber-500" />
                    {fmt(scorecard.biggestWin)}
                  </div>
                </div>
                <div className="bg-zinc-50 dark:bg-zinc-800/50 rounded-lg p-2">
                  <div className="text-[10px] text-zinc-500">Biggest Loss</div>
                  <div className="text-sm font-bold text-red-600 dark:text-red-400 tabular-nums">
                    {fmt(scorecard.biggestLoss)}
                  </div>
                </div>
              </div>
            </div>

            {/* Process Ratings */}
            <div className="space-y-2">
              <h4 className="text-[10px] font-bold text-zinc-400 dark:text-zinc-500 tracking-[0.15em] uppercase">Process Check</h4>
              <div className="space-y-1.5 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg p-2.5">
                <StarRating label="Plan Adherence" value={ratings.planAdherence} onChange={(v) => updateRating('planAdherence', v)} />
                <StarRating label="Risk Management" value={ratings.riskManagement} onChange={(v) => updateRating('riskManagement', v)} />
                <StarRating label="Emotional Discipline" value={ratings.emotionalDiscipline} onChange={(v) => updateRating('emotionalDiscipline', v)} />
                <StarRating label="Entry Quality" value={ratings.entryQuality} onChange={(v) => updateRating('entryQuality', v)} />
                <StarRating label="Exit Quality" value={ratings.exitQuality} onChange={(v) => updateRating('exitQuality', v)} />
              </div>
            </div>

            {/* Reflection */}
            <div className="space-y-2">
              <h4 className="text-[10px] font-bold text-zinc-400 dark:text-zinc-500 tracking-[0.15em] uppercase">Reflection</h4>
              <textarea
                placeholder="What did I learn today?"
                className="w-full h-20 text-xs bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200/50 dark:border-zinc-700/50 rounded-lg p-2.5 text-zinc-700 dark:text-zinc-300 placeholder:text-zinc-400 focus:outline-none focus:ring-1 focus:ring-amber-500/50 resize-none"
              />
              <div className="flex gap-1.5">
                <button className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 rounded-md hover:bg-amber-100 dark:hover:bg-amber-900/30 transition-colors">
                  <ZapIcon className="h-2.5 w-2.5" />
                  AI Suggest
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
