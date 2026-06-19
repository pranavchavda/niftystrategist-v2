// Web Push handlers, importScripts'd into the Workbox-generated service worker
// (see vite.config.js workbox.importScripts). Keep dependency-free — this runs
// in the SW global scope. See docs/plans/2026-06-19-web-push-notifications.md.

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { body: event.data ? event.data.text() : "" };
  }

  const title = data.title || "Nifty Strategist";
  const options = {
    body: data.body || "",
    tag: data.tag || undefined, // same tag collapses repeated fires
    data: { url: data.url || "/" },
    icon: "/icons/icon-192x192.png",
    badge: "/icons/icon-96x96.png",
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/";

  event.waitUntil(
    (async () => {
      const allClients = await self.clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      });
      // Focus an existing tab if one is open, then navigate it.
      for (const client of allClients) {
        if ("focus" in client) {
          await client.focus();
          if ("navigate" in client && target !== "/") {
            try {
              await client.navigate(target);
            } catch (e) {
              /* cross-origin or detached — fall through to openWindow */
            }
          }
          return;
        }
      }
      if (self.clients.openWindow) {
        await self.clients.openWindow(target);
      }
    })()
  );
});
