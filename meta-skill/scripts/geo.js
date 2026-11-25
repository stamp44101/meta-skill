// geo.js — where each kept ad ran, from the Ad Library country filter (step 2b of SKILL.md).
// The library shows no country for ads outside the EU, but `country=XX` lists only ads that reached XX.
// Three snippets, pasted with javascript_tool. Data rides in window.name (it survives navigation in the tab; CSP blocks eval).
//
// 1. SET — once per tab per brand, on any Ad Library page. Get the exact line from:
//      python3 -I scripts/build.py geo-ids meta-<brand> "<Brand>"
//    It stores the brand's kept IDs (plus "also shown as" IDs) in the order build.py saved to geo-ids.json.
//
// 2. SCROLL — after navigating to ...&country=XX&q=<same search as step 1>. Starts loading in the background and returns at once.
//    The small jump up and back down makes the page fetch the next batch; it stops after ~36 s with no new cards.
clearInterval(window.__s);window.__l=-1;window.__m=0;window.__s=setInterval(()=>{const n=document.body.textContent.split('Library ID:').length-1;if(n===window.__l)window.__m++;else{window.__m=0;window.__l=n}if(window.__m>12)clearInterval(window.__s);scrollTo(0,document.body.scrollHeight-2000);setTimeout(()=>scrollTo(0,document.body.scrollHeight),400)},3000);'go '+new URLSearchParams(location.search).get('country')
//
// 3. CHECK — fast, any time. Returns one line for the results file, e.g.
//      #Bupbes|KR t=360 n=294 done=true hit=0.1.2.5
//    t = results the page reports, n = cards loaded, hit = indexes into geo-ids.json (indexes, not IDs:
//    the extension redacts some 16-digit IDs as card numbers). Small pages (t under ~30) are done in ~15 s;
//    long pages often stall: when done=true but n is far below t, run SCROLL again and CHECK again; build.py adds the passes up.
(()=>{const N=JSON.parse(window.name);const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,{acceptNode:n=>/Library ID: \d+/.test(n.nodeValue)?1:3});const S=new Set();while(w.nextNode())S.add(w.currentNode.nodeValue.match(/Library ID: (\d+)/)[1]);const t=(document.body.textContent.match(/~?([\d,]+) results?/)||[,'0'])[1];const h=[];N.W.forEach((x,k)=>{if(S.has(x))h.push(k)});return '#'+N.b+'|'+new URLSearchParams(location.search).get('country')+' t='+t+' n='+S.size+' done='+(window.__m>12)+' hit='+h.join('.')})()
