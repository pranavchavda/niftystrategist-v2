import { useEffect, useState, useCallback } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router';
import * as Headless from '@headlessui/react';
import Sidebar from '../components/Sidebar';
import ScratchpadPanel from '../components/ScratchpadPanel';

function OpenMenuIcon() {
  return (
    <svg data-slot="icon" viewBox="0 0 20 20" aria-hidden="true" className="w-5 h-5">
      <path d="M2 6.75C2 6.33579 2.33579 6 2.75 6H17.25C17.6642 6 18 6.33579 18 6.75C18 7.16421 17.6642 7.5 17.25 7.5H2.75C2.33579 7.5 2 7.16421 2 6.75ZM2 13.25C2 12.8358 2.33579 12.5 2.75 12.5H17.25C17.6642 12.5 18 12.8358 18 13.25C18 13.6642 17.6642 14 17.25 14H2.75C2.33579 14 2 13.6642 2 13.25Z" />
    </svg>
  );
}

function CloseMenuIcon() {
  return (
    <svg data-slot="icon" viewBox="0 0 20 20" aria-hidden="true" className="w-5 h-5">
      <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
    </svg>
  );
}

function MobileScratchpad({ open, close, children }: { open: boolean; close: () => void; children: React.ReactNode }) {
  return (
    <Headless.Dialog open={open} onClose={close} className="xl:hidden">
      <Headless.DialogBackdrop
        transition
        className="fixed inset-0 bg-black/10 transition data-[closed]:opacity-0 data-[enter]:duration-300 data-[enter]:ease-out data-[leave]:duration-200 data-[leave]:ease-in z-40"
      />
      <Headless.DialogPanel
        transition
        className="fixed bg-black/25 backdrop-blur-2xl inset-y-0 right-0 w-full max-w-sm p-2 transition duration-300 ease-in-out data-[closed]:translate-x-full z-50"
      >
        <div className="flex h-full flex-col rounded-lg shadow-sm ring-1 ring-zinc-950/5 dark:bg-zinc-900 dark:ring-white/10">
          <div className="-mb-3 px-4 pt-3 flex items-center justify-between">
            <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">Scratchpad</h2>
            <Headless.CloseButton
              className="flex items-center gap-3 rounded-lg px-2 py-2.5 text-left text-base/6 font-medium text-zinc-950 hover:bg-zinc-950/5 dark:text-white dark:hover:bg-white/5"
              aria-label="Close scratchpad"
            >
              <CloseMenuIcon />
            </Headless.CloseButton>
          </div>
          {children}
        </div>
      </Headless.DialogPanel>
    </Headless.Dialog>
  );
}

function MobileSidebar({ open, close, children }: { open: boolean; close: () => void; children: React.ReactNode }) {
  return (
    <Headless.Dialog open={open} onClose={close} className="lg:hidden">
      <Headless.DialogBackdrop
        transition
        className="fixed inset-0 bg-black/30 transition data-[closed]:opacity-0 data-[enter]:duration-300 data-[enter]:ease-out data-[leave]:duration-200 data-[leave]:ease-in"
      />
      <Headless.DialogPanel
        transition
        className="fixed inset-y-0 w-full max-w-80 p-2 transition duration-300 ease-in-out data-[closed]:-translate-x-full"
      >
        <div className="flex h-full flex-col rounded-lg bg-white shadow-sm ring-1 ring-zinc-950/5 dark:bg-zinc-900 dark:ring-white/10">
          <div className="-mb-3 px-4 pt-3">
            <Headless.CloseButton
              className="flex items-center gap-3 rounded-lg px-2 py-2.5 text-left text-base/6 font-medium text-zinc-950 sm:py-2 sm:text-sm/5 data-[slot=icon]:*:size-6 data-[slot=icon]:*:shrink-0 sm:data-[slot=icon]:*:size-5 data-[slot=icon]:last:*:ml-auto data-[slot=icon]:last:*:size-5 sm:data-[slot=icon]:last:*:size-4 data-[slot=avatar]:*:-m-0.5 data-[slot=avatar]:*:size-7 data-[slot=avatar]:*:[--avatar-radius:theme(borderRadius.DEFAULT)] data-[slot=avatar]:*:[--ring-opacity:10%] sm:data-[slot=avatar]:*:size-6 data-[hover]:bg-zinc-950/5 data-[slot=icon]:*:data-[hover]:text-zinc-950 data-[active]:bg-zinc-950/5 data-[slot=icon]:*:data-[active]:text-zinc-950 dark:text-white dark:data-[slot=icon]:*:text-zinc-400 dark:data-[hover]:bg-white/5 dark:data-[slot=icon]:*:data-[hover]:text-white dark:data-[active]:bg-white/5 dark:data-[slot=icon]:*:data-[active]:text-white"
              aria-label="Close navigation"
            >
              <CloseMenuIcon />
            </Headless.CloseButton>
          </div>
          {children}
        </div>
      </Headless.DialogPanel>
    </Headless.Dialog>
  );
}

