# PWA (Progressive Web App) Features

EspressoBot is now a fully functional Progressive Web App with offline support and installability.

## Features

### 📱 Installable
- Users can install the app on desktop and mobile devices
- Appears in app drawer/home screen
- Launches in standalone mode (no browser UI)
- Custom app icons and splash screens

### 🔄 Offline Support
- Service worker caches all app assets
- Works offline after first visit
- Automatic updates when new version is available
- Smart caching strategies:
  - **Google Fonts**: Cached for 1 year (CacheFirst)
  - **API Calls**: Network-first with 5-minute cache fallback
  - **App Assets**: Precached for instant loading

### 🎨 App Manifest
- **Name**: EspressoBot - AI Assistant for Shopify
- **Theme Color**: #1f2937 (dark gray)
- **Background**: #ffffff (white)
- **Display**: Standalone
- **Icons**: 8 sizes (72x72 to 512x512)

### ⚡ Features
1. **Auto-Update**: Service worker automatically updates when new version is available
2. **Install Prompt**: Appears 5 seconds after page load (dismissible)
3. **Update Notifications**: Toast notification when new content is available
4. **Shortcuts**: Quick access to New Chat, Dashboard, and CMS

## Installation

### Desktop (Chrome/Edge)
1. Visit the app in Chrome or Edge
2. Click the install icon in the address bar (⊕)
3. Or wait for the install prompt to appear
4. Click "Install"

### Mobile (iOS)
1. Visit the app in Safari
2. Tap the Share button
3. Tap "Add to Home Screen"
4. Tap "Add"

### Mobile (Android)
1. Visit the app in Chrome
2. Tap the menu (⋮)
3. Tap "Install app" or "Add to Home screen"
4. Tap "Install"

## Technical Details

### Build Configuration
- **Plugin**: vite-plugin-pwa v1.1.0
- **Strategy**: generateSW (Workbox)
- **Registration**: Auto-update
- **Precached Files**: 84 entries (~3.5 MB)

### Caching Strategy
```javascript
{
  // Google Fonts: Cache first, 1 year expiration
  'https://fonts.googleapis.com/*': CacheFirst,
  'https://fonts.gstatic.com/*': CacheFirst,

  // API calls: Network first with 5-minute fallback
  '/api/*': NetworkFirst (10s timeout, 50 entry limit)
}
```

### Files Added
- `/frontend-v2/public/manifest.json` - PWA manifest with app metadata
- `/frontend-v2/public/icons/` - App icons (8 sizes)
- `/frontend-v2/app/components/PWAHandler.tsx` - Service worker registration & update UI
- `/frontend-v2/app/components/PWAInstallPrompt.tsx` - Install prompt UI

### Files Modified
- `/frontend-v2/vite.config.js` - Added VitePWA plugin configuration
- `/frontend-v2/app/root.tsx` - Added manifest link, PWA meta tags, and components

## Development

### Running in Dev Mode
The PWA is enabled in development mode for testing:
```bash
pnpm dev
```

### Building for Production
```bash
pnpm build
```

The service worker (`sw.js`) and workbox runtime are generated automatically during build.

### Testing PWA
1. Build the app: `pnpm build`
2. Serve the build: `pnpm start`
3. Open Chrome DevTools → Application → Service Workers
4. Verify service worker is registered and running
5. Check manifest: Application → Manifest

### Debugging
- **Service Worker**: Chrome DevTools → Application → Service Workers
- **Cache Storage**: Chrome DevTools → Application → Cache Storage
- **Manifest**: Chrome DevTools → Application → Manifest
- **Install Prompt**: Appears 5s after page load (check console for errors)

## Browser Support
- ✅ Chrome/Edge (Desktop & Mobile)
- ✅ Firefox (Desktop & Mobile)
- ✅ Safari (iOS & macOS)
- ✅ Samsung Internet
- ⚠️ Older browsers: Falls back to regular web app

## Lighthouse PWA Score
The app should score 100/100 on Lighthouse PWA audit with:
- ✅ Installable
- ✅ Works offline
- ✅ HTTPS (production)
- ✅ Configured for a custom splash screen
- ✅ Sets a theme color
- ✅ Provides a valid web app manifest
- ✅ Has a registered service worker

## Future Enhancements
- [ ] Add actual screenshots to manifest (currently using placeholders)
- [ ] Implement background sync for offline form submissions
- [ ] Add push notifications support
- [ ] Improve icon quality (currently using favicon as placeholder)
- [ ] Add app shortcuts for common actions
- [ ] Implement share target API for sharing content to the app
