const C='tt-v3',S=['./','./index.html','./manifest.json','./icon-192.png','https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css','https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js'];
self.addEventListener('install',e=>e.waitUntil(caches.open(C).then(c=>c.addAll(S)).then(()=>self.skipWaiting())));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==C).map(x=>caches.delete(x)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{const u=new URL(e.request.url);
  if(u.hostname.includes('weather.gov')||u.hostname.includes('mesonet')||u.hostname.includes('noaa.gov')||e.request.method!=='GET')return;
  if(u.origin===location.origin)e.respondWith(fetch(e.request).then(r=>{const k=r.clone();caches.open(C).then(c=>c.put(e.request,k));return r}).catch(()=>caches.match(e.request)));
  else e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)))});
