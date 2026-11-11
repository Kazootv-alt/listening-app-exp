const C='exp-shell-1';
self.addEventListener('install',e=>{self.skipWaiting()});
self.addEventListener('activate',e=>{e.waitUntil((async()=>{for(const k of await caches.keys())if(k.startsWith('exp-')&&k!==C)await caches.delete(k);await self.clients.claim()})())});
self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(u.origin!==location.origin||!u.pathname.includes('/listening-app-exp/'))return;
 e.respondWith((async()=>{const c=await caches.open(C);const m=await c.match(e.request,{ignoreSearch:true});
  const net=fetch(e.request).then(r=>{if(r.ok)c.put(e.request,r.clone());return r}).catch(()=>m);
  return m&&!/\.html$|\/$|tracks\.json|index\.json/.test(u.pathname)?m:(await net)||m})())});
