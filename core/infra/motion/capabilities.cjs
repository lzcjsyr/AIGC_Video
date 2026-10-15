const fs=require('node:fs');const path=require('node:path');const {createRequire}=require('node:module');
const {launchBrowser}=require('./browser.cjs');
const spec=JSON.parse(fs.readFileSync(0,'utf8'));
(async()=>{
  const puppeteer=createRequire(path.join(spec.modules,'package.json'))('puppeteer-core');
  const launched=await launchBrowser(puppeteer,spec.browser,spec.browserMode);
  try {
    const page=await launched.browser.newPage();await page.setViewport({width:spec.width,height:spec.height,deviceScaleFactor:1});
    await page.setContent('<canvas id="probe"></canvas>');
    const codecs=await page.evaluate(()=>{
      const canvas=document.getElementById('probe');canvas.width=innerWidth;canvas.height=innerHeight;
      const gl=canvas.getContext('webgl');if(!gl)throw Error('WebGL probe failed');
      gl.clearColor(.2,.4,.6,1);gl.clear(gl.COLOR_BUFFER_BIT);gl.finish();
      const video=document.createElement('video');return {h264:video.canPlayType('video/mp4; codecs="avc1.42E01E"'),vp9:video.canPlayType('video/webm; codecs="vp9"')};
    });
    const screenshot=await page.screenshot();if(screenshot.length<100)throw Error('Browser screenshot probe failed');
    console.log(JSON.stringify({browser:await launched.browser.version(),mode:launched.mode,gpu:launched.gpu,fallbackReason:launched.fallbackReason,codecs,screenshotVerified:true}));
  } finally {await launched.browser.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
