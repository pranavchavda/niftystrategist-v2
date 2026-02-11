import { useNavigate } from 'react-router';
import { useEffect, useState, useMemo, useRef } from 'react';
import {
  ChartBarIcon,
  CpuChipIcon,
  Cog6ToothIcon,
  QuestionMarkCircleIcon,
  ArrowRightStartOnRectangleIcon,
  BookOpenIcon,
  CheckBadgeIcon,
  PhotoIcon,
  PaperClipIcon,
  XMarkIcon,
  ArrowTrendingUpIcon,
  WalletIcon,
} from '@heroicons/react/24/outline';
import ChatInput from '../components/ChatInput';
const ChatInputAny = ChatInput as any;
import { decodeJWT } from '../utils/route-permissions';

// TODO: Replace with trading logo
const logo = new URL('../assets/eblogo-notext.webp', import.meta.url).href;

const sections = [
  {
    title: 'Dashboard',
    description:
      'Portfolio overview, positions, and P&L tracking.',
    icon: ChartBarIcon,
    href: '/dashboard',
    permission: 'dashboard.access',
  },
  {
    title: 'Tasks',
    description:
      'AI-powered task management for trading activities.',
    icon: CheckBadgeIcon,
    href: '/tasks',
    permission: 'notes.access',
  },
  {
    title: 'Memory',
    description:
      'Trading preferences, risk tolerance, and learned patterns.',
    icon: CpuChipIcon,
    href: '/memory',
    permission: 'memory.access',
  },
  {
    title: 'Notes',
    description:
      'Personal knowledge base for trading research and analysis.',
    icon: BookOpenIcon,
    href: '/notes',
    permission: 'notes.access',
  },
  {
    title: 'Settings',
    description:
      'Customize trading preferences and AI models.',
    icon: Cog6ToothIcon,
    href: '/settings',
    permission: 'settings.access',
  },
];

interface LandingStats {
  toolsCount: number;
  docsCount: number;
}

