import React, { useState } from 'react';
import { Routes, Route, useLocation, useNavigate } from 'react-router-dom';
import {
  PhotoIcon,
  QuestionMarkCircleIcon,
  BookOpenIcon,
  Squares2X2Icon,
  Cog6ToothIcon,
  Bars3Icon,
  XMarkIcon,
} from '@heroicons/react/20/solid';
import { FileEdit } from 'lucide-react';
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

import CategoryLandingPagesPage from './CategoryLandingPagesPage';
import HomeBannersPage from './HomeBannersPage';
import HeaderBannerPage from './HeaderBannerPage';
import MenusPage from './MenusPage';
import HelpPage from './HelpPage';
import HomeBannersHelpPage from './HomeBannersHelpPage';
import HeaderBannerHelpPage from './HeaderBannerHelpPage';
import MenusHelpPage from './MenusHelpPage';

const navigation = [
  {
    name: 'Category Pages',
    path: '',
    icon: PhotoIcon,
    description: 'Edit hero banners and content for category landing pages',
    helpPath: 'help',
  },
  {
    name: 'Home Banners',
    path: 'home-banners',
    icon: PhotoIcon,
    description: 'Manage homepage hero and secondary banners',
    helpPath: 'help/home-banners',
  },
  {
    name: 'Header Banner',
    path: 'header-banner',
    icon: Bars3Icon,
    description: 'Edit top navigation bar promotional links',
    helpPath: 'help/header-banner',
  },
  {
    name: 'Menus',
    path: 'menus',
    icon: Bars3Icon,
    description: 'Manage navigation menus and menu items',
    helpPath: 'help/menus',
  },
  {
    name: 'Settings',
    path: 'settings',
    icon: Cog6ToothIcon,
    description: 'CMS configuration and preferences',
    comingSoon: true,
  },
];

// Removed resourcesNav - help is now context-specific via page header buttons

export default function CMSLayout({ authToken }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  const isActive = (item) => {
    const fullPath = `/cms${item.path ? `/${item.path}` : ''}`;
    return location.pathname === fullPath;
  };

  const handleNavigate = (path, comingSoon) => {
    if (comingSoon) {
      return; // Don't navigate for coming soon items
    }
    navigate(`/cms${path ? `/${path}` : ''}`);
    setMobileSidebarOpen(false); // Close mobile sidebar on navigation
  };

  const sidebarContent = (
    <Sidebar className="h-full bg-white dark:bg-zinc-900">
      {/* Header */}
      <SidebarHeader>
        <div className="flex items-center gap-3 px-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-600 shadow-lg shadow-amber-500/25">
            <FileEdit className="h-6 w-6 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-bold text-zinc-900 dark:text-zinc-100 truncate">
              Content CMS
            </div>
            <div className="text-xs text-zinc-500 dark:text-zinc-400">
              Manage metaobjects
            </div>
          </div>
        </div>
      </SidebarHeader>

      {/* Navigation */}
      <SidebarBody>
        <SidebarSection>
          <SidebarHeading>Content Types</SidebarHeading>
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
            title="CMS settings and configuration"
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
        <div className="px-2 py-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
          <div className="flex items-start gap-2">
            <div className="flex-shrink-0 w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
              <QuestionMarkCircleIcon className="h-5 w-5 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-blue-900 dark:text-blue-100">
                Need Help?
              </p>
              <p className="text-xs text-blue-700 dark:text-blue-200 mt-0.5">
                Click the Help button on any page
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
                {navigation.find((item) => isActive(item))?.name || 'Content Management System'}
              </h2>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-0.5">
                {navigation.find((item) => isActive(item))?.description || 'Manage content for iDrinkCoffee.com'}
              </p>
            </div>
            {/* Help Button */}
            {(() => {
              const activeItem = navigation.find((item) => isActive(item));
              if (activeItem?.helpPath) {
                return (
                  <button
                    onClick={() => navigate(`/cms/${activeItem.helpPath}`)}
                    className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg transition-colors"
                    title={`Help for ${activeItem.name}`}
                  >
                    <QuestionMarkCircleIcon className="h-5 w-5" />
                    <span className="hidden sm:inline">Help</span>
                  </button>
                );
              }
              return null;
            })()}
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 bg-zinc-50 dark:bg-zinc-950 overflow-auto">
          <Routes>
            <Route path="/" element={<CategoryLandingPagesPage authToken={authToken} />} />
            <Route path="/home-banners" element={<HomeBannersPage authToken={authToken} />} />
            <Route path="/header-banner" element={<HeaderBannerPage authToken={authToken} />} />
            <Route path="/menus/*" element={<MenusPage authToken={authToken} />} />
            <Route path="/help" element={<HelpPage />} />
            <Route path="/help/home-banners" element={<HomeBannersHelpPage />} />
            <Route path="/help/header-banner" element={<HeaderBannerHelpPage />} />
            <Route path="/help/menus" element={<MenusHelpPage />} />
            {/* Future routes:
            <Route path="/faq" element={<FAQPage authToken={authToken} />} />
            <Route path="/education" element={<EducationalBlocksPage authToken={authToken} />} />
            <Route path="/comparison" element={<ComparisonTablesPage authToken={authToken} />} />
            <Route path="/settings" element={<CMSSettingsPage authToken={authToken} />} />
            */}
          </Routes>
        </div>
      </div>
    </div>
  );
}
