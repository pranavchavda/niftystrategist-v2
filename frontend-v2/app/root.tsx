import {
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
} from 'react-router';
import type { LinksFunction } from 'react-router';
import { PWAHandler } from './components/PWAHandler';
import { PWAInstallPrompt } from './components/PWAInstallPrompt';
import { ThemeProvider } from './context/ThemeContext';

import './index.css';
import './tailwind-fixes.css';

// Inline script to prevent flash of wrong theme
// This runs before React hydrates to set the correct theme class
const themeScript = `
(function() {
  try {
    var theme = localStorage.getItem('nifty-strategist-theme') || 'system';
    var isDark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    if (isDark) {
      document.documentElement.classList.add('dark');
      document.documentElement.style.colorScheme = 'dark';
    } else {
      document.documentElement.classList.remove('dark');
      document.documentElement.style.colorScheme = 'light';
    }
  } catch (e) {}
})();
`;

export const links: LinksFunction = () => [
  { rel: 'icon', href: '/eblogo-notext.webp', type: 'image/webp' },
  { rel: 'manifest', href: '/manifest.json' },
  { rel: 'apple-touch-icon', href: '/icons/icon-192x192.png' },
  { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
  {
    rel: 'preconnect',
    href: 'https://fonts.gstatic.com',
    crossOrigin: 'anonymous',
  },
];

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />

        {/* Theme script - runs before page renders to prevent flash */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />

        {/* PWA Meta Tags */}
        <meta name="theme-color" content="#1f2937" />
        <meta name="description" content="AI-powered trading assistant for the Indian stock market (NSE/BSE). Analyze stocks, track portfolios, and execute trades with intelligent recommendations." />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="apple-mobile-web-app-title" content="Nifty Strategist" />

        <Meta />
        <Links />
      </head>
      <body className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 antialiased">
        <ThemeProvider>
          {children}
        </ThemeProvider>
        <PWAHandler />
        <PWAInstallPrompt />
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function Root() {
  return <Outlet />;
}
