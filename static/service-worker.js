// Bump CACHE whenever the shipped static assets change — the activate handler
// deletes every other cache, so the new version wins.
const CACHE = "viperai-v5";
const STATIC = ["/", "/static/css/style.css", "/static/js/script.js"];

self.addEventListener("install", e => {
    e.waitUntil(
        caches.open(CACHE).then(c => c.addAll(STATIC)).then(() => self.skipWaiting())
    );
});

self.addEventListener("activate", e => {
    e.waitUntil(
        caches.keys()
            .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
            .then(() => self.clients.claim())
    );
});

self.addEventListener("fetch", e => {
    const { request } = e;

    // Only GET is cacheable; POST/DELETE must always hit the network.
    if (request.method !== "GET") return;

    const url = new URL(request.url);

    // Never serve app data from the cache.
    if (url.origin !== self.location.origin ||
        url.pathname.startsWith("/api/") || url.pathname.startsWith("/chat") ||
        url.pathname.startsWith("/login") || url.pathname.startsWith("/logout")) {
        e.respondWith(fetch(request));
        return;
    }

    if (request.mode === "navigate") {
        e.respondWith(fetch(request).catch(() => caches.match("/")));
        return;
    }

    e.respondWith(
        caches.match(request).then(cached => cached || fetch(request).then(res => {
            if (res && res.ok && res.type === "basic") {
                const clone = res.clone();
                caches.open(CACHE).then(c => c.put(request, clone));
            }
            return res;
        }))
    );
});
