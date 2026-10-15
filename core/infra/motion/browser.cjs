// Hardware discovery is shared by exports and the capability command.
async function launchBrowser(puppeteer, executablePath, requested='auto') {
  if (!['auto','hardware','software'].includes(requested || 'auto')) throw Error('Invalid browser mode');
  let browser, fallbackReason=null;
  const hardware=['--enable-gpu','--enable-webgl','--hide-scrollbars'];
  if(process.platform==='darwin') hardware.push('--use-gl=angle','--use-angle=metal');
  if(process.platform==='win32') hardware.push('--use-gl=angle','--use-angle=d3d11');
  const launch=args=>puppeteer.launch({executablePath,headless:true,args});
  const gpu=async b=>{const p=await b.newPage();try{return await p.evaluate(()=>{
    const gl=document.createElement('canvas').getContext('webgl2') || document.createElement('canvas').getContext('webgl');
    if(!gl) return null;const ext=gl.getExtension('WEBGL_debug_renderer_info');
    return String(gl.getParameter(ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER));
  });}finally{await p.close();}};
  if(requested!=='software') {
    try {
      browser=await launch(hardware);const renderer=await gpu(browser);
      if(!renderer || /swiftshader|llvmpipe|software/i.test(renderer)) throw Error('Hardware WebGL unavailable: '+renderer);
      return {browser,gpu:renderer,mode:'hardware',fallbackReason};
    } catch(error) {
      if(browser) await browser.close();browser=null;
      if(requested==='hardware') throw error;
      fallbackReason=error.message;
    }
  } else fallbackReason='Software mode explicitly requested';
  browser=await launch(['--use-angle=swiftshader','--enable-unsafe-swiftshader','--hide-scrollbars']);
  try {
    const renderer=await gpu(browser);if(!renderer)throw Error('Software WebGL unavailable');
    return {browser,gpu:renderer,mode:'software',fallbackReason};
  }catch(error){await browser.close();throw error;}
}
module.exports={launchBrowser};
