import { useEffect, useRef, useState } from 'react';
import { Line, LineChart, ReferenceDot, ResponsiveContainer, YAxis } from 'recharts';
import {
  createChart, ColorType, CandlestickSeries, LineSeries,
  createSeriesMarkers, type IChartApi, type CandlestickData, type LineData,
  type Time, type SeriesMarker,
} from 'lightweight-charts';
import { Dialog, DialogTitle, DialogBody, DialogActions } from '../catalyst/dialog';
import { Button } from '../catalyst/button';
import { Maximize2 } from 'lucide-react';

export interface SnapshotCandle {
  t: string;          // ISO timestamp (UTC, naive — same convention as other backend datetimes)
  o: number; h: number; l: number; c: number; v: number;
}

export interface DecisionSnapshot {
  v: number;
  timeframe: string;
  primary_indicator: string;
  primary_series: (number | null)[];
  confirm_indicator: string | null;
  confirm_series: (number | null)[] | null;
  decision_price: number | null;
  candles: SnapshotCandle[];
}

interface SnapshotChartProps {
  snapshot: DecisionSnapshot;
  eventType: string;
  optionType?: string | null;
  strike?: number | null;
}

// Color the marker by event direction.
function eventColor(eventType: string): string {
  if (eventType.startsWith('entry')) return '#3b82f6';      // blue
  if (eventType === 'exit_target') return '#16a34a';        // green
  if (eventType === 'exit_sl') return '#dc2626';            // red
  if (eventType === 'exit_trail') return '#f59e0b';         // amber
  if (eventType === 'exit_reversal') return '#a855f7';      // purple
  if (eventType === 'exit_squareoff') return '#71717a';     // zinc
  return '#71717a';
}

// Convert snapshot ISO timestamp (UTC, no tz suffix) to seconds-since-epoch
// for lightweight-charts Time, and to a stable string key for recharts.
function toEpochSeconds(iso: string): number {
  // The backend writes naive UTC; coerce by appending Z.
  const t = iso.endsWith('Z') ? iso : iso + 'Z';
  return Math.floor(new Date(t).getTime() / 1000);
}

