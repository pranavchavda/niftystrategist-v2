import { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, CandlestickSeries, type IChartApi, type ISeriesApi, type CandlestickData, type Time } from 'lightweight-charts';

interface PriceChartProps {
  symbol: string;
  data: { time: string; open: number; high: number; low: number; close: number }[];
  className?: string;
  activeTimeframe?: string;
  onTimeframeChange?: (tf: string) => void;
}

const TIMEFRAMES = ['1W', '1M', '3M', '6M', '1Y'] as const;

export default function PriceChart({ symbol, data, className = '', activeTimeframe: controlledTf, onTimeframeChange }: PriceChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const [internalTf, setInternalTf] = useState<typeof TIMEFRAMES[number]>('3M');
  const activeTimeframe = controlledTf || internalTf;
  const [isDark, setIsDark] = useState(false);

  // Detect dark mode
  useEffect(() => {
    const check = () => setIsDark(document.documentElement.classList.contains('dark'));
    check();
    const observer = new MutationObserver(check);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Clean up existing chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const container = chartContainerRef.current;

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: isDark ? '#a1a1aa' : '#71717a',
        fontFamily: "'Inter', system-ui, sans-serif",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: isDark ? 'rgba(63, 63, 70, 0.3)' : 'rgba(228, 228, 231, 0.5)' },
        horzLines: { color: isDark ? 'rgba(63, 63, 70, 0.3)' : 'rgba(228, 228, 231, 0.5)' },
      },
      crosshair: {
        mode: 0,
        vertLine: {
          color: isDark ? 'rgba(245, 158, 11, 0.4)' : 'rgba(245, 158, 11, 0.3)',
          width: 1,
          style: 2,
          labelBackgroundColor: isDark ? '#27272a' : '#f4f4f5',
        },
        horzLine: {
          color: isDark ? 'rgba(245, 158, 11, 0.4)' : 'rgba(245, 158, 11, 0.3)',
          width: 1,
          style: 2,
          labelBackgroundColor: isDark ? '#27272a' : '#f4f4f5',
        },
      },
      rightPriceScale: {
        borderColor: isDark ? 'rgba(63, 63, 70, 0.5)' : 'rgba(228, 228, 231, 0.7)',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: isDark ? 'rgba(63, 63, 70, 0.5)' : 'rgba(228, 228, 231, 0.7)',
        timeVisible: false,
      },
      handleScroll: { vertTouchDrag: false },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#16a34a',
      downColor: '#dc2626',
      borderUpColor: '#16a34a',
      borderDownColor: '#dc2626',
      wickUpColor: '#16a34a',
      wickDownColor: '#dc2626',
    });

    const chartData: CandlestickData<Time>[] = data.map((d) => ({
      time: d.time as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));

    series.setData(chartData);
    chart.timeScale().fitContent();

    chartRef.current = chart;
    seriesRef.current = series;

    // Handle resize
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        chart.applyOptions({ width, height });
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [data, isDark]);

  // Get current price info from data
  const lastCandle = data[data.length - 1];
  const prevCandle = data[data.length - 2];
  const priceChange = lastCandle && prevCandle ? lastCandle.close - prevCandle.close : 0;
  const priceChangePct = prevCandle ? (priceChange / prevCandle.close) * 100 : 0;
  const isUp = priceChange >= 0;

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Chart Header */}
      <div className="flex items-center justify-between px-3 py-2 flex-shrink-0">
        <div className="flex items-baseline gap-3">
          <h3 className="text-sm font-bold text-zinc-800 dark:text-zinc-200">{symbol}</h3>
          {lastCandle && (
            <>
              <span className="text-lg font-bold text-zinc-900 dark:text-zinc-100 tabular-nums">
                {lastCandle.close.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </span>
              <span className={`text-xs font-semibold tabular-nums ${isUp ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                {isUp ? '+' : ''}{priceChange.toFixed(2)} ({isUp ? '+' : ''}{priceChangePct.toFixed(2)}%)
              </span>
            </>
          )}
        </div>

        {/* Timeframe Selector */}
        <div className="flex items-center gap-0.5 bg-zinc-100/80 dark:bg-zinc-800/80 rounded-md p-0.5">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => { setInternalTf(tf); onTimeframeChange?.(tf); }}
              className={`px-2 py-1 text-[10px] font-bold rounded transition-colors ${
                activeTimeframe === tf
                  ? 'bg-white dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100 shadow-sm'
                  : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Chart Container */}
      <div ref={chartContainerRef} className="flex-1 min-h-0" />
    </div>
  );
}
