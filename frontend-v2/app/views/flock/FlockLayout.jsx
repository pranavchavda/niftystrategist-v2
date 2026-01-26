import React, { useState } from 'react';
import { Routes, Route, useLocation, useNavigate } from 'react-router-dom';
import {
  InboxIcon,
  ClipboardDocumentListIcon,
  Cog6ToothIcon,
  Bars3Icon,
  XMarkIcon,
  ChatBubbleLeftRightIcon,
} from '@heroicons/react/20/solid';
import { MessageSquare } from 'lucide-react';
import {
  Sidebar,
  SidebarHeader,
  SidebarBody,
  SidebarFooter,
  SidebarSection,
  SidebarItem,
  SidebarLabel,
  SidebarHeading,
  SidebarDivider,
} from '../../components/catalyst/sidebar';

import DigestListPage from './DigestListPage';
import ActionablesPage from './ActionablesPage';

const navigation = [
  {
    name: 'Daily Digests',
    path: '',
    icon: InboxIcon,
    description: 'View all daily actionable digests with calendar display',
  },
  {
    name: 'Actionables',
    path: 'actionables',
    icon: ClipboardDocumentListIcon,
    description: 'Browse and manage all actionable items with filters',
  },
  {
    name: 'Settings',
    path: 'settings',
    icon: Cog6ToothIcon,
    description: 'Configure Flock integration settings',
    comingSoon: true,
  },
];

export default function FlockLayout({ authToken }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  const isActive = (item) => {
    const fullPath = `/flock${item.path ? `/${item.path}` : ''}`;
    return location.pathname === fullPath;
  };

  const handleNavigate = (path, comingSoon) => {
    if (comingSoon) {
      return; // Don't navigate for coming soon items
    }
    navigate(`/flock${path ? `/${path}` : ''}`);
    setMobileSidebarOpen(false); // Close mobile sidebar on navigation
  };

  const sidebarContent = (
    <Sidebar className="h-full bg-white dark:bg-zinc-900">
      {/* Header */}
      <SidebarHeader>
        <div className="flex items-center gap-3 px-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-600 shadow-lg shadow-purple-500/25">
            <MessageSquare className="h-6 w-6 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-bold text-zinc-900 dark:text-zinc-100 truncate">
              Flock Digest
            </div>
            <div className="text-xs text-zinc-500 dark:text-zinc-400">
              Actionable Extraction
            </div>
          </div>
        </div>
      </SidebarHeader>

      {/* Navigation */}
      <SidebarBody>
        <SidebarSection>
          <SidebarHeading>Views</SidebarHeading>
          {navigation.map((item) => {
            const active = isActive(item);
            const Icon = item.icon;

            return (
              <SidebarItem
                key={item.name}
                current={active}
                onClick={() => handleNavigate(item.path, item.comingSoon)}
                className={item.comingSoon ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}
                title={item.description}
              >
                <Icon data-slot="icon" />
                <SidebarLabel className="flex-1">{item.name}</SidebarLabel>
                {item.comingSoon && (
                  <span className="text-xs bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 px-2 py-0.5 rounded-full font-medium">
                    Soon
                  </span>
                )}
              </SidebarItem>
            );
          })}
        </SidebarSection>

        <SidebarDivider />

        <SidebarSection>
          <SidebarHeading>Administration</SidebarHeading>
          <SidebarItem
            onClick={() => handleNavigate('settings', true)}
            className="cursor-not-allowed opacity-50"
            title="Flock integration settings"
          >
            <Cog6ToothIcon data-slot="icon" />
            <SidebarLabel className="flex-1">Settings</SidebarLabel>
            <span className="text-xs bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 px-2 py-0.5 rounded-full font-medium">
              Soon
            </span>
          </SidebarItem>
        </SidebarSection>
      </SidebarBody>

      {/* Footer */}
      <SidebarFooter>
        <div className="px-2 py-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg border border-purple-200 dark:border-purple-800">
          <div className="flex items-start gap-2">
            <div className="flex-shrink-0 w-8 h-8 bg-purple-600 rounded-full flex items-center justify-center">
              <ChatBubbleLeftRightIcon className="h-5 w-5 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-purple-900 dark:text-purple-100">
                Daily Extraction
              </p>
              <p className="text-xs text-purple-700 dark:text-purple-200 mt-0.5">
                Digests generated at 6 AM daily
              </p>
            </div>
          </div>
        </div>
      </SidebarFooter>
    </Sidebar>
  );

  return (
    <div className="flex h-full">
      {/* Mobile Sidebar Toggle Button */}
      <button
        onClick={() => setMobileSidebarOpen(true)}
        className="md:hidden fixed top-4 left-4 z-50 p-2 bg-white dark:bg-zinc-900 rounded-lg shadow-lg border border-zinc-200 dark:border-zinc-800"
        aria-label="Open sidebar"
      >
        <Bars3Icon className="h-6 w-6 text-zinc-700 dark:text-zinc-300" />
      </button>

      {/* Mobile Sidebar Overlay */}
      {mobileSidebarOpen && (
        <>
          {/* Backdrop */}
          <div
            className="md:hidden fixed inset-0 bg-black/30 z-40 transition-opacity"
            onClick={() => setMobileSidebarOpen(false)}
          />

          {/* Sidebar Panel */}
          <div className="md:hidden fixed inset-y-0 left-0 w-64 z-50 transform transition-transform duration-300 ease-in-out shadow-2xl">
            <div className="relative h-full">
              {/* Close Button */}
              <button
                onClick={() => setMobileSidebarOpen(false)}
                className="absolute top-4 right-4 z-10 p-2 bg-white dark:bg-zinc-800 rounded-lg shadow-md hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors"
                aria-label="Close sidebar"
              >
                <XMarkIcon className="h-5 w-5 text-zinc-700 dark:text-zinc-300" />
              </button>
              {sidebarContent}
            </div>
          </div>
        </>
      )}

      {/* Desktop Sidebar */}
      <div className="hidden md:block w-64 flex-shrink-0 border-r border-zinc-200 dark:border-zinc-800">
        {sidebarContent}
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Page Header */}
        <div className="flex-shrink-0 bg-white dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">
                {navigation.find((item) => isActive(item))?.name || 'Flock Digest'}
              </h2>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">
                {navigation.find((item) => isActive(item))?.description || 'Actionable extraction from Flock messages'}
              </p>
            </div>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 bg-zinc-50 dark:bg-zinc-950 overflow-auto">
          <Routes>
            <Route path="/" element={<DigestListPage authToken={authToken} />} />
            <Route path="/actionables" element={<ActionablesPage authToken={authToken} />} />
          </Routes>
        </div>
      </div>
    </div>
  );
}
