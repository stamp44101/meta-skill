// adlib.js — paste the whole file into javascript_tool after every navigation (the Ad Library's CSP now blocks eval,
// so the old window.name + eval install no longer works; window.name is used by geo.js for data instead). Installs window.MA. Every call returns compact JSON and never returns URLs or base64
// (the Chrome extension blocks query strings and long encoded data in tool results).
// Keep each call under ~40 s: the tool times out at 45 s.
(() => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const MON = { Jan:0, Feb:1, Mar:2, Apr:3, May:4, Jun:5, Jul:6, Aug:7, Sep:8, Oct:9, Nov:10, Dec:11 };
  const iso = s => { const m = (s || '').match(/(\d{1,2}) (\w{3}) (\d{4})/); if (!m) return '';
    const d = new Date(Date.UTC(+m[3], MON[m[2]], +m[1])); return d.toISOString().slice(0, 10); };

  // The smallest element holding exactly one "Library ID: n" inside root.
  function cardOf(node, root) {
    let e = node.parentElement;
    // textContent, not innerText: innerText forces layout and freezes the tab past ~100 cards
    while (e.parentElement && e.parentElement !== root &&
           e.parentElement.textContent.split('Library ID:').length === 2) e = e.parentElement;
    return e;
  }
  function cards(root = document.body) {
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT,
      { acceptNode: n => /Library ID: \d+/.test(n.nodeValue) ? 1 : 3 });
    const out = new Map();
    while (w.nextNode()) {
      const id = w.currentNode.nodeValue.match(/Library ID: (\d+)/)[1];
      if (!out.has(id)) out.set(id, cardOf(w.currentNode, root));
    }
    return out;
  }
  const mainCards = () => { // skip cards inside an open dialog
    const m = cards(); for (const [id, c] of m) if (c.closest('[role=dialog]')) m.delete(id); return m; };

  function parse(id, c) {
    const t = c.innerText, lines = t.split('\n').map(s => s.trim()).filter(s => s && s !== '​');
    const range = t.match(/(\d{1,2} \w{3} \d{4}) - (\d{1,2} \w{3} \d{4})/);
    const start = iso(range ? range[1] : (t.match(/Started running on ([^\n]+)/) || [])[1]);
    const end = range ? iso(range[2]) : '';
    const n = +((t.match(/(\d+) ads? use this creative/) || [])[1] || 1);
    const si = lines.indexOf('Sponsored');
    const pageLink = [...c.querySelectorAll('a')].map(a => (a.href.match(/facebook\.com\/(\d{6,})\/?$/) || [])[1]).find(Boolean);
    const vids = c.querySelectorAll('video').length;
    const imgs = [...c.querySelectorAll('img')].filter(i => i.naturalWidth > 100).length;
    const media = vids + imgs;
    const format = media > 1 ? (vids ? 'carousel-video' : 'carousel') : vids ? 'video' : imgs ? 'image' : 'text';
    // body = lines after the advertiser/Sponsored block until the first media/time/CTA marker
    const body = [];
    for (let i = si + 1; i < lines.length && body.join(' ').length < 400; i++) {
      if (/^0:00 \/|^[A-Z0-9.-]+\.[A-Z]{2,}$|^(Shop now|Learn more|Send message|Order now|Sign up|Book now|Get offer|Shop Now)$/.test(lines[i])) break;
      body.push(lines[i]);
    }
    const cta = lines.find(l => /^(Shop now|Learn more|Send message|Order now|Sign up|Book now|Get offer|Send WhatsApp message|Contact us|See menu|Watch more)$/.test(l)) || '';
    return { id, status: /^​?\s*Active/.test(t.trim()) || /\nActive\n/.test('\n' + t) ? 'active' : 'ended',
      start, end, advertiser: si > 0 ? lines[si - 1] : '', page_id: pageLink || '',
      creatives: n, versions: /multiple versions/.test(t), format, media,
      eu_flag: /EU transparency/.test(t), body: body.join(' ').slice(0, 400), cta };
  }

  window.MA = {
    // Count loaded cards cheaply (no layout).
    count() { return document.body.textContent.split('Library ID:').length - 1; },
    // Big searches freeze the tab if a single call scrolls for long, so scrolling runs in the
    // background: autoscroll() starts it and returns at once; poll status() between short waits
    // until done is true (the list stopped growing for ~30 s), then export().
    autoscroll(every = 3000, idle = 10) {
      clearInterval(window.__maScroll); window.__maLast = 0; window.__maSame = 0;
      window.__maScroll = setInterval(() => {
        const n = this.count();
        if (n === window.__maLast) window.__maSame++; else { window.__maSame = 0; window.__maLast = n; }
        if (window.__maSame > idle) clearInterval(window.__maScroll);
        window.scrollTo(0, document.body.scrollHeight);
      }, every);
      return 'scrolling';
    },
    status() {
      const tot = (document.body.textContent.match(/~?([\d,]+) results/) || [, ''])[1];
      return JSON.stringify({ loaded: this.count(), total: tot, done: window.__maSame > 10 });
    },
    // Parsed rows, a page at a time (keep limit small: results past ~1,500 characters are cut off).
    rows(offset = 0, limit = 25) {
      return JSON.stringify([...mainCards()].slice(offset, offset + limit).map(([id, c]) => parse(id, c)));
    },
    // Short summary of everything loaded: ids with dates and creative counts only.
    brief() {
      return JSON.stringify([...mainCards()].map(([id, c]) => { const p = parse(id, c);
        return [id, p.advertiser.slice(0, 24), p.status[0], p.start, p.end, p.creatives, p.versions ? 1 : 0, p.format[0]]; }));
    },
    // Open the "N ads use this creative" summary for a card and list its versions.
    async versions(id) {
      const c = mainCards().get(id); if (!c) return JSON.stringify({ error: 'card not loaded' });
      c.scrollIntoView({ block: 'center' });
      const b = [...c.querySelectorAll('*')].find(x => x.childElementCount === 0 && /^See (ad|summary) details$/.test(x.textContent.trim()));
      (b.closest('[role=button]') || b).click(); await sleep(3500);
      const d = [...document.querySelectorAll('div[role=dialog]')].pop();
      const v = [...cards(d)].map(([vid, vc]) => { const p = parse(vid, vc); return { id: vid, start: p.start, end: p.end, status: p.status, eu: p.eu_flag }; });
      return JSON.stringify(v);
    },
    // In the open dialog, open one version's details and read EU reach + countries.
    async eu(versionId) {
      let d = [...document.querySelectorAll('div[role=dialog]')].pop(); if (!d) return JSON.stringify({ error: 'no dialog' });
      const vc = cards(d).get(versionId);
      if (vc) { const b = [...vc.querySelectorAll('*')].find(x => x.childElementCount === 0 && x.textContent.trim() === 'See ad details');
        if (b) { (b.closest('[role=button]') || b).click(); await sleep(3000); } }
      d = [...document.querySelectorAll('div[role=dialog]')].pop();
      const h = [...d.querySelectorAll('*')].find(x => x.childElementCount === 0 && x.textContent.trim() === 'Transparency by location');
      // the accordion ignores a bare .click(): send the full pointer sequence
      if (h) { const tg = h.closest('[role=button]') || h;
        ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(ev => tg.dispatchEvent(new MouseEvent(ev, { bubbles: true })));
        await sleep(2500); }
      const t = d.innerText;
      const reach = (t.match(/Reach\n([\d,]+)/) || [, ''])[1].replace(/,/g, '');
      const countries = [...t.matchAll(/\n([^\n]+)\nCountry\nIncluded/g)].map(m => m[1]);
      return JSON.stringify({ id: versionId, eu_reach: reach ? +reach : '', countries });
    },
    closeDialogs() {
      for (const d of [...document.querySelectorAll('div[role=dialog]')].reverse()) {
        const b = [...d.querySelectorAll('[role=button]')].find(x => x.innerText.trim() === 'Close'); if (b) b.click(); }
      return 'ok';
    },
    // Lay a snapshot grid of one ad over the page: every carousel card, and frames frames
    // spread across each video. Returns the rectangle to capture with computer.zoom(save_to_disk).
    async grid(id, frames = 6, label = '') {
      document.getElementById('__ma_grid')?.remove();
      // open https://www.facebook.com/ads/library/?id=<id> first: one card, no freeze
      for (let i = 0; i < 20 && !document.body.textContent.includes('Library ID: ' + id); i++) await sleep(500);
      const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT,
        { acceptNode: n => n.nodeValue.includes('Library ID: ' + id) ? 1 : 3 });
      if (!w.nextNode()) return JSON.stringify({ error: 'ad not on page' });
      const c = cardOf(w.currentNode, document.body);
      await sleep(800);
      const H = 300, tiles = [];
      for (const img of [...c.querySelectorAll('img')].filter(i => i.naturalWidth > 100).slice(0, 10)) {
        const i = new Image(); i.src = img.currentSrc || img.src; tiles.push(i);
      }
      await Promise.all(tiles.map(t => t.decode().catch(() => {})));
      for (const v of [...c.querySelectorAll('video')].slice(0, 10)) {
        const src = v.currentSrc || v.src; if (!src) continue;
        const blob = await (await fetch(src)).blob();
        const pv = document.createElement('video'); pv.muted = true; pv.src = URL.createObjectURL(blob);
        await new Promise(r => { pv.onloadeddata = r; setTimeout(r, 8000); });
        const k = c.querySelectorAll('video').length > 1 ? 1 : frames; // carousel of videos: one frame per card
        for (let f = 0; f < k; f++) {
          pv.currentTime = pv.duration * (k === 1 ? 0.3 : (f + 0.5) / k);
          await new Promise(r => { pv.onseeked = r; setTimeout(r, 4000); });
          const cv = document.createElement('canvas'); cv.height = H; cv.width = Math.round(pv.videoWidth * H / pv.videoHeight);
          cv.getContext('2d').drawImage(pv, 0, 0, cv.width, cv.height); tiles.push(cv);
        }
      }
      if (!tiles.length) return JSON.stringify({ error: 'no media in card' });
      // shrink tiles so every card or frame fits on one row (decision 10: keep every carousel card)
      const asp = tiles.reduce((a, t) => a + (t.naturalWidth ? t.naturalWidth / t.naturalHeight : t.width / t.height), 0);
      const fitH = Math.max(120, Math.min(H, Math.floor((innerWidth - 24 - 6 * (tiles.length - 1)) / asp)));
      tiles.forEach(t => { t.style.height = fitH + 'px'; t.style.width = 'auto'; });
      // Full-screen dark layer with the tiles top-left. Capture it with one full-frame
      // computer.zoom (save_to_disk); build.py trim cuts the empty dark area off afterwards.
      const g = document.createElement('div'); g.id = '__ma_grid';
      g.style.cssText = 'position:fixed;inset:0;z-index:2147483647;background:#111;padding:8px;display:flex;flex-wrap:wrap;gap:6px;align-content:flex-start;align-items:flex-start';
      const cap = document.createElement('div');
      cap.textContent = label || id;
      cap.style.cssText = 'flex-basis:100%;color:#ddd;font:13px system-ui;padding:0 2px 4px';
      g.appendChild(cap); tiles.forEach(t => g.appendChild(t)); document.body.appendChild(g);
      await sleep(900);
      // if a tile still wraps (image sizes known late), shrink until everything is on one row
      let fh = fitH; const nrows = () => new Set(tiles.map(t => Math.round(t.getBoundingClientRect().top))).size;
      while (nrows() > 1 && fh > 110) { fh -= 12; tiles.forEach(t => t.style.height = fh + 'px'); await sleep(60); }
      const last = tiles[tiles.length - 1].getBoundingClientRect();
      const rows = new Set(tiles.map(t => Math.round(t.getBoundingClientRect().top))).size;
      // zoom region: top 35% of the frame height (one row); full frame if rows > 1
      return JSON.stringify({ tiles: tiles.length, rows, cut: last.bottom > innerHeight });
    },
    clearGrid() { document.getElementById('__ma_grid')?.remove(); return 'ok'; },
    // Tool results are cut off past ~1,500 characters, so bulk data goes out through the page:
    // export() parses every loaded ad that ran >= minDays, shows one line per ad (fields joined
    // by " ¦ ", since page text turns tabs into spaces) in a full-page <article>, hides the rest,
    // and pads it past 50 KB so get_page_text saves it to a file instead of printing it.
    // Read that file with build.py import, then clearOut() to restore the page.
    // Fields: id advertiser page_id status start end days creatives versions format media eu body
    export(minDays = 30, today = new Date().toISOString().slice(0, 10)) {
      this.clearOut();
      const T = Date.parse(today), out = [];
      let all = 0;
      for (const [id, c] of mainCards()) {
        const p = parse(id, c); all++;
        const days = Math.round(((p.end ? Date.parse(p.end) : T) - Date.parse(p.start)) / 864e5);
        if (!(days >= minDays)) continue;
        // IDs go out as 12345678x9012345: the extension redacts digit runs that look like card numbers
        const unredact = v => String(v).replace(/^(\d{8})(\d)/, '$1x$2');
        out.push([unredact(p.id), p.advertiser, unredact(p.page_id), p.status, p.start, p.end, days, p.creatives, p.versions ? 1 : 0,
          p.format, p.media, p.eu_flag ? 1 : 0, p.body.replace(/\s+/g, ' ').replace(/¦/g, '|').slice(0, 220)].join(' ¦ '));
      }
      const art = document.createElement('article'); art.id = '__ma_out';
      const pre = document.createElement('pre'); pre.style.cssText = 'white-space:pre-wrap;font:11px monospace';
      pre.textContent = 'MA-EXPORT-START\n' + out.join('\n') + '\nMA-EXPORT-END\n' + ('.'.repeat(99) + '\n').repeat(520);
      art.appendChild(pre);
      for (const ch of document.body.children) { ch.dataset.maDisplay = ch.style.display; ch.style.display = 'none'; }
      document.body.appendChild(art);
      return JSON.stringify({ loaded: all, kept: out.length });
    },
    clearOut() {
      document.getElementById('__ma_out')?.remove();
      for (const ch of document.body.children) if ('maDisplay' in ch.dataset) { ch.style.display = ch.dataset.maDisplay; delete ch.dataset.maDisplay; }
      return 'ok';
    },
  };
  return 'MA ready';
})();
