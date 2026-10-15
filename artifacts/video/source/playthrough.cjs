const fs=require('fs');
const {createRequire}=require('module');
const {pathToFileURL}=require('url');
const r=createRequire('C:/Users/fanzhen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_playthrough.cjs');
const OUT='D:/project/ai算法/deliverables/project_intro_video_20261015';
(async()=>{
 const browser=await r('playwright').chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  await page.goto(pathToFileURL(OUT+'/观微证据链三分钟介绍.html').href);await page.waitForFunction(()=>window.filmReady);
  await page.locator('#play').click();const samples=[];
  for(let i=0;i<12;i++){
   await page.waitForTimeout(15020);const s=await page.evaluate(()=>film.getState());samples.push(s);
   if(Math.abs(s.timelineTime-s.time)>.1)throw Error('Audio/visual clock drift');
   console.log('PLAYTHROUGH',i+1,JSON.stringify(s));
  }
  const final=samples.at(-1);if(final.time!==180||final.playing||final.scene!==11)throw Error('Full playback failed');
  fs.writeFileSync(OUT+'/检查/完整播放检查.json',JSON.stringify({passed:true,duration:180,samples},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
