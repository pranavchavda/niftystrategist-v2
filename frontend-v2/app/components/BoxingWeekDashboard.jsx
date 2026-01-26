import React, { useState, useEffect, useCallback } from 'react';
import {
    TrendingUpIcon,
    TrendingDownIcon,
    ShoppingCartIcon,
    DollarSignIcon,
    RefreshCwIcon,
    Loader2Icon,
    CircleIcon,
    TargetIcon,
    TrophyIcon,
} from 'lucide-react';
import {
    AreaChart, Area, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
    PieChart, Pie, Cell, BarChart, Bar, LineChart, Line, ReferenceLine,
} from 'recharts';
import { Card, StatCard } from './Card';
import { Button } from './catalyst/button';

// Constants
const REFRESH_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes
const MILESTONE_MESSAGES = {
    50000: { emoji: "Fantastic Start! $50K reached!", icon: TrophyIcon },
    100000: { emoji: "SIX FIGURES! $100K milestone reached!", icon: TrophyIcon },
    250000: { emoji: "QUARTER MILLION! $250K and counting!", icon: TrophyIcon },
    400000: { emoji: "Almost Half Mil! $400K achieved!", icon: TrophyIcon },
    500000: { emoji: "HALF A MILLION! $500K crushed!", icon: TrophyIcon },
    750000: { emoji: "THREE QUARTERS! $750K milestone!", icon: TrophyIcon },
    1000000: { emoji: "ONE MILLION DOLLARS! $1M achieved!", icon: TrophyIcon },
};

// Chart colors for each year
const YEAR_COLORS = {
    2025: '#ef4444', // red for boxing week
    2024: '#3b82f6', // blue
    2023: '#22c55e', // green
    2022: '#f97316', // orange
};

// Category colors for pie chart
const CATEGORY_COLORS = [
    '#ef4444', // red
    '#3b82f6', // blue
    '#22c55e', // green
    '#f97316', // orange
    '#8b5cf6', // purple
    '#ec4899', // pink
    '#6b7280', // gray
];

// Utility functions
const formatCurrency = (amount) => {
    if (!amount && amount !== 0) return '$0';
    const num = typeof amount === 'string' ? parseFloat(amount.replace(/[^0-9.-]+/g, '')) : amount;
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(num);
};

const formatNumber = (num) => {
    if (!num && num !== 0) return '0';
    const number = typeof num === 'string' ? parseFloat(num.replace(/[^0-9.-]+/g, '')) : num;
    return new Intl.NumberFormat('en-US').format(number);
};

