const CACHE = "viperai-v2";
const STATIC = ["/", "/static/css/style.css", "/static/js/script.js"];

self.addEventListener("install", e => {
    e.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC)));
    self.skipWaiting();
});

self.addEventListener("activate", e => {
    e.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener("fetch", e => {
    const { request } = e;
    const url = new URL(request.url);

    // Let API and auth requests always go to network
    if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/chat") ||
        url.pathname.startsWith("/login") || url.pathname.startsWith("/logout")) {
        e.respondWith(fetch(request));
        return;
    }

    // Navigation requests → serve app shell from cache
    if (request.mode === "navigate") {
        e.respondWith(
            fetch(request).catch(() => caches.match("/"))
        );
        return;
    }

    // Static assets → cache first, fallback to network
    e.respondWith(
        caches.match(request).then(cached => cached || fetch(request).then(res => {
            const clone = res.clone();
            caches.open(CACHE).then(c => c.put(request, clone));
            return res;
        }))
    );
});
