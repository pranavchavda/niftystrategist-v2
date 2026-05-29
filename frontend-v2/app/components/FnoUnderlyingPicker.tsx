// Searchable picker for F&O underlyings — indices (NIFTY, BANKNIFTY, SENSEX…)
// plus every stock that offers options. Mirrors EquitySymbolPicker's UX
// (debounced-feel dropdown, click-outside, raw-input honored) but filters a
// locally-cached list from /api/strategies/fno-underlyings instead of hitting
// a search endpoint per keystroke — the list is small and changes ~daily.
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Input } from './catalyst/input';

export interface FnoUnderlying {
  symbol: string;
  name: string;
  kind: 'index' | 'stock';
  lot_size: number;
}

export interface FnoUnderlyingPickerProps {
  authToken: string;
  value: string;
  onSelect: (symbol: string) => void;
  placeholder?: string;
}

// Shared across mounts — the two surfaces (backtester + scalp sessions) reuse it.
let _cache: FnoUnderlying[] | null = null;

export function FnoUnderlyingPicker({
  authToken, value, onSelect, placeholder = 'NIFTY, SENSEX, RELIANCE…',
}: FnoUnderlyingPickerProps) {
  const [query, setQuery] = useState(value);
  const [items, setItems] = useState<FnoUnderlying[]>(_cache || []);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setQuery(value); }, [value]);

  useEffect(() => {
    // Refetch if we never got a populated list (e.g. a transient 503 on first
    // hit cached an empty array) — an empty [] is truthy and would stick.
    if (_cache && _cache.length) { setItems(_cache); return; }
    fetch('/api/strategies/fno-underlyings', {
      headers: { Authorization: `Bearer ${authToken}` },
    })
      .then(r => (r.ok ? r.json() : { underlyings: [] }))
      .then(d => { _cache = d.underlyings || []; setItems(_cache); })
      .catch(() => setItems([]));
  }, [authToken]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Filter on symbol + name. Indices stay first (API returns them first), so a
  // bare focus shows the indices at the top.
  const results = useMemo(() => {
    const q = query.trim().toUpperCase();
    const matched = q
      ? items.filter(u => u.symbol.includes(q) || u.name.toUpperCase().includes(q))
      : items;
    return matched.slice(0, 30);
  }, [query, items]);

  return (
    <div ref={wrapRef} className="relative">
      <Input
        value={query}
        placeholder={placeholder}
        autoComplete="off"
        spellCheck={false}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
          const v = e.target.value.toUpperCase();
          setQuery(v);
          onSelect(v);          // honor raw input even without picking a row
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
      />
      {open && results.length > 0 && (
        <div className="absolute z-20 mt-1 w-full max-h-60 overflow-auto rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 shadow-lg">
          {results.map(u => (
            <button
              key={`${u.kind}:${u.symbol}`}
              type="button"
              className="w-full text-left px-3 py-2 text-sm hover:bg-zinc-100 dark:hover:bg-zinc-700"
              onClick={() => { setQuery(u.symbol); setOpen(false); onSelect(u.symbol); }}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-zinc-900 dark:text-zinc-100">{u.symbol}</span>
                <span className="text-[10px] uppercase tracking-wide text-zinc-400">
                  {u.kind === 'index' ? 'Index' : `lot ${u.lot_size}`}
                </span>
              </div>
              {u.kind === 'stock' && <div className="text-xs text-zinc-500">{u.name}</div>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
