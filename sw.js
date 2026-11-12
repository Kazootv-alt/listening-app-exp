const C='exp-shell-2';
self.addEventListener('install',e=>{self.skipWaiting()});
self.addEventListener('activate',e=>{e.waitUntil((async()=>{for(const k of await caches.keys())if(k.startsWith('exp-')&&k!==C)await caches.delete(k);await self.clients.claim()})())});
/* 音声（mp3）と途中取得（Range）は触らない：Safariの音声再生は部分取得が前提で、ここで横取りすると再生が止まることがあるため。
   画面のファイルと英文一覧（.json）は、ネットを先に見て、つながらない時だけ保存分を使う */
self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(u.origin!==location.origin||!u.pathname.includes('/listening-app-exp/'))return;
 if(/\.mp3$/.test(u.pathname)||e.request.headers.has('range'))return;
 e.respondWith((async()=>{const c=await caches.open(C);const m=await c.match(e.request,{ignoreSearch:true});
  const net=fetch(e.request).then(r=>{if(r.ok&&r.status===200)c.put(e.request,r.clone()).catch(()=>{});return r}).catch(()=>m);
  return m&&!/\.html$|\/$|\.json$|\.webmanifest$/.test(u.pathname)?m:(await net)||m})())});
