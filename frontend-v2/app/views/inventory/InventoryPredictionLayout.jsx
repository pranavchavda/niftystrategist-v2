import React from 'react';
import { Routes, Route, useLocation, useNavigate } from 'react-router-dom';
import {
  HomeIcon,
  ChartBarSquareIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  MagnifyingGlassIcon,
  Cog6ToothIcon,
  CubeIcon
} from '@heroicons/react/20/solid';

import Dashboard from './Dashboard';
import ForecastsPage from './ForecastsPage';
import AlertsPage from './AlertsPage';
import HistoryPage from './HistoryPage';
import SKULookupPage from './SKULookupPage';

const navigation = [
  { name: 'Dashboard', path: '', icon: HomeIcon },
  { name: 'Forecasts', path: 'forecasts', icon: ChartBarSquareIcon },
  { name: 'Alerts', path: 'alerts', icon: ExclamationTriangleIcon },
  { name: 'Sales History', path: 'history', icon: ClockIcon },
  { name: 'SKU Lookup', path: 'lookup', icon: MagnifyingGlassIcon },
];

export default function InventoryPredictionLayout({ authToken }) {
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (item) => {
    const fullPath = `/inventory${item.path ? `/${item.path}` : ''}`;
    return location.pathname === fullPath;
  };

  return (
    <div className="flex flex-col h-full">
      {/* Top Navigation Bar */}
      <div className="bg-white dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800">
        <div className="px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            <div className="flex items-center gap-3">
              <CubeIcon className="h-6 w-6 text-emerald-600" />
              <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                Inventory Prediction
              </h1>
            </div>
          </div>
        </div>
      </div>

      {/* Sub-navigation Tabs */}
      <div className="bg-white dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800">
        <div className="px-4 sm:px-6 lg:px-8">
          <nav className="flex gap-6 overflow-x-auto" aria-label="Inventory Prediction Navigation">
            {navigation.map((item) => {
              const active = isActive(item);
              return (
                <button
                  key={item.name}
                  onClick={() => navigate(`/inventory${item.path ? `/${item.path}` : ''}`)}
                  className={`
                    flex items-center gap-2 py-3 px-1 border-b-2 text-sm font-medium whitespace-nowrap transition-colors
                    ${active
                      ? 'border-emerald-600 text-emerald-600'
                      : 'border-transparent text-zinc-500 hover:text-zinc-700 hover:border-zinc-300 dark:text-zinc-400 dark:hover:text-zinc-300'
                    }
                  `}
                >
                  <item.icon className="h-5 w-5" />
                  {item.name}
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 bg-zinc-50 dark:bg-zinc-950 overflow-auto">
        <Routes>
          <Route path="/" element={<Dashboard authToken={authToken} />} />
          <Route path="/forecasts" element={<ForecastsPage authToken={authToken} />} />
          <Route path="/forecasts/:sku" element={<ForecastsPage authToken={authToken} />} />
          <Route path="/alerts" element={<AlertsPage authToken={authToken} />} />
          <Route path="/history" element={<HistoryPage authToken={authToken} />} />
          <Route path="/history/:sku" element={<HistoryPage authToken={authToken} />} />
          <Route path="/lookup" element={<SKULookupPage authToken={authToken} />} />
        </Routes>
      </div>
    </div>
  );
}
