import { useEffect, useState } from 'react';

export function PWAHandler() {
  const [showReload, setShowReload] = useState(false);
  const [offlineReady, setOfflineReady] = useState(false);

  useEffect(() => {
    // Only run in browser
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
      return;
    }

    let updateServiceWorker: ((reloadPage?: boolean) => Promise<void>) | null = null;

    // Dynamically import and register SW
    const registerSW = async () => {
      try {
        const { registerSW: register } = await import('virtual:pwa-register');

        updateServiceWorker = register({
          immediate: true,
          onRegistered(registration) {
            console.log('SW Registered:', registration);
          },
          onRegisterError(error) {
            console.error('SW registration error:', error);
          },
          onOfflineReady() {
            setOfflineReady(true);
          },
          onNeedRefresh() {
            setShowReload(true);
          },
        });
      } catch (error) {
        console.warn('PWA register module not available:', error);
      }
    };

    registerSW();

    // Cleanup
    return () => {
      updateServiceWorker = null;
    };
  }, []);

  const close = () => {
    setOfflineReady(false);
    setShowReload(false);
  };

  const reload = async () => {
    try {
      const { registerSW } = await import('virtual:pwa-register');
      const updateSW = registerSW({
        immediate: true,
        onNeedRefresh() {},
        onOfflineReady() {},
      });
      await updateSW(true);
    } catch (error) {
      console.error('Error updating service worker:', error);
      window.location.reload();
    }
  };

  if (!offlineReady && !showReload) {
    return null;
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 max-w-md">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex items-start gap-3">
          <div className="flex-1">
            {offlineReady ? (
              <p className="text-sm text-gray-700 dark:text-gray-300">
                App ready to work offline
              </p>
            ) : (
              <p className="text-sm text-gray-700 dark:text-gray-300">
                New content available, click reload to update
              </p>
            )}
          </div>
          <button
            onClick={close}
            className="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300"
            aria-label="Close"
          >
            <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>
        {showReload && (
          <div className="mt-3">
            <button
              onClick={reload}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2 px-4 rounded-md transition-colors"
            >
              Reload
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
