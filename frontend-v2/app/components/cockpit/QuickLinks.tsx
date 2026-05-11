import { Link } from 'react-router';
import {
  CandlestickChartIcon,
  ShieldIcon,
  BookOpenIcon,
  TargetIcon,
  ZapIcon,
  StickyNoteIcon,
} from 'lucide-react';

interface QuickLinkProps {
  to: string;
  label: string;
  icon: React.ReactNode;
}

function QuickLink({ to, label, icon }: QuickLinkProps) {
  return (
    <Link
      to={to}
      className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/50 dark:bg-zinc-900/50 border border-zinc-200/60 dark:border-zinc-800/60 hover:border-amber-400/60 dark:hover:border-amber-500/40 hover:bg-amber-50/40 dark:hover:bg-amber-950/20 transition-colors group"
    >
      <span className="text-zinc-400 group-hover:text-amber-500 transition-colors">{icon}</span>
      <span className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 group-hover:text-amber-700 dark:group-hover:text-amber-400 transition-colors">
        {label}
      </span>
    </Link>
  );
}

export default function QuickLinks() {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 px-3 py-2 border-b border-zinc-200/60 dark:border-zinc-800/60">
      <QuickLink to="/charts" label="Charts" icon={<CandlestickChartIcon className="h-4 w-4" />} />
      <QuickLink to="/monitor" label="Monitor" icon={<ShieldIcon className="h-4 w-4" />} />
      <QuickLink to="/mandates" label="Mandates" icon={<TargetIcon className="h-4 w-4" />} />
      <QuickLink to="/scalp-sessions" label="Scalp" icon={<ZapIcon className="h-4 w-4" />} />
      <QuickLink to="/notes" label="Notes" icon={<StickyNoteIcon className="h-4 w-4" />} />
      <QuickLink to="/strategies" label="Strategies" icon={<BookOpenIcon className="h-4 w-4" />} />
    </div>
  );
}