const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${String(secs).padStart(2, '0')}`;
};

// Goal Progress Thermometer Component
const GoalProgress = ({ current, goal, nextMilestone, eta }) => {
    const progress = Math.min((current / goal) * 100, 100);
    const milestones = [100000, 250000, 500000, 750000, 1000000];

    return (
        <Card variant="default" className="p-4">
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <TargetIcon className="w-5 h-5 text-red-500" />
                    <span className="font-semibold text-zinc-900 dark:text-zinc-100">Boxing Week Goal</span>
                </div>
                <span className="text-sm text-zinc-500 dark:text-zinc-400">
                    {formatCurrency(current)} / {formatCurrency(goal)}
                </span>
            </div>

            {/* Progress bar */}
            <div className="relative h-6 bg-zinc-200 dark:bg-zinc-700 rounded-full overflow-hidden">
                <div
                    className="absolute h-full bg-gradient-to-r from-red-500 to-red-600 transition-all duration-1000 ease-out"
                    style={{ width: `${progress}%` }}
                />
                {/* Milestone markers */}
                {milestones.map((milestone) => {
                    const markerPosition = (milestone / goal) * 100;
                    if (markerPosition > 100) return null;
                    return (
                        <div
                            key={milestone}
                            className="absolute top-0 h-full w-0.5 bg-zinc-400 dark:bg-zinc-500"
                            style={{ left: `${markerPosition}%` }}
                        >
                            <span className="absolute -top-5 left-1/2 -translate-x-1/2 text-xs text-zinc-500 whitespace-nowrap">
                                ${milestone / 1000}K
                            </span>
                        </div>
                    );
                })}
            </div>

            {/* Progress percentage and next milestone */}
            <div className="flex items-center justify-between mt-3 text-sm">
                <span className="font-bold text-red-600 dark:text-red-400">{progress.toFixed(1)}%</span>
                {nextMilestone && (
                    <span className="text-zinc-500 dark:text-zinc-400">
                        Next: {formatCurrency(nextMilestone.threshold)}
                        {eta && ` (est. ${new Date(eta).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})`}
                    </span>
                )}
            </div>
        </Card>
    );
};

// Revenue Chart Component (Multi-year comparison)
const RevenueChart = ({ yearsData }) => {
    // Transform data for Recharts
    const chartData = [];
    const years = ['2022', '2023', '2024', '2025'];

    // Boxing Week is 14 days (Dec 23 - Jan 5)
    // Day labels are approximate
    const daysCount = 14;

    for (let dayIndex = 0; dayIndex < daysCount; dayIndex++) {
        // Generate label
        let label = `Day ${dayIndex + 1}`;
        if (dayIndex === 0) label = "Dec 23";
        else if (dayIndex === 1) label = "Dec 24";
        else if (dayIndex === 2) label = "Dec 25";
        else if (dayIndex === 3) label = "Dec 26";
        else if (dayIndex === 9) label = "Jan 1";

        const dataPoint = { day: label };

        for (const year of years) {
            const yearDaily = yearsData[year]?.daily || [];
            // Need to handle missing days carefully
            if (dayIndex < yearDaily.length) {
                dataPoint[year] = yearDaily[dayIndex]?.revenue || 0;
            } else {
                dataPoint[year] = 0;
            }
        }

        chartData.push(dataPoint);
    }

    return (
        <Card variant="default" className="p-4">
            <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Revenue Over Time</h3>
            <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                    <defs>
                        {Object.entries(YEAR_COLORS).map(([year, color]) => (
                            <linearGradient key={year} id={`gradient${year}`} x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                                <stop offset="95%" stopColor={color} stopOpacity={0} />
                            </linearGradient>
                        ))}
                    </defs>
                    <XAxis dataKey="day" stroke="#71717a" interval={2} />
                    <YAxis
                        stroke="#71717a"
                        tickFormatter={(value) => `$${(value / 1000).toFixed(0)}K`}
                    />
                    <Tooltip
                        formatter={(value) => formatCurrency(value)}
                        labelFormatter={(label) => `${label}`}
                        contentStyle={{
                            backgroundColor: 'rgba(24, 24, 27, 0.9)',
                            border: 'none',
                            borderRadius: '8px',
                            color: '#fff'
                        }}
                    />
                    <Legend />
                    {years.map((year) => (
                        <Area
                            key={year}
                            type="monotone"
                            dataKey={year}
                            stroke={YEAR_COLORS[year]}
                            fill={`url(#gradient${year})`}
                            strokeWidth={year === '2025' ? 3 : 1.5}
                            fillOpacity={1}
                        />
                    ))}
                </AreaChart>
            </ResponsiveContainer>
        </Card>
    );
};

// Day-by-Day Comparison Bar Chart
const DayComparisonChart = ({ dayData, loading }) => {
    if (loading) {
        return (
            <Card variant="default" className="p-4">
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Day-by-Day Comparison</h3>
                <div className="flex items-center justify-center h-[300px]">
                    <Loader2Icon className="w-6 h-6 animate-spin text-red-500" />
                </div>
            </Card>
        );
    }

    if (!dayData || !dayData.days || dayData.days.length === 0) {
        return (
            <Card variant="default" className="p-4">
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Day-by-Day Comparison</h3>
                <p className="text-sm text-zinc-500">No day comparison data available</p>
            </Card>
        );
    }

    return (
        <Card variant="default" className="p-4">
            <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Day-by-Day Comparison</h3>
            <ResponsiveContainer width="100%" height={300}>
                <BarChart data={dayData.days} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                    <XAxis dataKey="day_label" stroke="#71717a" tick={{ fontSize: 11 }} interval={0} />
                    <YAxis
                        stroke="#71717a"
                        tickFormatter={(value) => `$${(value / 1000).toFixed(0)}K`}
                    />
                    <Tooltip
                        formatter={(value) => formatCurrency(value)}
                        contentStyle={{
                            backgroundColor: 'rgba(24, 24, 27, 0.9)',
                            border: 'none',
                            borderRadius: '8px',
                            color: '#fff'
                        }}
                    />
                    <Legend />
                    <Bar dataKey="2022" fill={YEAR_COLORS[2022]} name="2022" />
                    <Bar dataKey="2023" fill={YEAR_COLORS[2023]} name="2023" />
                    <Bar dataKey="2024" fill={YEAR_COLORS[2024]} name="2024" />
                    <Bar dataKey="2025" fill={YEAR_COLORS[2025]} name="2025" />
                </BarChart>
            </ResponsiveContainer>
        </Card>
    );
};

