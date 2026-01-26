import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CalendarIcon,
  ClipboardDocumentListIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from '@heroicons/react/20/solid';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function DigestListPage({ authToken }) {
  const navigate = useNavigate();
  const [digests, setDigests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedMonth, setSelectedMonth] = useState(new Date());
  const [stats, setStats] = useState(null);

  useEffect(() => {
    fetchDigests();
    fetchStats();
  }, []);

  const fetchDigests = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/flock/digests`, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });

      if (!response.ok) throw new Error('Failed to fetch digests');

      const data = await response.json();
      setDigests(data.digests || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/flock/stats`, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });

      if (!response.ok) throw new Error('Failed to fetch stats');

      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  const getDigestForDate = (date) => {
    const dateStr = date.toISOString().split('T')[0];
    return digests.find((d) => d.digest_date === dateStr);
  };

  const renderCalendar = () => {
    const year = selectedMonth.getFullYear();
    const month = selectedMonth.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDayOfWeek = firstDay.getDay();

    const weeks = [];
    let currentWeek = Array(7).fill(null);

    // Fill in the days
    for (let day = 1; day <= daysInMonth; day++) {
      const date = new Date(year, month, day);
      const dayOfWeek = date.getDay();
      const digest = getDigestForDate(date);

      currentWeek[dayOfWeek] = { date, digest };

      if (dayOfWeek === 6 || day === daysInMonth) {
        weeks.push(currentWeek);
        currentWeek = Array(7).fill(null);
      }
    }

    return weeks;
  };

  const prevMonth = () => {
    setSelectedMonth(new Date(selectedMonth.getFullYear(), selectedMonth.getMonth() - 1));
  };

  const nextMonth = () => {
    setSelectedMonth(new Date(selectedMonth.getFullYear(), selectedMonth.getMonth() + 1));
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'urgent':
        return 'text-red-600 bg-red-50';
      case 'high':
        return 'text-orange-600 bg-orange-50';
      case 'medium':
        return 'text-yellow-600 bg-yellow-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto"></div>
          <p className="mt-4 text-sm text-zinc-500">Loading digests...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <ExclamationCircleIcon className="h-12 w-12 text-red-500 mx-auto" />
          <p className="mt-4 text-sm text-red-600">{error}</p>
        </div>
      </div>
    );
  }

  const monthNames = [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
  ];

  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  return (
    <div className="h-full p-6">
      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white dark:bg-zinc-900 rounded-lg p-4 border border-zinc-200 dark:border-zinc-800">
            <div className="text-sm text-zinc-500 dark:text-zinc-400">Total Digests</div>
            <div className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mt-1">
              {stats.total_digests}
            </div>
          </div>
          <div className="bg-white dark:bg-zinc-900 rounded-lg p-4 border border-zinc-200 dark:border-zinc-800">
            <div className="text-sm text-zinc-500 dark:text-zinc-400">Total Actionables</div>
            <div className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mt-1">
              {stats.total_actionables}
            </div>
          </div>
          <div className="bg-white dark:bg-zinc-900 rounded-lg p-4 border border-zinc-200 dark:border-zinc-800">
            <div className="text-sm text-zinc-500 dark:text-zinc-400">Pending</div>
            <div className="text-2xl font-bold text-orange-600 mt-1">{stats.pending_count}</div>
          </div>
          <div className="bg-white dark:bg-zinc-900 rounded-lg p-4 border border-zinc-200 dark:border-zinc-800">
            <div className="text-sm text-zinc-500 dark:text-zinc-400">Completed</div>
            <div className="text-2xl font-bold text-green-600 mt-1">{stats.completed_count}</div>
          </div>
        </div>
      )}

      {/* Calendar */}
      <div className="bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden">
        {/* Calendar Header */}
        <div className="flex items-center justify-between p-4 border-b border-zinc-200 dark:border-zinc-800">
          <button
            onClick={prevMonth}
            className="p-2 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
          >
            <ChevronLeftIcon className="h-5 w-5 text-zinc-600 dark:text-zinc-400" />
          </button>
          <div className="flex items-center gap-2">
            <CalendarIcon className="h-5 w-5 text-purple-600" />
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              {monthNames[selectedMonth.getMonth()]} {selectedMonth.getFullYear()}
            </h3>
          </div>
          <button
            onClick={nextMonth}
            className="p-2 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
          >
            <ChevronRightIcon className="h-5 w-5 text-zinc-600 dark:text-zinc-400" />
          </button>
        </div>

        {/* Calendar Grid */}
        <div className="p-4">
          {/* Day Headers */}
          <div className="grid grid-cols-7 gap-2 mb-2">
            {dayNames.map((day) => (
              <div
                key={day}
                className="text-center text-xs font-medium text-zinc-500 dark:text-zinc-400 py-2"
              >
                {day}
              </div>
            ))}
          </div>

          {/* Calendar Days */}
          {renderCalendar().map((week, weekIndex) => (
            <div key={weekIndex} className="grid grid-cols-7 gap-2 mb-2">
              {week.map((day, dayIndex) => (
                <div
                  key={dayIndex}
                  className={`
                    min-h-24 p-2 rounded-lg border transition-colors
                    ${
                      day
                        ? 'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900'
                        : 'border-transparent'
                    }
                    ${
                      day?.digest
                        ? 'cursor-pointer hover:border-purple-300 hover:bg-purple-50 dark:hover:bg-purple-900/20'
                        : ''
                    }
                  `}
                  onClick={() => day?.digest && navigate(`/flock/digests/${day.digest.id}`)}
                >
                  {day && (
                    <>
                      <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-1">
                        {day.date.getDate()}
                      </div>
                      {day.digest && (
                        <div className="space-y-1">
                          <div className="flex items-center gap-1 text-xs text-zinc-600 dark:text-zinc-400">
                            <ClipboardDocumentListIcon className="h-3 w-3" />
                            <span>{day.digest.total_actionables || 0}</span>
                          </div>
                          {day.digest.urgent_count > 0 && (
                            <div className="text-xs font-medium text-red-600">
                              {day.digest.urgent_count} urgent
                            </div>
                          )}
                          {day.digest.high_priority_count > 0 && (
                            <div className="text-xs font-medium text-orange-600">
                              {day.digest.high_priority_count} high
                            </div>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Recent Digests List */}
      <div className="mt-6 bg-white dark:bg-zinc-900 rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden">
        <div className="p-4 border-b border-zinc-200 dark:border-zinc-800">
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Recent Digests</h3>
        </div>
        <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
          {digests.slice(0, 10).map((digest) => (
            <div
              key={digest.id}
              className="p-4 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 cursor-pointer transition-colors"
              onClick={() => navigate(`/flock/digests/${digest.id}`)}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <CalendarIcon className="h-4 w-4 text-zinc-400" />
                    <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                      {new Date(digest.digest_date).toLocaleDateString('en-US', {
                        weekday: 'long',
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                      })}
                    </span>
                  </div>
                  {digest.summary && (
                    <p className="text-sm text-zinc-600 dark:text-zinc-400 line-clamp-2">
                      {digest.summary}
                    </p>
                  )}
                </div>
                <div className="flex flex-col items-end gap-2 ml-4">
                  <div className="flex items-center gap-1 text-sm text-zinc-600 dark:text-zinc-400">
                    <ClipboardDocumentListIcon className="h-4 w-4" />
                    <span>{digest.total_actionables || 0} items</span>
                  </div>
                  <div className="flex gap-1">
                    {digest.urgent_count > 0 && (
                      <span className="px-2 py-0.5 text-xs font-medium rounded-full text-red-600 bg-red-50">
                        {digest.urgent_count} urgent
                      </span>
                    )}
                    {digest.high_priority_count > 0 && (
                      <span className="px-2 py-0.5 text-xs font-medium rounded-full text-orange-600 bg-orange-50">
                        {digest.high_priority_count} high
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
