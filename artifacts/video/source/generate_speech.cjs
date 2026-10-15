const fs=require('fs');
const path=require('path');
const {EdgeTTS}=require('@andresaya/edge-tts');
const scenes=require('./scenes.json');
const OUT=path.join(__dirname,'speech');fs.mkdirSync(OUT,{recursive:true});
const tts=new EdgeTTS({timeout:30000});
const target=13.7;
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function speak(text,rate){
 for(let retry=0;retry<4;retry++){
  await sleep(3500);
  try{return await tts.generate(text,'zh-CN-YunxiNeural',{rate:rate+'%',outputFormat:'audio-24khz-96kbitrate-mono-mp3',timeout:30000});}
  catch(error){if(!/429/.test(String(error))||retry===3)throw error;console.log('VOICE_RATE_LIMIT_WAIT',60*(retry+1));await sleep(60000*(retry+1));}
 }
}
(async()=>{
 for(let i=0;i<scenes.length;i++){
  const stem=String(i).padStart(2,'0');
  if(fs.existsSync(OUT+'/'+stem+'.json')){const previous=JSON.parse(fs.readFileSync(OUT+'/'+stem+'.json','utf8'));if(previous.text===scenes[i].voice){console.log('CACHED',i,previous.duration);continue;}}
  let rate=12,result;
  for(let attempt=0;attempt<4;attempt++){
   result=await speak(scenes[i].voice,rate);
   if(result.duration<=14.1&&result.duration>=12.1)break;
   const next=Math.round((1+rate/100)*result.duration/target*100-100);
   rate=Math.max(-20,Math.min(42,next));
  }
  if(result.duration>14.25)throw Error('Speech exceeds slot '+i+': '+result.duration);
  fs.writeFileSync(OUT+'/'+stem+'.mp3',result.audio);
  fs.writeFileSync(OUT+'/'+stem+'.json',JSON.stringify({text:scenes[i].voice,voice:'zh-CN-YunxiNeural',rate,duration:result.duration,wordBoundaries:result.wordBoundaries,sentenceBoundaries:result.sentenceBoundaries},null,2));
  console.log('SPEECH',i,'seconds',result.duration,'rate',rate,'words',result.wordBoundaries.length);
 }
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