export default function Index() {
  const navigate = useNavigate();
  const [mounted, setMounted] = useState(false);
  const [userName, setUserName] = useState('User');
  const [stats, setStats] = useState<LandingStats>({
    toolsCount: 17,
    docsCount: 10,
  });
  const [initialMessage, setInitialMessage] = useState('');
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [attachedImages, setAttachedImages] = useState<File[]>([]);
  const newTaskInputRef = useRef<HTMLTextAreaElement>(null);

  // Trigger mount animations
  useEffect(() => {
    setMounted(true);
  }, []);

  // Get user permissions and name
  const userPermissions = useMemo(() => {
    const token = localStorage.getItem('auth_token');
    if (!token) return null;

    const payload = decodeJWT(token);
    // Set user name if available
    if (payload?.name) {
      setUserName(payload.name);
    } else if (token.startsWith('dev-')) {
      setUserName('Developer');
    }

    return payload?.permissions || [];
  }, [userName]);

  // Greeting logic
  const greeting = useMemo(() => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Good evening';
  }, []);

  // Filter sections
  const visibleSections = useMemo(() => {
    if (!userPermissions) return [];
    return sections.filter(section =>
      userPermissions.includes(section.permission)
    );
  }, [userPermissions]);

  const isLoggedIn = userPermissions !== null;
  const isPendingActivation = isLoggedIn && visibleSections.length === 0 && !userPermissions.includes('chat.access');

  useEffect(() => {
    // Fetch stats
    fetch('/api/stats/landing')
      .then((res) => res.json())
      .then((data) => setStats(data))
      .catch((err) => console.warn('Failed to fetch stats:', err));
  }, []);

  const handleNewTask = (message?: string, files: File[] = [], images: File[] = []) => {
    const newThreadId = `thread_${Date.now()}`;
    const target = `/chat/${newThreadId}`;

    // Prepare navigation state with message and attachments
    const navigationState: any = {};
    if (typeof message === 'string' && message.trim()) {
      navigationState.initialMessage = message;
    }
    if (files.length > 0) navigationState.initialFiles = files;
    if (images.length > 0) navigationState.initialImages = images;

    if (Object.keys(navigationState).length > 0) {
      navigate(target, { state: navigationState });
    } else {
      navigate(target);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    navigate('/login');
  };

  const handleLogin = () => {
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 font-sans text-zinc-900 dark:text-zinc-100 selection:bg-blue-500/30">
      {/* Background Gradients - Subtle */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-blue-500/5 rounded-full blur-[100px] -translate-y-1/2 translate-x-1/2" />
        <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-zinc-500/5 rounded-full blur-[100px] translate-y-1/2 -translate-x-1/2" />
      </div>

      {/* Header */}
      <header className="sticky top-0 z-50 w-full backdrop-blur-xl bg-white/70 dark:bg-zinc-900/70 border-b border-zinc-200/50 dark:border-zinc-800/50 transition-all">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ArrowTrendingUpIcon className="h-8 w-8 text-blue-600 dark:text-blue-400" />
            <span className="text-lg tracking-tight text-transparent bg-clip-text bg-gradient-to-b from-zinc-900 to-zinc-400 font-bold dark:from-zinc-100 dark:to-zinc-600">Nifty Strategist</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate('/help')}
              className="p-2 text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-all"
              title="Help"
            >
              <QuestionMarkCircleIcon className="w-5 h-5" />
            </button>

            {isLoggedIn ? (
              <button
                onClick={handleLogout}
                className="p-2 text-zinc-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/10 rounded-lg transition-all"
                title="Logout"
              >
                <ArrowRightStartOnRectangleIcon className="w-5 h-5" />
              </button>
            ) : (
              <button
                onClick={handleLogin}
                className="ml-2 px-4 py-2 bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 rounded-full text-sm font-medium hover:opacity-90 shadow-sm transition-all"
              >
                Login
              </button>
            )}
          </div>
        </div>
      </header>

      <main
        className="relative z-10 max-w-6xl mx-auto px-6 py-10"
        style={{
          opacity: mounted ? 1 : 0,
          transform: mounted ? 'translateY(0)' : 'translateY(10px)',
          transition: 'opacity 500ms ease-out, transform 500ms ease-out'
        }}
      >
        {isLoggedIn ? (
          <div className="flex flex-col gap-10">
            {/* Greeting & Hero */}
            <div className="flex flex-col gap-6 md:flex-row md:items-end justify-between">
              <div>
                <h1 className="text-3xl sm:text-4xl font-bold tracking-tight bg-gradient-to-t from-zinc-900 to-zinc-500 dark:from-white dark:to-zinc-400 bg-clip-text text-transparent mb-2">
                  {greeting}, {userName}.
                </h1>
                {!isPendingActivation && (
                  <p className="mt-2 text-lg text-zinc-500 dark:text-zinc-400">
                    What would you like to analyze today?
                  </p>
                )}
              </div>
            </div>

            {isPendingActivation ? (
              /* Pending Activation Banner */
              <div className="p-6 bg-slate-50 dark:bg-slate-900/30 rounded-xl border border-slate-200 dark:border-slate-700/50">
                <div className="flex items-start gap-4">
                  <div className="p-2 bg-slate-100 dark:bg-slate-800 rounded-lg flex-shrink-0">
                    <ArrowTrendingUpIcon className="w-6 h-6 text-slate-500 dark:text-slate-400" />
                  </div>
                  <div>
                    <p className="text-base font-semibold text-slate-800 dark:text-slate-200">Your account is pending activation.</p>
                    <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                      Contact Pranav to enable your account.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <>
                {/* Main Action Bar */}
                {userPermissions.includes('chat.access') && (
                  <div className="flex flex-col gap-4">
                    {/* Attachment Previews */}
                    {(attachedFiles.length > 0 || attachedImages.length > 0) && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-2 animate-in fade-in slide-in-from-bottom-2 duration-300">
                        {attachedImages.map((image, index) => (
                          <div key={`image-${index}`} className="flex items-center justify-between p-3 bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 shadow-sm">
                            <div className="flex items-center space-x-3 truncate">
                              <div className="p-2 rounded-lg bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 flex-shrink-0">
                                <PhotoIcon className="w-4 h-4" />
                              </div>
                              <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300 truncate">
                                {image.name}
                              </span>
                            </div>
                            <button
                              onClick={() => setAttachedImages(prev => prev.filter((_, i) => i !== index))}
                              className="p-1 text-zinc-400 hover:text-red-500 transition-colors"
                            >
                              <XMarkIcon className="w-4 h-4" />
                            </button>
                          </div>
                        ))}
                        {attachedFiles.map((file, index) => (
                          <div key={`file-${index}`} className="flex items-center justify-between p-3 bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 shadow-sm">
                            <div className="flex items-center space-x-3 truncate">
                              <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 flex-shrink-0">
                                <PaperClipIcon className="w-4 h-4" />
                              </div>
                              <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300 truncate">
                                {file.name}
                              </span>
                            </div>
                            <button
                              onClick={() => setAttachedFiles(prev => prev.filter((_, i) => i !== index))}
                              className="p-1 text-zinc-400 hover:text-red-500 transition-colors"
                            >
                              <XMarkIcon className="w-4 h-4" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}

                    <ChatInputAny
                      ref={newTaskInputRef}
                      value={initialMessage}
                      onChange={setInitialMessage}
                      onSubmit={() => handleNewTask(initialMessage, attachedFiles, attachedImages)}
                      onFileAttach={(files: File[]) => {
                        const images = files.filter((f: File) => f.type.startsWith('image/'));
                        const docs = files.filter((f: File) => !f.type.startsWith('image/'));
                        setAttachedImages(prev => [...prev, ...images]);
                        setAttachedFiles(prev => [...prev, ...docs]);
                      }}
                      placeholder="Analyze RELIANCE, check my portfolio, find swing trades..."
                      authToken={localStorage.getItem('auth_token')}
                    />
                  </div>
                )}

                {/* Applications Grid */}
                {visibleSections.length > 0 && (
                  <div className="pt-4">
                    <h2 className="text-sm font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-5">Applications</h2>
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
                      {visibleSections.map((section) => (
                        <button
                          key={section.href}
                          onClick={() => navigate(section.href)}
                          className="group flex flex-col items-start p-5 h-full bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-700 hover:shadow-md transition-all duration-200 text-left cursor-pointer"
                        >
                          <div className="mb-3 p-2 bg-zinc-50 dark:bg-zinc-800 rounded-lg text-zinc-500 dark:text-zinc-400 group-hover:text-zinc-900 dark:group-hover:text-zinc-100 group-hover:bg-zinc-100 dark:group-hover:bg-zinc-700/50 transition-colors">
                            <section.icon className="w-6 h-6" />
                          </div>
                          <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 mb-1 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                            {section.title}
                          </h3>
                          <p className="text-xs text-zinc-500 dark:text-zinc-500 line-clamp-2">
                            {section.description}
                          </p>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Paper Trading Notice */}
                <div className="mt-4 p-4 bg-amber-50 dark:bg-amber-900/20 rounded-xl border border-amber-200 dark:border-amber-800/50">
                  <div className="flex items-start gap-3">
                    <WalletIcon className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-amber-800 dark:text-amber-200">Paper Trading Mode</p>
                      <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
                        You're using simulated trading with virtual funds. Connect Upstox in Settings for live trading.
                      </p>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        ) : (
          <div className=" md:py-10 flex flex-col items-center justify-center text-center">
            <div className="w-full h-full md:pt-20 md:pb-10 my-8 bg-gradient-to-br from-zinc-900 to-zinc-700 dark:from-white dark:to-zinc-300 rounded-2xl flex justify-center shadow-2xl transform rotate-3">
              <ArrowTrendingUpIcon className="w-12 h-12 text-white dark:text-zinc-900" />
            </div>
            <h1 className="text-4xl font-bold text-zinc-900 dark:text-white mb-4">Welcome to Nifty Strategist</h1>
            <p className="text-xl text-zinc-600 dark:text-zinc-400 max-w-md mb-10 leading-relaxed">
              AI-powered trading assistant for Indian stock markets (NSE/BSE).
            </p>
            <button
              onClick={handleLogin}
              className="px-8 py-3 bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 rounded-full font-semibold text-lg shadow-lg hover:shadow-xl hover:-translate-y-1 transition-all"
            >
              Get Started
            </button>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="mt-auto py-8 text-center bg-white/50 dark:bg-zinc-900/50 border-t border-zinc-200/50 dark:border-zinc-800/50">
        <p className="text-xs text-zinc-400 dark:text-zinc-600">
          Nifty Strategist v2.0 - AI Trading Assistant
        </p>
      </footer>
    </div>
  );
}

// React router Meta function
export function meta() {
  return [
    { title: "Nifty Strategist - AI Trading Assistant" },
    { name: "description", content: "AI-powered trading assistant for Indian stock markets" }
  ];
}
