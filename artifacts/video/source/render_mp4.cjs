const fs=require('fs');
const {spawn}=require('child_process');
const {once}=require('events');
const {pathToFileURL}=require('url');
const {createRequire}=require('module');
const r=createRequire('C:/Users/fanzhen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_render.cjs');
const {chromium}=r('playwright');
const sharp=r('sharp');
const OUT='D:/project/ai算法/deliverables/project_intro_video_20261015';
const output=OUT+'/观微证据链三分钟项目介绍.mp4';
const ffmpeg=require.resolve('@ffmpeg-installer/win32-x64/ffmpeg.exe');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 let encoder;
 try{
  const page=await browser.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:1});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(OUT+'/观微证据链三分钟介绍.html').href);await page.waitForFunction(()=>window.filmReady);
  await page.addStyleTag({content:`html,body{margin:0!important;padding:0!important;width:1920px!important;height:1080px!important;overflow:hidden!important;background:white!important;display:block!important}.shell{width:1920px!important;max-width:none!important;margin:0!important;border:0!important;box-shadow:none!important}.view{width:1920px!important;height:1080px!important}.stage{width:1920px!important;height:1080px!important;aspect-ratio:auto!important}.controls,.chapters{display:none!important}.captions{left:8%!important;right:8%!important;bottom:24px!important;min-height:70px!important;font-size:30px!important}.scene[data-index="0"] .scene-content{top:350px!important}`});
  await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(250);
  const layouts=[];
  for(let i=0;i<12;i++){
   await page.evaluate(t=>film.sample(t),i*15+7);await page.waitForTimeout(40);
   const bounds=await page.evaluate(()=>{const active=document.querySelector('.scene[data-index="'+film.getState().scene+'"]');const h=active.querySelector('h1').getBoundingClientRect(),c=document.querySelector('.captions').getBoundingClientRect();return{titleLeft:h.left,titleRight:h.right,captionTop:c.top,captionBottom:c.bottom,width:innerWidth,height:innerHeight,scrollWidth:document.body.scrollWidth,controlsHidden:getComputedStyle(document.querySelector('.controls')).display==='none'};});
   if(bounds.titleLeft<40||bounds.titleRight>1880||bounds.captionBottom>1080||bounds.scrollWidth>1920||!bounds.controlsHidden)throw Error('Export layout failed '+JSON.stringify(bounds));
   layouts.push(bounds);await page.screenshot({path:OUT+'/检查/视频帧'+String(i+1).padStart(2,'0')+'.png'});
  }
  for(let k=0;k<12;k+=4){const layers=[];for(let j=0;j<4;j++)layers.push({input:await sharp(OUT+'/检查/视频帧'+String(k+j+1).padStart(2,'0')+'.png').resize(640,360).toBuffer(),left:j%2*650,top:Math.floor(j/2)*370});await sharp({create:{width:1290,height:730,channels:3,background:'#d9dfdf'}}).composite(layers).png().toFile(OUT+'/检查/视频总览'+(k/4+1)+'.png');}
  console.log('Full HD preflight passed: 12 scenes');
  encoder=spawn(ffmpeg,['-y','-hide_banner','-loglevel','warning','-f','image2pipe','-framerate','30','-vcodec','png','-i','pipe:0','-i',OUT+'/项目介绍旁白.wav','-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','fast','-crf','18','-threads','4','-pix_fmt','yuv420p','-r','30','-c:a','aac','-b:a','160k','-movflags','+faststart','-t','180',output],{windowsHide:true,stdio:['pipe','ignore','pipe']});
  let logs='';encoder.stderr.on('data',d=>{logs+=d.toString();});
  const ended=new Promise((resolve,reject)=>{encoder.on('error',reject);encoder.on('close',code=>code===0?resolve():reject(Error('Encoder exit '+code+' '+logs)));});
  encoder.stdin.on('error',()=>{});
  const cdp=await page.context().newCDPSession(page),start=Date.now();
  for(let i=0;i<5400;i++){
   await page.evaluate(t=>film.sample(t),i/30);
   const {data}=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false,optimizeForSpeed:true});
   if(!encoder.stdin.write(Buffer.from(data,'base64')))await once(encoder.stdin,'drain');
   if(i%300===0)console.log(JSON.stringify({frames:i,total:5400,videoSeconds:i/30,elapsedSeconds:Math.round((Date.now()-start)/1000)}));
  }
  encoder.stdin.end();await ended;
  if(errors.length)throw Error(errors.join(';'));
  const result={passed:true,frames:5400,width:1920,height:1080,fps:30,duration:180,subtitles:'burned-in',audio:'Chinese synthetic male voice',layouts,browserErrors:errors,encoderLog:logs,bytes:fs.statSync(output).size,renderSeconds:(Date.now()-start)/1000};
  fs.writeFileSync(OUT+'/检查/视频渲染记录.json',JSON.stringify(result,null,2));console.log('RENDER COMPLETE '+JSON.stringify({bytes:result.bytes,seconds:result.renderSeconds}));
 }finally{if(encoder&&!encoder.stdin.destroyed)encoder.stdin.destroy();await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
