const fs=require('fs');
const {createRequire}=require('module');
const {pathToFileURL}=require('url');
const r=createRequire('C:/Users/fanzhen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_qa.cjs');
const {chromium}=r('playwright');
const sharp=r('sharp');
const OUT='D:/project/ai算法/deliverables/project_intro_video_20261015';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
  const errors=[],warnings=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='warning')warnings.push(m.text());if(m.type()==='error')errors.push(m.text())});
  await page.goto(pathToFileURL(OUT+'/观微证据链三分钟介绍.html').href);await page.waitForFunction(()=>window.filmReady);
  await page.screenshot({path:OUT+'/检查/开场.png'});
  const captures=[];
  for(let i=0;i<12;i++){
   const t=i*15+7;await page.evaluate(t=>film.sample(t),t);await page.waitForTimeout(120);
   const state=await page.evaluate(()=>{const s=film.getState();const active=document.querySelector('.scene[data-index="'+s.scene+'"]'),title=active.querySelector('h1').getBoundingClientRect(),stage=document.getElementById('stage').getBoundingClientRect();return{...s,titleFits:title.left>=stage.left&&title.right<=stage.right,bodyWidth:document.body.scrollWidth,windowWidth:innerWidth}});
   if(state.scene!==i||Math.abs(state.time-t)>.05||Math.abs(state.timelineTime-t)>.05||!state.titleFits)throw Error('State/layout mismatch '+JSON.stringify(state));
   const file=OUT+'/检查/片段'+String(i+1).padStart(2,'0')+'.png';await page.screenshot({path:file});captures.push(file);
  }
  await page.evaluate(()=>film.sample(0));await page.locator('#play').click();await page.waitForTimeout(1600);
  const playing=await page.evaluate(()=>film.getState());if(!playing.playing||playing.time<1||!playing.caption)throw Error('Audio playback or captions failed');
  await page.locator('#play').click();const paused=await page.evaluate(()=>film.getState());await page.waitForTimeout(350);const later=await page.evaluate(()=>film.getState());if(Math.abs(later.time-paused.time)>.03)throw Error('Pause did not stop voice');
  await page.locator('#mute').click();if(!await page.locator('#voice').evaluate(e=>e.muted))throw Error('Mute failed');await page.locator('#mute').click();
  await page.locator('#captionsToggle').click();await page.evaluate(()=>film.seek(8));if(await page.locator('#caption').textContent())throw Error('Captions toggle failed');await page.locator('#captionsToggle').click();
  await page.evaluate(()=>film.sample(178.8));await page.locator('#play').click();await page.waitForTimeout(1800);const end=await page.evaluate(()=>film.getState());if(end.scene!==11||Math.abs(end.time-180)>.05||end.playing)throw Error('Ending failed '+JSON.stringify(end));
  const mobile=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1});await mobile.goto(pathToFileURL(OUT+'/观微证据链三分钟介绍.html').href);await mobile.waitForFunction(()=>window.filmReady);
  for(const i of [0,2,7,8,11]){await mobile.evaluate(t=>film.sample(t),i*15+7);await mobile.waitForTimeout(100);if(await mobile.evaluate(()=>document.body.scrollWidth>innerWidth+1))throw Error('Mobile horizontal overflow');await mobile.screenshot({path:OUT+'/检查/手机'+i+'.png'});}
  for(let k=0;k<captures.length;k+=4){const inputs=[];for(let j=0;j<4&&k+j<captures.length;j++)inputs.push({input:await sharp(captures[k+j]).resize({width:640}).png().toBuffer(),left:j%2*660,top:Math.floor(j/2)*465});await sharp({create:{width:1320,height:930,channels:3,background:'#d9dfdf'}}).composite(inputs).png().toFile(OUT+'/检查/总览'+(k/4+1)+'.png');}
  if(errors.length)throw Error('Browser errors '+errors.join(';'));
  const result={duration:end.audioDuration,scenes:12,desktopScreenshots:12,mobileScreenshots:5,voicePlayback:true,pause:true,mute:true,subtitleToggle:true,endAt180Seconds:true,timelineDriftMs:Math.abs(playing.time-playing.timelineTime)*1000,errors,warnings};fs.writeFileSync(OUT+'/检查/验收结果.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
