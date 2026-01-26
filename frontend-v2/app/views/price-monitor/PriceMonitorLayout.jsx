import React from 'react';
import { Routes, Route, useLocation, useNavigate } from 'react-router-dom';
import {
  HomeIcon,
  BuildingStorefrontIcon,
  Square2StackIcon,
  ExclamationTriangleIcon,
  Cog6ToothIcon,
  QuestionMarkCircleIcon,
  ClockIcon,
  ChartBarIcon
} from '@heroicons/react/20/solid';

import Dashboard from './Dashboard';
import CompetitorsPage from './CompetitorsPage';
import ProductMatchesPage from './ProductMatchesPage';
import PriceAlertsPage from './PriceAlertsPage';
import ViolationHistoryPage from './ViolationHistoryPage';
import MonitorSettingsPage from './MonitorSettingsPage';
import PriceMonitorHelp from './PriceMonitorHelp';

const navigation = [
  { name: 'Dashboard', path: '', icon: HomeIcon },
  { name: 'Competitors', path: 'competitors', icon: BuildingStorefrontIcon },
  { name: 'Product Matches', path: 'matches', icon: Square2StackIcon },
  { name: 'Price Alerts', path: 'alerts', icon: ExclamationTriangleIcon },
  { name: 'Violation History', path: 'history', icon: ClockIcon },
  { name: 'Settings', path: 'settings', icon: Cog6ToothIcon },
  { name: 'Help', path: 'help', icon: QuestionMarkCircleIcon },
];

export default function PriceMonitorLayout() {
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (item) => {
    const fullPath = `/price-monitor${item.path ? `/${item.path}` : ''}`;
    return location.pathname === fullPath;
  };

  return (
    <div className="flex flex-col h-full">
      {/* Top Navigation Bar */}
      <div className="bg-white dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800">
        <div className="px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            <div className="flex items-center gap-3">
              <ChartBarIcon className="h-6 w-6 text-indigo-600" />
              <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                MAP Enforcement
              </h1>
            </div>
          </div>
        </div>
      </div>

      {/* Sub-navigation Tabs */}
      <div className="bg-white dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800">
        <div className="px-4 sm:px-6 lg:px-8">
          <nav className="flex gap-6 overflow-x-auto" aria-label="Price Monitor Navigation">
            {navigation.map((item) => {
              const active = isActive(item);
              return (
                <button
                  key={item.name}
                  onClick={() => navigate(`/price-monitor${item.path ? `/${item.path}` : ''}`)}
                  className={`
                    flex items-center gap-2 py-3 px-1 border-b-2 text-sm font-medium whitespace-nowrap transition-colors
                    ${active
                      ? 'border-indigo-600 text-indigo-600'
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
          <Route path="/" element={<Dashboard />} />
          <Route path="/competitors" element={<CompetitorsPage />} />
          <Route path="/matches" element={<ProductMatchesPage />} />
          <Route path="/alerts" element={<PriceAlertsPage />} />
          <Route path="/history" element={<ViolationHistoryPage />} />
          <Route path="/settings" element={<MonitorSettingsPage />} />
          <Route path="/help" element={<PriceMonitorHelp />} />
        </Routes>
      </div>
    </div>
  );
}