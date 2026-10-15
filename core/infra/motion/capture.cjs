// Browser capture only: clip time belongs to the composition, never the wall clock.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { createRequire } = require('node:module');
const spec = JSON.parse(fs.readFileSync(0, 'utf8'));
const puppeteer = createRequire(path.join(spec.modules, 'package.json'))('puppeteer-core');

(async () => {
  const root = fs.realpathSync(spec.work);
  const types = {'.html':'text/html; charset=utf-8','.js':'text/javascript','.json':'application/json',
    '.css':'text/css','.svg':'image/svg+xml','.png':'image/png','.woff2':'font/woff2', '.mp4':'video/mp4', '.webm':'video/webm'};
  const server = http.createServer((req, res) => {
    if (req.url === '/favicon.ico') { res.writeHead(204).end(); return; }
    try {
      const file = fs.realpathSync(path.resolve(root, '.' + decodeURIComponent(new URL(req.url, 'http://localhost').pathname)));
      if (!file.startsWith(root + path.sep)) { res.writeHead(403).end(); return; }
      res.setHeader('Content-Type', types[path.extname(file)] || 'application/octet-stream');
      const size=fs.statSync(file).size;
      res.setHeader('Accept-Ranges','bytes');
      const range=/^bytes=(\d+)-(\d*)$/.exec(req.headers.range || '');
      if (range) {
        const start=Number(range[1]), end=Math.min(size-1,range[2] ? Number(range[2]) : size-1);
        if (start>end) {res.writeHead(416).end();return;}
        res.writeHead(206,{'Content-Range':`bytes ${start}-${end}/${size}`,'Content-Length':end-start+1});
        fs.createReadStream(file,{start,end}).pipe(res);
      } else {
        res.setHeader('Content-Length',size);fs.createReadStream(file).pipe(res);
      }
    } catch { res.writeHead(404).end(); }
  });
  let browser;
  const errors = [];
  const report = {success:false, width:spec.width, height:spec.height, fps:spec.fps, frames:0, errors};
  const status = (phase, completed=0, total=0) => {
    const target=path.join(root,'render-status.json'), temporary=target+'.tmp';
    fs.writeFileSync(temporary,JSON.stringify({phase,completed,total,updatedAt:Date.now()}));fs.renameSync(temporary,target);
  };
  try {
    status('starting');
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const origin = `http://127.0.0.1:${server.address().port}`;
    const {launchBrowser}=require('./browser.cjs');
    const launched=await launchBrowser(puppeteer,spec.browser,spec.browserMode);
    browser=launched.browser;report.browserMode=launched.mode;report.gpu=launched.gpu;report.fallbackReason=launched.fallbackReason;
    const page = await browser.newPage();
    await page.setViewport({width:spec.width,height:spec.height,deviceScaleFactor:1});
    page.on('pageerror', err => errors.push(String(err)));
    page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
    await page.setRequestInterception(true);
    page.on('request', request => {
      const url = request.url();
      if (url.startsWith(origin + '/') || url.startsWith('data:') || url.startsWith('blob:')) request.continue();
      else { errors.push(`External resource blocked: ${url}`); request.abort(); }
    });
    page.on('response', response => { if (response.status() >= 400) errors.push(`HTTP ${response.status()}: ${response.url()}`); });
    await page.evaluateOnNewDocument(payload => {
      window.clipPayload = payload;
      // Compatibility for previously saved HTML. No framework runtime is loaded.
      window.__timelines = {};
      window.__hyperframes = {getVariables: () => payload};
      window.clipTools = {
        async seekVideo(video, time) {
          video.pause();
          if (video.readyState < 1) await new Promise((resolve,reject) => {
            video.addEventListener('loadedmetadata',resolve,{once:true});
            video.addEventListener('error',()=>reject(Error('Video failed: '+video.src)),{once:true});
          });
          const target=Math.max(0,Math.min(time,Number.isFinite(video.duration) ? Math.max(0,video.duration-1/1000) : time));
          if (Math.abs(video.currentTime-target) < 1e-7 && video.readyState>=2 && !video.seeking) return;
          await new Promise((resolve,reject) => {
            const done=()=>{cleanup();resolve();};
            const fail=()=>{cleanup();reject(Error('Video seek failed: '+video.src));};
            const timer=setTimeout(fail,10000);
            const cleanup=()=>{clearTimeout(timer);video.removeEventListener('seeked',done);video.removeEventListener('error',fail);};
            video.addEventListener('seeked',done,{once:true});video.addEventListener('error',fail,{once:true});
            video.currentTime=target;
          });
          // seeked means the decoder finished; allow its texture to reach the compositor.
          await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
        }
      };
    }, spec.payload);
    await page.goto(origin + '/' + spec.entry.split('/').map(encodeURIComponent).join('/'), {waitUntil:'networkidle0',timeout:30000});
    await page.evaluate(payload => {
      if (window.clip) return;
      const root = document.querySelector('[data-composition-id]');
      const timelines = Object.values(window.__timelines || {});
      if (!root || !timelines.length) return;
      root.id = 'segment-root';
      const width = Number(root.dataset.width), height = Number(root.dataset.height);
      root.style.width = width + 'px'; root.style.height = height + 'px';
      document.body.style.margin = '0';
      const durationSeconds = Number(root.dataset.duration) || payload.durationSeconds;
      timelines.forEach(tl => tl.pause());
      window.clip = {width, height, durationSeconds, ready:document.fonts.ready,
        async renderAt(t) {
          timelines.forEach(tl => tl.totalTime(t, false));
          await Promise.all([...document.querySelectorAll('video')].map(video => {
            const start=Number(video.dataset.start || 0), duration=Number(video.dataset.duration || Infinity);
            if(t < start || t >= start+duration) return;
            return window.clipTools.seekVideo(video, t-start+Number(video.dataset.mediaStart || 0));
          }));
          window.__hfThreeTime = t;
          window.dispatchEvent(new CustomEvent('hf-seek', {detail:{time:t}}));
        }};
    }, spec.payload);
    await page.waitForFunction(() => window.clip && typeof window.clip.renderAt === 'function', {timeout:10000});
    await page.evaluate(async () => {
      if (!window.clip.ready || typeof window.clip.ready.then !== 'function') throw Error('clip.ready must be a Promise');
      await Promise.race([window.clip.ready, new Promise((_, reject) => setTimeout(() => reject(Error('clip.ready timed out')), 30000))]);
      await document.fonts.ready;
      await Promise.all([...document.images].filter(img => img.currentSrc || img.getAttribute('src')).map(img => img.decode()));
    });
    const contract = await page.evaluate(() => ({width:clip.width,height:clip.height,durationSeconds:clip.durationSeconds}));
    if (contract.width !== spec.width || contract.height !== spec.height || !(contract.durationSeconds > 0))
      throw Error('clip width/height must match the requested canvas; durationSeconds must be positive. Regenerate the clip for a changed canvas.');
    report.authoredDuration = contract.durationSeconds;
    report.browser = await browser.version();
    console.log('Browser GPU: ' + report.gpu);
    if (/SwiftShader|llvmpipe|software/i.test(report.gpu)) console.log('Browser hardware GPU unavailable; software fallback: ' + report.gpu);
    const duration = spec.duration;
    const count = Math.ceil(duration * spec.fps - 1e-9);
    const times = spec.mode === 'render' ? Array.from({length:count}, (_,i) => i/spec.fps) : spec.times;
    status(spec.mode==='render'?'capture':'checking',0,times.length);
    fs.mkdirSync(spec.destination, {recursive:true});
    const draw = async time => {
      // Preserve authored pacing if the narration length was changed after design.
      await page.evaluate(async t => {
        await Promise.race([window.clip.renderAt(t), new Promise((_, reject) => setTimeout(() => reject(Error('clip.renderAt timed out')), 10000))]);
      }, time * contract.durationSeconds / duration);
      if (errors.length) throw Error(errors.join('\n'));
    };
    for (let i=0;i<times.length;i++) {
      await draw(times[i]);
      if (spec.mode === 'check') {
        const issues = await page.evaluate(captionZone => {
          const issues=[];
          const root=document.getElementById('segment-root');
          if (!root) return ['Missing #segment-root'];
          if (document.documentElement.scrollWidth > innerWidth || document.documentElement.scrollHeight > innerHeight) issues.push('Canvas overflow');
          const wrapper=document.getElementById('content-wrapper');
          if (captionZone && !wrapper) issues.push('Missing #content-wrapper');
          for (const el of (captionZone && wrapper ? [wrapper,...wrapper.querySelectorAll('*')] : [])) {
            const s=getComputedStyle(el), r=el.getBoundingClientRect();
            if (s.display==='none' || s.visibility==='hidden' || +s.opacity===0 || !r.width || !r.height) continue;
            if (r.left < -.5 || r.top < -.5 || r.right > innerWidth+.5 || r.bottom > innerHeight*.8+.5) issues.push(`Foreground outside caption-safe canvas: ${el.id || el.tagName}`);
          }
          return issues;
        }, spec.captionZone);
        if (issues.length) throw Error(issues.join('\n'));
      }
      const bytes = await page.screenshot({type:'png'});
      if (spec.mode === 'check') {
        await draw((count - 1)/spec.fps);
        await draw(times[i]);
        const again=await page.screenshot({type:'png'});
        if (!Buffer.from(bytes).equals(Buffer.from(again))) {
          // GPU video scaling may vary by a few levels at isolated edge pixels.
          // Reject changed content while tolerating bounded rasterization noise.
          const difference=await page.evaluate(async pngs=>{
            const pixels=await Promise.all(pngs.map(async value=>{
              const bitmap=await createImageBitmap(await (await fetch('data:image/png;base64,'+value)).blob());
              const canvas=new OffscreenCanvas(bitmap.width,bitmap.height),ctx=canvas.getContext('2d',{willReadFrequently:true});
              ctx.drawImage(bitmap,0,0);const data=ctx.getImageData(0,0,canvas.width,canvas.height).data;bitmap.close();return data;
            }));
            let max=0,changed=0;
            for(let i=0;i<pixels[0].length;i+=4){
              let delta=0;for(let c=0;c<4;c++)delta=Math.max(delta,Math.abs(pixels[0][i+c]-pixels[1][i+c]));
              max=Math.max(max,delta);if(delta>2)changed++;
            }
            return {max,changed,total:pixels[0].length/4};
          },[Buffer.from(bytes).toString('base64'),Buffer.from(again).toString('base64')]);
          if(difference.max>12 || difference.changed>Math.max(1,Math.ceil(difference.total*.0001))) {
            fs.writeFileSync(path.join(spec.destination,'nonrepeatable-before.png'),bytes);
            fs.writeFileSync(path.join(spec.destination,'nonrepeatable-after.png'),again);
            throw Error(`Non-repeatable frame at ${times[i]}s (${JSON.stringify(difference)})`);
          }
          report.rasterNoiseTolerance={maxChannelDelta:12,maxChangedFraction:.0001};
        }
      }
      fs.writeFileSync(path.join(spec.destination, `frame-${String(i).padStart(6,'0')}.png`), bytes);
      report.frames++;
      if (i===0 || (i+1)%30===0 || i===times.length-1) {
        status(spec.mode==='render'?'capture':'checking',i+1,times.length);
        if(spec.mode==='render')console.log(`Captured ${i+1}/${times.length} frames`);
      }
    }
    report.success=true;
    report.durationSeconds=duration;
    status(spec.mode==='render'?'encoding':'checked',times.length,times.length);
  } catch (err) {
    status('failed');
    errors.push(String(err));
    process.exitCode=1;
  } finally {
    if (browser) await browser.close();
    server.close();
    fs.writeFileSync(spec.report, JSON.stringify(report,null,2));
    if (errors.length) console.error(errors.join('\n'));
  }
})().catch(err => { console.error(err); process.exitCode=1; });