// Pace Comparison Chart (Cumulative over time)
const PaceComparisonChart = ({ paceData, loading }) => {
    if (loading) {
        return (
            <Card variant="default" className="p-4">
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Cumulative Pace Comparison</h3>
                <div className="flex items-center justify-center h-[300px]">
                    <Loader2Icon className="w-6 h-6 animate-spin text-red-500" />
                </div>
            </Card>
        );
    }

    if (!paceData || !paceData.pace_data || paceData.pace_data.length === 0) {
        return (
            <Card variant="default" className="p-4">
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Cumulative Pace Comparison</h3>
                <p className="text-sm text-zinc-500">No pace data available</p>
            </Card>
        );
    }

    const currentHour = paceData.current_hour || 0;

    return (
        <Card variant="default" className="p-4">
            <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">Cumulative Pace Comparison</h3>
                {currentHour > 0 && (
                    <span className="text-sm text-zinc-500 dark:text-zinc-400">
                        Hour {currentHour} of Boxing Week
                    </span>
                )}
            </div>
            <ResponsiveContainer width="100%" height={300}>
                <LineChart data={paceData.pace_data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                    <XAxis
                        dataKey="label"
                        stroke="#71717a"
                        tick={{ fontSize: 10 }}
                        interval={8}
                    />
                    <YAxis
                        stroke="#71717a"
                        tickFormatter={(value) => `$${(value / 1000).toFixed(0)}K`}
                    />
                    <Tooltip
                        formatter={(value) => formatCurrency(value)}
                        contentStyle={{
                            backgroundColor: 'rgba(24, 24, 27, 0.9)',
                            border: 'none',
                            borderRadius: '8px',
                            color: '#fff'
                        }}
                    />
                    <Legend />
                    {currentHour > 0 && (
                        <ReferenceLine
                            x={paceData.pace_data.find(p => p.hour >= currentHour)?.label}
                            stroke="#ef4444"
                            strokeDasharray="3 3"
                            label={{ value: 'Now', fill: '#ef4444', fontSize: 10 }}
                        />
                    )}
                    <Line type="monotone" dataKey="2022" stroke={YEAR_COLORS[2022]} strokeWidth={1.5} dot={false} name="2022" />
                    <Line type="monotone" dataKey="2023" stroke={YEAR_COLORS[2023]} strokeWidth={1.5} dot={false} name="2023" />
                    <Line type="monotone" dataKey="2024" stroke={YEAR_COLORS[2024]} strokeWidth={2} dot={false} name="2024" />
                    <Line type="monotone" dataKey="2025" stroke={YEAR_COLORS[2025]} strokeWidth={3} dot={false} name="2025" />
                </LineChart>
            </ResponsiveContainer>
        </Card>
    );
};

// Pace Summary Card - Shows current position vs previous years
const PaceSummaryCard = ({ paceSummary, loading }) => {
    if (loading) {
        return (
            <Card variant="default" className="p-4">
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Current Pace</h3>
                <div className="flex items-center justify-center h-24">
                    <Loader2Icon className="w-6 h-6 animate-spin text-red-500" />
                </div>
            </Card>
        );
    }

    if (!paceSummary || paceSummary.current_hour === 0) {
        return (
            <Card variant="default" className="p-4">
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Current Pace</h3>
                <p className="text-sm text-zinc-500">Boxing Week has not started yet</p>
            </Card>
        );
    }

    const { comparisons, current_2025, day_number, hour_of_day } = paceSummary;

    return (
        <Card variant="default" className="p-4">
            <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">Current Pace</h3>
                <span className="text-sm text-zinc-500 dark:text-zinc-400">
                    Day {day_number}, {hour_of_day}:00
                </span>
            </div>
            <p className="text-2xl font-bold text-red-600 dark:text-red-500 mb-4">
                {formatCurrency(current_2025)}
            </p>
            <div className="space-y-2">
                {comparisons && comparisons.map((comp) => (
                    <div key={comp.year} className="flex items-center justify-between text-sm">
                        <span className="text-zinc-600 dark:text-zinc-400">vs {comp.year}</span>
                        <div className="flex items-center gap-2">
                            <span className={comp.ahead ? 'text-green-600' : 'text-red-600'}>
                                {comp.ahead ? '+' : ''}{comp.percent_change}%
                            </span>
                            <span className="text-zinc-500">
                                ({comp.ahead ? '+' : ''}{formatCurrency(comp.difference)})
                            </span>
                        </div>
                    </div>
                ))}
            </div>
        </Card>
    );
};

// Today vs Same Day/Hour Comparison Card
const TodayComparisonCard = ({ todayData, loading }) => {
    if (loading) {
        return (
            <Card variant="default" className="p-4">
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Today vs Previous Years</h3>
                <div className="flex items-center justify-center h-32">
                    <Loader2Icon className="w-6 h-6 animate-spin text-red-500" />
                </div>
            </Card>
        );
    }

    if (!todayData || todayData.status === 'not_started') {
        return (
            <Card variant="default" className="p-4">
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Today vs Previous Years</h3>
                <p className="text-sm text-zinc-500">Boxing Week has not started yet</p>
                {todayData?.starts_at && (
                    <p className="text-xs text-zinc-400 mt-2">Starts: {todayData.starts_at}</p>
                )}
            </Card>
        );
    }

    if (todayData.status === 'ended') {
        return (
            <Card variant="default" className="p-4">
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Today vs Previous Years</h3>
                <p className="text-sm text-zinc-500">Boxing Week 2025 has ended</p>
            </Card>
        );
    }

    const { day_name, current_hour, current_2025, comparisons, data } = todayData;

    return (
        <Card variant="default" className="p-4">
            <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">
                    {day_name} up to {current_hour}:00
                </h3>
                <span className="text-xs px-2 py-1 bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 rounded-full">
                    Live Comparison
                </span>
            </div>

            {/* Current 2025 Revenue - Prominent Display */}
            <div className="bg-gradient-to-r from-red-50 to-red-100/50 dark:from-red-900/20 dark:to-red-900/10 rounded-lg p-4 mb-4">
                <p className="text-xs text-red-600 dark:text-red-400 uppercase tracking-wide mb-1">2025 Revenue</p>
                <p className="text-3xl font-bold text-red-700 dark:text-red-300">
                    {formatCurrency(current_2025)}
                </p>
            </div>

            {/* Year-by-Year Comparison Bars */}
            <div className="space-y-3">
                {data && data.map((yearData) => {
                    if (yearData.year === 2025) return null; // Skip 2025, it's shown above
                    const comparison = comparisons?.find(c => c.year === yearData.year);
                    const percentOfCurrent = current_2025 > 0 ? (yearData.revenue / current_2025) * 100 : 0;

                    return (
                        <div key={yearData.year} className="space-y-1">
                            <div className="flex items-center justify-between text-sm">
                                <span className="font-medium text-zinc-700 dark:text-zinc-300">{yearData.year}</span>
                                <div className="flex items-center gap-2">
                                    <span className="text-zinc-600 dark:text-zinc-400">{formatCurrency(yearData.revenue)}</span>
                                    {comparison && comparison.percent_change !== null && (
                                        <span className={`text-xs font-medium ${comparison.ahead ? 'text-green-600' : 'text-red-600'}`}>
                                            {comparison.ahead ? '+' : ''}{comparison.percent_change}%
                                        </span>
                                    )}
                                </div>
                            </div>
                            <div className="h-2 bg-zinc-200 dark:bg-zinc-700 rounded-full overflow-hidden">
                                <div
                                    className="h-full rounded-full transition-all duration-500"
                                    style={{
                                        width: `${Math.min(percentOfCurrent, 100)}%`,
                                        backgroundColor: YEAR_COLORS[yearData.year]
                                    }}
                                />
                            </div>
                        </div>
                    );
                })}
            </div>
        </Card>
    );
};

// Category Breakdown Donut Chart
const CategoryDonut = ({ categories }) => {
    if (!categories || categories.length === 0) {
        return (
            <Card variant="default" className="p-4">
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Category Breakdown</h3>
                <p className="text-sm text-zinc-500">No category data available</p>
            </Card>
        );
    }

    // Calculate total for percentage
    const total = categories.reduce((sum, cat) => sum + (cat.revenue || 0), 0);

    return (
        <Card variant="default" className="p-4">
            <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Category Breakdown</h3>
            <div className="flex items-center">
                <ResponsiveContainer width="50%" height={200}>
                    <PieChart>
                        <Pie
                            data={categories.slice(0, 5)}
                            cx="50%"
                            cy="50%"
                            innerRadius={50}
                            outerRadius={80}
                            dataKey="revenue"
                            nameKey="category"
                        >
                            {categories.slice(0, 5).map((entry, index) => (
                                <Cell
                                    key={`cell-${index}`}
                                    fill={CATEGORY_COLORS[index % CATEGORY_COLORS.length]}
                                />
                            ))}
                        </Pie>
                        <Tooltip formatter={(value) => formatCurrency(value)} />
                    </PieChart>
                </ResponsiveContainer>
                <div className="flex-1 space-y-2">
                    {categories.slice(0, 5).map((cat, index) => (
                        <div key={cat.category} className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2">
                                <div
                                    className="w-3 h-3 rounded-full"
                                    style={{ backgroundColor: CATEGORY_COLORS[index % CATEGORY_COLORS.length] }}
                                />
                                <span className="text-zinc-700 dark:text-zinc-300 truncate max-w-[120px]">
                                    {cat.category}
                                </span>
                            </div>
                            <span className="text-zinc-500 dark:text-zinc-400">
                                {total > 0 ? ((cat.revenue / total) * 100).toFixed(1) : 0}%
                            </span>
                        </div>
                    ))}
                </div>
            </div>
        </Card>
    );
};

// Top Products Table
const TopProductsTable = ({ products }) => {
    if (!products || products.length === 0) {
        return (
            <Card variant="default" className="p-4">
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Top Products</h3>
                <p className="text-sm text-zinc-500">No product data available</p>
            </Card>
        );
    }

    return (
        <Card variant="default" className="p-4">
            <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Top Products</h3>
            <div className="space-y-3">
                {products.slice(0, 5).map((product, index) => (
                    <div
                        key={product.title}
                        className="flex items-center justify-between p-2 rounded-lg hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors"
                    >
                        <div className="flex items-center gap-3">
                            <span className="flex items-center justify-center w-6 h-6 bg-red-100 dark:bg-red-900 text-red-600 dark:text-red-300 rounded-full text-sm font-bold">
                                {index + 1}
                            </span>
                            <span className="text-sm text-zinc-700 dark:text-zinc-300 truncate max-w-[200px]">
                                {product.title}
                            </span>
                        </div>
                        <div className="text-right">
                            <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                                {formatCurrency(product.revenue)}
                            </p>
                            <p className="text-xs text-zinc-500 dark:text-zinc-400">
                                {product.quantity} sold
                            </p>
                        </div>
                    </div>
                ))}
            </div>
        </Card>
    );
};

// YoY Comparison Table
const YoYComparisonTable = ({ yearsData, yoyComparison }) => {
    const years = ['2025', '2024', '2023', '2022'];

    return (
        <Card variant="default" className="p-4">
            <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Year-over-Year Comparison</h3>
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-zinc-200 dark:border-zinc-700">
                            <th className="text-left py-2 px-3 font-medium text-zinc-500 dark:text-zinc-400">Metric</th>
                            {years.map((year) => (
                                <th key={year} className="text-right py-2 px-3 font-medium text-zinc-500 dark:text-zinc-400">
                                    {year}
                                </th>
                            ))}
                            <th className="text-right py-2 px-3 font-medium text-zinc-500 dark:text-zinc-400">YoY</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr className="border-b border-zinc-100 dark:border-zinc-800">
                            <td className="py-3 px-3 font-medium text-zinc-700 dark:text-zinc-300">Revenue</td>
                            {years.map((year) => (
                                <td key={year} className="py-3 px-3 text-right text-zinc-900 dark:text-zinc-100">
                                    {formatCurrency(yearsData[year]?.total_revenue || 0)}
                                </td>
                            ))}
                            <td className="py-3 px-3 text-right">
                                {yoyComparison?.['2025_vs_2024'] != null && (
                                    <span className={yoyComparison['2025_vs_2024'] >= 0 ? 'text-green-600' : 'text-red-600'}>
                                        {yoyComparison['2025_vs_2024'] >= 0 ? '+' : ''}
                                        {yoyComparison['2025_vs_2024']}%
                                    </span>
                                )}
                            </td>
                        </tr>
                        <tr className="border-b border-zinc-100 dark:border-zinc-800">
                            <td className="py-3 px-3 font-medium text-zinc-700 dark:text-zinc-300">Orders</td>
                            {years.map((year) => (
                                <td key={year} className="py-3 px-3 text-right text-zinc-900 dark:text-zinc-100">
                                    {formatNumber(yearsData[year]?.order_count || 0)}
                                </td>
                            ))}
                            <td className="py-3 px-3 text-right text-zinc-500">-</td>
                        </tr>
                        <tr>
                            <td className="py-3 px-3 font-medium text-zinc-700 dark:text-zinc-300">AOV</td>
                            {years.map((year) => (
                                <td key={year} className="py-3 px-3 text-right text-zinc-900 dark:text-zinc-100">
                                    {formatCurrency(yearsData[year]?.aov || 0)}
                                </td>
                            ))}
                            <td className="py-3 px-3 text-right text-zinc-500">-</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </Card>
    );
};

// Milestone Toast Component
const MilestoneToast = ({ milestone, onDismiss }) => {
    const milestoneInfo = MILESTONE_MESSAGES[milestone.threshold] || {
        emoji: "Milestone achieved!",
        icon: TrophyIcon
    };
    const Icon = milestoneInfo.icon;

    useEffect(() => {
        const timer = setTimeout(onDismiss, 8000);
        return () => clearTimeout(timer);
    }, [onDismiss]);

    return (
        <div className="fixed bottom-4 right-4 z-50 animate-bounce-in">
            <div className="bg-gradient-to-r from-yellow-400 to-orange-500 text-white p-4 rounded-xl shadow-2xl flex items-center gap-3 max-w-sm">
                <Icon className="w-8 h-8" />
                <div>
                    <p className="font-bold">{milestoneInfo.emoji}</p>
                    <p className="text-sm opacity-90">{formatCurrency(milestone.threshold)} milestone!</p>
                </div>
                <button onClick={onDismiss} className="ml-auto text-white/70 hover:text-white">
                    &times;
                </button>
            </div>
        </div>
    );
};

// Main BoxingWeek Dashboard Component
const BoxingWeekDashboard = ({ authToken }) => {
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [data, setData] = useState(null);
    const [secondsUntilRefresh, setSecondsUntilRefresh] = useState(300);
    const [milestoneToasts, setMilestoneToasts] = useState([]);
    const [notifiedMilestones, setNotifiedMilestones] = useState(new Set());
    const [autoRefresh, setAutoRefresh] = useState(false); // Auto-refresh OFF by default

    // Comparison data states
    const [dayComparison, setDayComparison] = useState(null);
    const [paceComparison, setPaceComparison] = useState(null);
    const [paceSummary, setPaceSummary] = useState(null);
    const [todayComparison, setTodayComparison] = useState(null);
    const [comparisonLoading, setComparisonLoading] = useState(true);

    // Fetch comparison data (day-by-day, pace, and today)
    const fetchComparisonData = useCallback(async () => {
        try {
            setComparisonLoading(true);
            const token = localStorage.getItem('authToken') || authToken;
            const headers = {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            };

            // Fetch all comparison data in parallel
            const [dayRes, paceRes, summaryRes, todayRes] = await Promise.all([
                fetch('/api/boxing-week/comparison/days', { headers }),
                fetch('/api/boxing-week/comparison/pace', { headers }),
                fetch('/api/boxing-week/comparison/pace/summary', { headers }),
                fetch('/api/boxing-week/comparison/today', { headers }),
            ]);

            if (dayRes.ok) {
                const dayResult = await dayRes.json();
                if (dayResult.success) setDayComparison(dayResult.data);
            }

            if (paceRes.ok) {
                const paceResult = await paceRes.json();
                if (paceResult.success) setPaceComparison(paceResult.data);
            }

            if (summaryRes.ok) {
                const summaryResult = await summaryRes.json();
                if (summaryResult.success) setPaceSummary(summaryResult.data);
            }

            if (todayRes.ok) {
                const todayResult = await todayRes.json();
                if (todayResult.success) setTodayComparison(todayResult.data);
            }
        } catch (err) {
            console.error('Boxing Week comparison fetch error:', err);
        } finally {
            setComparisonLoading(false);
        }
    }, [authToken]);

    // Fetch dashboard data
    const fetchData = useCallback(async () => {
        try {
            setLoading(true);
            const token = localStorage.getItem('authToken') || authToken;

            const response = await fetch('/api/boxing-week/dashboard', {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
            });

            if (!response.ok) {
                throw new Error(`Failed to fetch Boxing Week data: ${response.statusText}`);
            }

            const result = await response.json();
            if (result.success) {
                setData(result.data);
                setError(null);

                // Check for new milestone achievements
                const newlyAchieved = result.data.newly_achieved_milestones || [];
                for (const milestone of newlyAchieved) {
                    if (!notifiedMilestones.has(milestone.threshold)) {
                        setMilestoneToasts((prev) => [...prev, milestone]);
                        setNotifiedMilestones((prev) => new Set([...prev, milestone.threshold]));

                        // Mark as notified on server
                        fetch(`/api/boxing-week/milestones/${milestone.threshold}/notified`, {
                            method: 'POST',
                            headers: { 'Authorization': `Bearer ${token}` },
                        });
                    }
                }
            } else {
                throw new Error(result.error || 'Unknown error');
            }
        } catch (err) {
            console.error('Boxing Week fetch error:', err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [authToken, notifiedMilestones]);

    // Initial fetch
    useEffect(() => {
        fetchData();
        fetchComparisonData();
    }, []); // Only run once on mount

    // Auto-refresh polling (only when enabled)
    useEffect(() => {
        if (!autoRefresh) return;

        const interval = setInterval(() => {
            fetchData();
            fetchComparisonData();
        }, REFRESH_INTERVAL_MS);
        return () => clearInterval(interval);
    }, [autoRefresh, fetchData, fetchComparisonData]);

    // Countdown timer (only when auto-refresh is enabled)
    useEffect(() => {
        if (!autoRefresh) return;

        const timer = setInterval(() => {
            setSecondsUntilRefresh((prev) => (prev <= 1 ? 300 : prev - 1));
        }, 1000);
        return () => clearInterval(timer);
    }, [autoRefresh]);

    // Reset countdown on data fetch or when auto-refresh is toggled on
    useEffect(() => {
        if (!loading && autoRefresh) {
            setSecondsUntilRefresh(300);
        }
    }, [data, loading, autoRefresh]);

    // Dismiss milestone toast
    const dismissToast = useCallback((index) => {
        setMilestoneToasts((prev) => prev.filter((_, i) => i !== index));
    }, []);

    if (loading && !data) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[50vh]">
                <Loader2Icon className="w-10 h-10 animate-spin text-red-500 mb-4" />
                <p className="text-zinc-500">Loading Boxing Week analytics...</p>
            </div>
        );
    }

    if (error && !data) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[50vh]">
                <h2 className="text-xl font-bold text-red-600 mb-2">Error Loading Dashboard</h2>
                <p className="text-zinc-500 mb-4">{error}</p>
                <Button onClick={() => { fetchData(); fetchComparisonData(); }} className="gap-2">
                    <RefreshCwIcon className="w-4 h-4" /> Try Again
                </Button>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                        <span className="text-3xl">🥊</span> Boxing Week Tracker
                        {data?.is_active && (
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 animate-pulse">
                                LIVE
                            </span>
                        )}
                    </h1>
                    <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
                        Real-time sales tracking for Dec 23 – Jan 5
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    {/* Refresh Controls */}
                    <div className="flex items-center gap-2 bg-zinc-100 dark:bg-zinc-800 rounded-lg p-1.5">
                        <Button
                            plain
                            onClick={() => setAutoRefresh(!autoRefresh)}
                            className={`text-xs ${autoRefresh ? 'text-green-600' : 'text-zinc-500'}`}
                        >
                            {autoRefresh ? `Auto-refresh ON (${secondsUntilRefresh}s)` : 'Auto-refresh OFF'}
                        </Button>
                        <div className="w-px h-4 bg-zinc-300 dark:bg-zinc-600"></div>
                        <Button
                            plain
                            onClick={() => { fetchData(); fetchComparisonData(); }}
                            title="Refresh now"
                        >
                            <RefreshCwIcon className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                        </Button>
                    </div>
                </div>
            </div>

            {/* Main KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                    title="Total Revenue (2025)"
                    value={formatCurrency(data?.years_data[2025]?.total_revenue || 0)}
                    icon={<DollarSignIcon className="w-6 h-6 text-zinc-500 dark:text-zinc-400" />}
                    trend={data?.yoy_comparison['2025_vs_2024'] ? {
                        value: Math.abs(data.yoy_comparison['2025_vs_2024']),
                        isPositive: data.yoy_comparison['2025_vs_2024'] >= 0
                    } : undefined}
                />
                <StatCard
                    title="Orders"
                    value={formatNumber(data?.years_data[2025]?.order_count || 0)}
                    icon={<ShoppingCartIcon className="w-6 h-6 text-zinc-500 dark:text-zinc-400" />}
                />
                <StatCard
                    title="Avg Order Value"
                    value={formatCurrency(data?.years_data[2025]?.aov || 0)}
                    icon={<TrendingUpIcon className="w-6 h-6 text-zinc-500 dark:text-zinc-400" />}
                />
                <div className="lg:col-span-1">
                    <Card variant="default" className="p-4 h-full flex flex-col justify-center items-center bg-gradient-to-br from-red-50 to-red-100 dark:from-red-900/20 dark:to-red-800/20 border-red-200 dark:border-red-800">
                        <div className="text-center">
                            <h3 className="font-semibold text-red-900 dark:text-red-200 mb-1">Next Milestone</h3>
                            <p className="text-2xl font-bold text-red-600 dark:text-red-400">
                                {data?.next_milestone ? formatCurrency(data.next_milestone.threshold) : "All Achieved!"}
                            </p>
                            {data?.next_milestone && (
                                <p className="text-xs text-red-700 dark:text-red-300 mt-1">
                                    {formatCurrency(data.next_milestone.threshold - (data?.years_data[2025]?.total_revenue || 0))} to go
                                </p>
                            )}
                        </div>
                    </Card>
                </div>
            </div>

            {/* Goal Progress - Top Priority */}
            <GoalProgress
                current={data?.years_data[2025]?.total_revenue || 0}
                goal={1000000} // $1M Goal for Boxing Week
                nextMilestone={data?.next_milestone}
            />

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left Column - Main Charts (2/3 width) */}
                <div className="lg:col-span-2 space-y-6">
                    {/* Revenue Chart */}
                    <RevenueChart yearsData={data?.years_data || {}} />

                    {/* Today Comparison */}
                    <TodayComparisonCard todayData={todayComparison} loading={comparisonLoading} />

                    {/* Pace Comparison */}
                    <PaceComparisonChart paceData={paceComparison} loading={comparisonLoading} />

                    {/* Day-by-Day Comparison */}
                    <DayComparisonChart dayData={dayComparison} loading={comparisonLoading} />
                </div>

                {/* Right Column - Breakdowns & Lists (1/3 width) */}
                <div className="lg:col-span-1 space-y-6">
                    {/* Pace Summary */}
                    <PaceSummaryCard paceSummary={paceSummary} loading={comparisonLoading} />

                    {/* YoY Table */}
                    <YoYComparisonTable
                        yearsData={data?.years_data || {}}
                        yoyComparison={data?.yoy_comparison}
                    />

                    {/* Top Products */}
                    <TopProductsTable products={data?.years_data[2025]?.top_products} />

                    {/* Category Breakdown */}
                    <CategoryDonut categories={data?.years_data[2025]?.category_breakdown} />
                </div>
            </div>

            {/* Milestone Toasts */}
            {milestoneToasts.map((milestone, index) => (
                <MilestoneToast
                    key={`${milestone.threshold}-${index}`}
                    milestone={milestone}
                    onDismiss={() => dismissToast(index)}
                />
            ))}
        </div>
    );
};

export default BoxingWeekDashboard;
