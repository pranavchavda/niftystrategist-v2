// Shared equity symbol autocomplete. Reuses /api/monitor/symbols (the same
// backend search endpoint the rule builder + scalp sessions UI already hit).
//
// Originally lived inline in scalp-sessions.tsx; extracted so /backtest can
// share the exact same UX without copy-pasting the debounce + click-outside
// + result-list logic.
import { useCallback, useEffect, useRef, useState } from 'react';
import { Input } from './catalyst/input';

export interface EquitySymbolPickerProps {
  authToken: string;
  value: string;
  onSelect: (symbol: string) => void;
  placeholder?: string;
}

export function EquitySymbolPicker({
  authToken, value, onSelect, placeholder = 'Search equity symbol (e.g. RELIANCE)',
}: EquitySymbolPickerProps) {
  const [query, setQuery] = useState(value);
  const [results, setResults] = useState<{ symbol: string; name: string }[]>([]);
  const [open, setOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  // Keep the input in sync when the parent resets value (e.g. mode toggle).
  useEffect(() => { setQuery(value); }, [value]);

  // Click outside closes the dropdown.
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const search = useCallback(async (term: string) => {
    if (term.length < 1) { setResults([]); return; }
    try {
      const res = await fetch(`/api/monitor/symbols?q=${encodeURIComponent(term)}&limit=8`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setResults(data.results || []);
        setOpen(true);
      }
    } catch { /* search is best-effort — fall through to manual typing */ }
  }, [authToken]);

  return (
    <div ref={wrapRef} className="relative">
      <Input
        value={query}
        placeholder={placeholder}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
          const v = e.target.value.toUpperCase();
          setQuery(v);
          // Surface the typed value immediately so a user who types a full
          // symbol and clicks Run without picking from the list still gets
          // the correct value submitted. The autocomplete list refines it
          // when they pick a row, but raw input is honored.
          onSelect(v);
          if (debounceRef.current) clearTimeout(debounceRef.current);
          debounceRef.current = setTimeout(() => search(v), 250);
        }}
        onFocus={() => { if (results.length > 0) setOpen(true); }}
      />
      {open && results.length > 0 && (
        <div className="absolute z-20 mt-1 w-full max-h-60 overflow-auto rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 shadow-lg">
          {results.map(r => (
            <button
              key={r.symbol}
              type="button"
              className="w-full text-left px-3 py-2 text-sm hover:bg-zinc-100 dark:hover:bg-zinc-700"
              onClick={() => { setQuery(r.symbol); setOpen(false); onSelect(r.symbol); }}
            >
              <div className="font-medium text-zinc-900 dark:text-zinc-100">{r.symbol}</div>
              <div className="text-xs text-zinc-500">{r.name}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
