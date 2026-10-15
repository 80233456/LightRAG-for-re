const fs=require('fs');
const {spawnSync}=require('child_process');
const {pathToFileURL}=require('url');
const {createRequire}=require('module');
const r=createRequire('C:/Users/fanzhen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_videoqa.cjs');
const {chromium}=r('playwright');
const OUT='D:/project/ai算法/deliverables/project_intro_video_20261015';
const file=OUT+'/观微证据链三分钟项目介绍.mp4';
const ffmpeg=require.resolve('@ffmpeg-installer/win32-x64/ffmpeg.exe');
const probe=require.resolve('@ffprobe-installer/win32-x64/ffprobe.exe');
(async()=>{
 const info=spawnSync(probe,['-v','error','-show_format','-show_streams','-of','json',file],{encoding:'utf8',windowsHide:true});
 if(info.status!==0)throw Error(info.stderr);
 const metadata=JSON.parse(info.stdout),v=metadata.streams.find(s=>s.codec_type==='video'),a=metadata.streams.find(s=>s.codec_type==='audio');
 if(!v||!a||v.width!==1920||v.height!==1080||v.codec_name!=='h264'||v.pix_fmt!=='yuv420p'||v.avg_frame_rate!=='30/1'||Number(v.nb_frames)!==5400||Math.abs(Number(metadata.format.duration)-180)>.1)throw Error('Unexpected MP4 metadata '+info.stdout);
 const decode=spawnSync(ffmpeg,['-v','error','-i',file,'-f','null','NUL'],{encoding:'utf8',windowsHide:true,timeout:300000});
 if(decode.status!==0||decode.stderr.trim())throw Error('Decode validation failed '+decode.stderr);
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const checks=[];
 try{
  const page=await browser.newPage({viewport:{width:1920,height:1080}});
  await page.goto(pathToFileURL(file).href);
  await page.waitForFunction(()=>{const v=document.querySelector('video');return v&&v.readyState>=2;});
  await page.addStyleTag({content:'html,body{margin:0;background:white;width:100%;height:100%;overflow:hidden}video{position:fixed;inset:0;width:1920px;height:1080px;object-fit:contain;background:white}'});
  await page.locator('video').evaluate(v=>{v.controls=false;v.muted=true;});
  for(const t of [7,37,82,127,157,172]){
   await page.locator('video').evaluate((v,t)=>new Promise(resolve=>{v.addEventListener('seeked',resolve,{once:true});v.currentTime=t;}),t);
   await page.waitForTimeout(80);
   checks.push(await page.locator('video').evaluate(v=>({time:v.currentTime,width:v.videoWidth,height:v.videoHeight,readyState:v.readyState,error:v.error&&v.error.message})));
   await page.screenshot({path:OUT+'/检查/成片复核'+t+'.png'});
  }
  await page.locator('video').evaluate(v=>v.play());await page.waitForTimeout(1100);const playback=await page.locator('video').evaluate(v=>({time:v.currentTime,paused:v.paused,error:v.error&&v.error.message}));
  if(playback.paused||playback.error||playback.time<173)throw Error('Chrome playback failed');
  const result={passed:true,fullDecode:'passed',browserPlayback:'passed',duration:Number(metadata.format.duration),frames:Number(v.nb_frames),resolution:[v.width,v.height],fps:v.avg_frame_rate,videoCodec:v.codec_name,pixelFormat:v.pix_fmt,audioCodec:a.codec_name,audioDuration:Number(a.duration),burnedInCaptions:true,checks,metadata};
  fs.writeFileSync(OUT+'/检查/成片验收.json',JSON.stringify(result,null,2));console.log(JSON.stringify({passed:true,duration:result.duration,frames:result.frames,resolution:result.resolution,audioCodec:result.audioCodec}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