export function clientLoader() {
  // Check authentication
  const token = localStorage.getItem('auth_token');
  if (!token) {
    // Not authenticated, redirect to login
    throw new Response(null, {
      status: 302,
      headers: { Location: '/login' },
    });
  }
  return { token };
}

export default function AuthLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [authToken, setAuthToken] = useState<string | null>(() => {
    // Initialize from localStorage immediately
    return localStorage.getItem('auth_token');
  });
  const [darkMode, setDarkMode] = useState(false);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const [userData, setUserData] = useState<any>(null);
  const [showMobileSidebar, setShowMobileSidebar] = useState(false);
  const [showMobileScratchpad, setShowMobileScratchpad] = useState(false);
  const [isScratchpadCollapsed, setIsScratchpadCollapsed] = useState<boolean>(() => {
    // Initialize from localStorage
    const saved = localStorage.getItem('scratchpadCollapsed');
    return saved === 'true';
  });
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(() => {
    // Initialize from localStorage
    const saved = localStorage.getItem('sidebarCollapsed');
    return saved === 'true';
  });

  // Initialize dark mode
  useEffect(() => {
    if (!authToken) {
      navigate('/login');
      return;
    }

    // Initialize dark mode from localStorage or system preference
    const savedDarkMode = localStorage.getItem('darkMode');
    if (savedDarkMode !== null) {
      setDarkMode(savedDarkMode === 'true');
    } else {
      setDarkMode(window.matchMedia('(prefers-color-scheme: dark)').matches);
    }
  }, [navigate, authToken]);

  // Load user data
  useEffect(() => {
    if (!authToken) return;

    console.log('Loading user data with token:', authToken.substring(0, 20) + '...');
    const loadUserData = async () => {
      try {
        const response = await fetch('/api/auth/me', {
          headers: {
            'Authorization': `Bearer ${authToken}`
          }
        });

        console.log('User data response status:', response.status);
        if (response.ok) {
          const user = await response.json();
          console.log('Loaded user data:', user);
          setUserData(user);
        } else {
          console.error('Failed to load user data:', response.status, response.statusText);
        }
      } catch (error) {
        console.error('Failed to load user data:', error);
      }
    };

    loadUserData();
  }, [authToken]);

  // Derive current view from URL path (must be before useEffect that uses it)
  const currentView = location.pathname.startsWith('/dashboard')
    ? 'dashboard'
    : location.pathname.startsWith('/price-monitor')
      ? 'price-monitor'
      : location.pathname.startsWith('/settings')
        ? 'settings'
        : location.pathname.startsWith('/memory')
          ? 'memory'
          : location.pathname.startsWith('/notes')
            ? 'notes'
            : location.pathname.startsWith('/tasks')
              ? 'tasks'
              : location.pathname.startsWith('/cms')
                ? 'cms'
                : location.pathname.startsWith('/flock')
                  ? 'flock'
                  : location.pathname.startsWith('/admin/docs')
                    ? 'admin-docs'
                    : location.pathname.startsWith('/admin/users')
                      ? 'admin-users'
                      : location.pathname.startsWith('/admin/models')
                        ? 'admin-models'
                        : 'chat';

  // Apply dark mode to document
  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode);
    localStorage.setItem('darkMode', String(darkMode));
  }, [darkMode]);

  // Update page title based on current view
  useEffect(() => {
    const titleMap = {
      'chat': 'EspressoBot',
      'dashboard': 'Dashboard - EspressoBot',
      'price-monitor': 'Price Monitor - EspressoBot',
      'settings': 'Settings - EspressoBot',
      'memory': 'Memory Management - EspressoBot',
      'notes': 'Notes - Second Brain - EspressoBot',
      'tasks': 'Tasks - EspressoBot',
      'cms': 'Content CMS - EspressoBot',
      'flock': 'Flock Digest - EspressoBot',
      'admin-docs': 'Documentation Admin - EspressoBot',
      'admin-users': 'User & Role Management - EspressoBot',
      'admin-models': 'AI Model Management - EspressoBot',
    };
    document.title = titleMap[currentView] || 'EspressoBot';
  }, [currentView]);

  const handleLogout = useCallback(() => {
    localStorage.removeItem('auth_token');
    setAuthToken(null);
    navigate('/login');
  }, [navigate]);


  const handleConversationChange = useCallback(() => {
    setSidebarRefresh(prev => prev + 1);
  }, []);

  const toggleScratchpad = useCallback(() => {
    setIsScratchpadCollapsed(prev => {
      const newValue = !prev;
      localStorage.setItem('scratchpadCollapsed', String(newValue));
      return newValue;
    });
  }, []);

  const toggleSidebar = useCallback(() => {
    setIsSidebarCollapsed(prev => {
      const newValue = !prev;
      localStorage.setItem('sidebarCollapsed', String(newValue));
      return newValue;
    });
  }, []);

  if (!authToken) {
    return null; // Will redirect via clientLoader
  }

  const sidebarContent = (
    <Sidebar
      authToken={authToken}
      refreshTrigger={sidebarRefresh}
      onLogout={handleLogout}
      currentView={currentView}
      user={{
        name: userData?.name || 'User',
        email: userData?.email || 'user@example.com',
        avatarUrl: userData?.picture || null,
        permissions: userData?.permissions || []
      }}
      isCollapsed={isSidebarCollapsed}
      onToggleCollapse={toggleSidebar}
    />
  );

  return (
    <div className="relative isolate flex min-h-svh w-full bg-white max-lg:flex-col lg:bg-zinc-100 dark:bg-zinc-900 dark:lg:bg-zinc-950">
      {/* Sidebar on desktop */}
      <div className={`fixed inset-y-0 z-10 left-0 transition-all duration-300 ${isSidebarCollapsed ? 'w-20' : 'w-64'} max-lg:hidden`}>
        {sidebarContent}
      </div>

      {/* Sidebar on mobile */}
      <MobileSidebar open={showMobileSidebar} close={() => setShowMobileSidebar(false)}>
        {sidebarContent}
      </MobileSidebar>

      {/* Scratchpad on mobile */}
      <MobileScratchpad open={showMobileScratchpad} close={() => setShowMobileScratchpad(false)}>
        <ScratchpadPanel />
      </MobileScratchpad>

      {/* Navbar on mobile */}
      <header className="flex items-center px-4 lg:hidden fixed top-2 left-2 z-30">
        <div className="py-2.5">
          <button
            onClick={() => setShowMobileSidebar(true)}
            className="flex items-center gap-3 rounded-lg px-2 py-2.5 text-left text-base/6 font-medium text-zinc-950 hover:bg-zinc-950/5 dark:text-white dark:hover:bg-white/5"
            aria-label="Open navigation"
          >
            <OpenMenuIcon />
          </button>
        </div>
      </header>

      {/* Content */}
      <main className={`flex flex-1 flex-col pb-2 lg:min-w-0 min-h-0 h-full lg:pt-2 ${isScratchpadCollapsed ? 'lg:pr-14' : 'xl:pr-[21rem]'} ${isSidebarCollapsed ? 'lg:pl-20' : 'lg:pl-64'} transition-all duration-300`}>
        <div className="grow flex max-lg:flex-col lg:rounded-lg lg:bg-white lg:shadow-xs lg:ring-1 lg:ring-zinc-950/5 dark:lg:bg-zinc-900 dark:lg:ring-white/10">
          {/* Main content area with chat */}
          <div className="flex-1 flex flex-col min-h-0 h-full">
            <Outlet context={{
              authToken,
              user: userData,
              setUser: setUserData,
              onConversationChange: handleConversationChange
            }} />
          </div>
        </div>
      </main>

      {/* Floating Action Buttons - Mobile/Tablet only, and only on chat routes */}
      {currentView === 'chat' && (
        <>
          {/* New Chat Button */}
          <button
            onClick={() => {
              const newThreadId = `thread_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
              navigate(`/chat/${newThreadId}`);
            }}
            className="xl:hidden fixed top-4 right-16 z-30 p-2.5 bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 rounded-full shadow-lg hover:shadow-xl transition-all duration-200 hover:scale-110 active:scale-95"
            aria-label="Start new chat"
            title="Start new chat"
          >
            <svg data-slot="icon" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="w-5 h-5">
              <path d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z" />
            </svg>
          </button>

          {/* Scratchpad Button */}
          <button
            onClick={() => setShowMobileScratchpad(true)}
            className="xl:hidden fixed top-4 right-4 z-30 p-2.5 bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 rounded-full shadow-lg hover:shadow-xl transition-all duration-200 hover:scale-110 active:scale-95"
            aria-label="Open scratchpad"
            title="Open scratchpad"
          >
            <svg data-slot="icon" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className="w-5 h-5">
              <path d="M5.433 13.917l1.262-3.155A4 4 0 017.58 9.42l6.92-6.918a2.121 2.121 0 013 3l-6.92 6.918c-.383.383-.84.685-1.343.886l-3.154 1.262a.5.5 0 01-.65-.65z" />
              <path d="M3.5 5.75c0-.69.56-1.25 1.25-1.25H10A.75.75 0 0010 3H4.75A2.75 2.75 0 002 5.75v9.5A2.75 2.75 0 004.75 18h9.5A2.75 2.75 0 0017 15.25V10a.75.75 0 00-1.5 0v5.25c0 .69-.56 1.25-1.25 1.25h-9.5c-.69 0-1.25-.56-1.25-1.25v-9.5z" />
            </svg>
          </button>
        </>
      )}

      {/* Scratchpad Sidebar - Fixed Right (Hidden on mobile/tablet, visible on xl+) */}
      <div className={`z-20 hidden xl:block fixed inset-y-0 right-0 transition-all duration-300 ${isScratchpadCollapsed ? 'w-12' : 'w-80'} border-l border-zinc-200 dark:border-zinc-800 overflow-hidden bg-white dark:bg-zinc-900`}>
        {isScratchpadCollapsed ? (
          /* Collapsed State - Show expand button */
          <button
            onClick={toggleScratchpad}
            className="absolute top-4 left-2 p-2 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md transition-colors"
            title="Expand Scratchpad"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
        ) : (
          /* Expanded State - Show scratchpad with collapse button */
          <>
            <button
              onClick={toggleScratchpad}
              className="absolute top-4 right-4 z-10 p-1.5 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md transition-colors"
              title="Collapse Scratchpad"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
            <ScratchpadPanel />
          </>
        )}
      </div>
    </div>
  );
}