export function MiniSnapshotChart({ snapshot, eventType }: SnapshotChartProps) {
  if (!snapshot?.candles?.length) return null;
  const data = snapshot.candles.map((c, i) => ({ i, c: c.c }));
  const lastIdx = data.length - 1;
  const lastClose = data[lastIdx].c;
  const color = eventColor(eventType);
  return (
    <div className="w-[280px] h-[80px] -mx-1">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <YAxis hide domain={['dataMin - 0.5', 'dataMax + 0.5']} />
          <Line
            type="monotone"
            dataKey="c"
            stroke="#64748b"
            strokeWidth={1.25}
            dot={false}
            isAnimationActive={false}
          />
          <ReferenceDot x={lastIdx} y={lastClose} r={4} fill={color} stroke="white" strokeWidth={1.5} ifOverflow="extendDomain" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function FullSnapshotChart({ snapshot, eventType, optionType, strike }: SnapshotChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const check = () => setIsDark(document.documentElement.classList.contains('dark'));
    check();
    const obs = new MutationObserver(check);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    // lightweight-charts displays in UTC by default. Backend timestamps are
    // naive UTC, so format axis + crosshair labels in IST for the trader.
    const istHHMM = (sec: number) => new Date(sec * 1000).toLocaleString('en-IN', {
      hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata',
    });
    const istFull = (sec: number) => new Date(sec * 1000).toLocaleString('en-IN', {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
      hour12: false, timeZone: 'Asia/Kolkata',
    });
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: isDark ? '#d4d4d8' : '#3f3f46',
      },
      grid: {
        vertLines: { color: isDark ? '#27272a' : '#e4e4e7' },
        horzLines: { color: isDark ? '#27272a' : '#e4e4e7' },
      },
      width: containerRef.current.clientWidth,
      height: 360,
      localization: {
        timeFormatter: (t: Time) => istFull(t as number),
      },
      timeScale: {
        timeVisible: true, secondsVisible: false,
        borderColor: isDark ? '#3f3f46' : '#a1a1aa',
        tickMarkFormatter: (t: Time) => istHHMM(t as number),
      },
      rightPriceScale: { borderColor: isDark ? '#3f3f46' : '#a1a1aa' },
    });
    chartRef.current = chart;

    const candleData: CandlestickData[] = snapshot.candles.map(c => ({
      time: toEpochSeconds(c.t) as Time,
      open: c.o, high: c.h, low: c.l, close: c.c,
    }));
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#16a34a', downColor: '#dc2626', borderVisible: false,
      wickUpColor: '#16a34a', wickDownColor: '#dc2626',
    });
    candleSeries.setData(candleData);

    // Primary indicator overlay (only plot when values are numeric — utbot's
    // ±1 sign is plotted on its own scale; ema_crossover diff plots on price
    // axis only when within range, otherwise on a separate scale).
    const primaryRange = snapshot.primary_series.filter(v => v !== null) as number[];
    if (primaryRange.length > 0) {
      const lineData: LineData[] = snapshot.candles.map((c, i) => {
        const v = snapshot.primary_series[i];
        return v === null ? null : { time: toEpochSeconds(c.t) as Time, value: v };
      }).filter((p): p is LineData => p !== null);
      // Use a separate price scale so non-price indicators don't squash candles.
      const overlay = chart.addSeries(LineSeries, {
        color: '#f59e0b', lineWidth: 2, priceScaleId: 'overlay',
        priceFormat: { type: 'price', precision: 4, minMove: 0.0001 },
      });
      chart.priceScale('overlay').applyOptions({
        scaleMargins: { top: 0.1, bottom: 0.7 },
        borderVisible: false,
      });
      overlay.setData(lineData);
    }

    if (snapshot.confirm_indicator && snapshot.confirm_series) {
      const lineData: LineData[] = snapshot.candles.map((c, i) => {
        const v = snapshot.confirm_series![i];
        return v === null ? null : { time: toEpochSeconds(c.t) as Time, value: v };
      }).filter((p): p is LineData => p !== null);
      if (lineData.length > 0) {
        const overlay = chart.addSeries(LineSeries, {
          color: '#06b6d4', lineWidth: 1.5, priceScaleId: 'confirm',
          priceFormat: { type: 'price', precision: 4, minMove: 0.0001 },
        });
        chart.priceScale('confirm').applyOptions({
          scaleMargins: { top: 0.7, bottom: 0.05 },
          borderVisible: false,
        });
        overlay.setData(lineData);
      }
    }

    // Decision marker on the last bar.
    const last = snapshot.candles[snapshot.candles.length - 1];
    const marker: SeriesMarker<Time> = {
      time: toEpochSeconds(last.t) as Time,
      position: eventType.startsWith('entry') ? 'belowBar' : 'aboveBar',
      color: eventColor(eventType),
      shape: eventType.startsWith('entry') ? 'arrowUp' : 'arrowDown',
      text: eventType.replace(/^(entry_|exit_)/, '').toUpperCase(),
    };
    createSeriesMarkers(candleSeries, [marker]);

    chart.timeScale().fitContent();

    const onResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', onResize);

    return () => {
      window.removeEventListener('resize', onResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [snapshot, eventType, isDark]);

  return (
    <div className="space-y-2">
      <div className="text-xs text-zinc-500 flex items-center gap-3 flex-wrap">
        <span>Timeframe: {snapshot.timeframe}</span>
        <span>Primary: <span className="text-amber-600 dark:text-amber-400">{snapshot.primary_indicator}</span></span>
        {snapshot.confirm_indicator && (
          <span>Confirm: <span className="text-cyan-600 dark:text-cyan-400">{snapshot.confirm_indicator}</span></span>
        )}
        {optionType && strike != null && <span>{optionType} {strike}</span>}
        {snapshot.decision_price != null && <span>@ {snapshot.decision_price.toFixed(2)}</span>}
      </div>
      <div ref={containerRef} className="w-full" />
    </div>
  );
}

interface SnapshotChartButtonProps extends SnapshotChartProps {
  className?: string;
}

export function SnapshotChartButton({ snapshot, eventType, optionType, strike, className }: SnapshotChartButtonProps) {
  const [open, setOpen] = useState(false);
  if (!snapshot?.candles?.length) return null;
  return (
    <>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setOpen(true); }}
        className={`group relative flex items-center gap-1 ${className || ''}`}
        title="Click for full chart"
      >
        <MiniSnapshotChart snapshot={snapshot} eventType={eventType} />
        <Maximize2 className="w-3 h-3 text-zinc-400 group-hover:text-zinc-600 dark:group-hover:text-zinc-300" />
      </button>
      <Dialog open={open} onClose={() => setOpen(false)} size="3xl">
        <DialogTitle>
          Decision Snapshot — {eventType.replace(/^(entry_|exit_)/, '').toUpperCase()}
          {optionType && strike != null && (
            <span className="ml-2 text-sm font-normal text-zinc-500">{optionType} {strike}</span>
          )}
        </DialogTitle>
        <DialogBody>
          {open && <FullSnapshotChart snapshot={snapshot} eventType={eventType} optionType={optionType} strike={strike} />}
        </DialogBody>
        <DialogActions>
          <Button plain onClick={() => setOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
