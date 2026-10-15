const fs=require('fs');
const path=require('path');
const crypto=require('crypto');
const {createRequire}=require('module');
const {spawnSync}=require('child_process');
const {pathToFileURL}=require('url');
const req=createRequire('C:/Users/fanzhen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_report.cjs');
const {chromium}=req('playwright');
const {PDFDocument}=req('pdf-lib');
const sharp=req('sharp');
const JSZip=req('jszip');
const BASE='D:/project/ai算法';
const OLD=BASE+'/deliverables/competition_report_20261015';
const INPUT=BASE+'/deliverables/20261015_v2/lightrag_v2_20261015';
const OUT=BASE+'/deliverables/competition_report_zh_20261015';
const FIG=OUT+'/图表';
const QA=OUT+'/排版检查';
for(const d of [OUT,FIG,QA])fs.mkdirSync(d,{recursive:true});
const read=p=>JSON.parse(fs.readFileSync(INPUT+'/'+p,'utf8'));
const a=read('results/audit_and_comparison.json'),T=a.test,V=a.validation;
const names=['基础方案','补检索方案','改进候选流程','改进验证流程','完整流程'];
const variants=['baseline','previous_recovery','v2_context','v2_verify','v2_full'];
const pct=n=>(n*100).toFixed(2)+'%';
const E=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const C={ink:'#4F5557',line:'#9FA7A8',blue:'#D8E9EF',green:'#DFEBD4',pink:'#F7E2D2',purple:'#E7DEED',gold:'#F5E9B8',teal:'#D5E9E2',red:'#C76559'};
const figures={};
const line=(x,y,X,Y,color=C.line,w=2,dash='')=>`<line x1="${x}" y1="${y}" x2="${X}" y2="${Y}" stroke="${color}" stroke-width="${w}" ${dash?`stroke-dasharray="${dash}"`:''}/>`;
const rect=(x,y,w,h,fill='white',stroke=C.line,r=8,dash='')=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" stroke="${stroke}" stroke-width="1.6" ${dash?`stroke-dasharray="${dash}"`:''}/>`;
const circle=(x,y,r,fill='white',stroke=C.ink)=>`<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="1.4"/>`;
const text=(x,y,s,size=22,anchor='middle',color=C.ink)=>`<text x="${x}" y="${y}" text-anchor="${anchor}" font-family="Microsoft YaHei,SimSun,sans-serif" font-size="${size}" fill="${color}">${E(s)}</text>`;
const arrow=(x,y,X,Y)=>`<path d="M${x},${y} L${X},${Y}" fill="none" stroke="#969D9F" stroke-width="2.1" marker-end="url(#arrow)"/>`;
const route=(d,dash=false)=>`<path d="${d}" fill="none" stroke="#969D9F" stroke-width="2.1" ${dash?'stroke-dasharray="6 4"':''} marker-end="url(#arrow)"/>`;
const frame=(x,y,w,h,title)=>rect(x,y,w,h,'white','#50575A',24,'7 5')+text(x+w/2,y+34,title,25);
function doc(x,y,w=82,h=107,color=C.blue,mark=true){
  let s=rect(x+12,y-12,w,h,'white','#C6CCCE',10)+rect(x+6,y-6,w,h,'white','#BFC7C9',10)+rect(x,y,w,h,'white','#A9B4B8',10);
  if(mark)s+=`<rect x="${x+8}" y="${y+28}" width="${w-16}" height="18" fill="${color}"/>`;
  for(let i=0;i<5;i++)s+=line(x+10,y+16+i*17,x+w-10-(i%2)*12,y+16+i*17,'#ABB4B7',1.8);
  return s;
}
function bars(x,y,w=130,h=17,color=C.green){let s='';for(let j=0;j<7;j++)s+=rect(x+j*w/7,y,w/7-2,h,j%3===0?'#F3F4F3':color,'#879193',2);return s;}
function stack(x,y,w=130){return bars(x,y,w,16,C.green)+bars(x,y+27,w,16,C.purple)+bars(x,y+54,w,16,C.gold)+bars(x,y+81,w,16,C.pink);}
function network(x,y,scale=1,highlight=true){
  const pts=[[0,20],[29,2],[57,24],[15,53],[52,62],[79,46],[94,11],[106,75],[33,88],[78,97],[119,34]];
  const edges=[[0,1],[0,3],[1,2],[1,4],[2,4],[2,6],[2,5],[3,4],[3,8],[4,5],[4,8],[5,7],[5,9],[6,10],[7,10],[7,9],[8,9]];
  let s=`<ellipse cx="${x+55*scale}" cy="${y+49*scale}" rx="${68*scale}" ry="${61*scale}" fill="${C.blue}" opacity="0.38"/>`;
  for(const [i,j]of edges)s+=line(x+pts[i][0]*scale,y+pts[i][1]*scale,x+pts[j][0]*scale,y+pts[j][1]*scale,'#899193',1.5);
  for(let i=0;i<pts.length;i++)s+=circle(x+pts[i][0]*scale,y+pts[i][1]*scale,4.5*scale,highlight&&[1,4,7].includes(i)?C.red:'#6C777B','white');
  return s;
}
function winDoc(x,y,w=188,h=163){let s=rect(x,y,w,h,'white','#B9C3C6',12);const rows=Math.max(3,Math.min(8,Math.floor((h-20)/17)));for(let i=0;i<rows;i++){if([2,3,6].includes(i))s+=`<rect x="${x+10}" y="${y+14+i*17}" width="${w-20}" height="13" fill="${i<5?C.blue:C.pink}"/>`;s+=line(x+15,y+20+i*17,x+w-15-(i%2)*18,y+20+i*17,'#A8B2B5',1.6);}return s;}
function saveSvg(name,body,w=1200,h=460){
  const source=`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img"><defs><marker id="arrow" markerWidth="9" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#B3B9BA" stroke="#858D8F" stroke-width="0.6"/></marker></defs><rect width="${w}" height="${h}" fill="white"/>${body}</svg>`;
  fs.writeFileSync(FIG+'/'+name+'.svg',source);figures[name]=source;
}
function mechanisms(){
  let s=frame(15,18,358,420,'多路证据汇聚')+frame(405,18,358,420,'父文档重组')+frame(795,18,390,420,'事实核查与组合');
  s+=rect(36,74,316,148,'white','#D0D5D5',18)+doc(61,102,66,95,C.pink)+network(168,93,.88)+arrow(137,151,161,151)+text(192,205,'文档与图谱',21);
  s+=arrow(193,230,193,261)+rect(36,270,316,142,'white','#D0D5D5',18)+network(65,286,.79)+network(207,286,.79)+line(153,337,210,327,C.red,2,'4 3')+text(192,401,'分问题均衡召回',21);
  s+=arrow(375,230,403,230)+rect(426,74,316,148,'white','#D0D5D5',18)+doc(452,107,65,91,C.blue)+doc(522,99,65,99,C.pink)+arrow(604,151,631,151)+bars(642,121,74,15,C.green)+bars(642,148,74,15,C.purple)+bars(642,175,74,15,C.gold);
  s+=arrow(584,231,584,261)+rect(426,270,316,142,'white','#D0D5D5',18)+winDoc(454,284,145,96)+route('M608,302 L658,302 L658,350 L692,350')+stack(620,277,91)+text(583,403,'原文区间与来源',21);
  s+=arrow(766,230,793,230)+rect(816,74,348,148,'white','#D0D5D5',18)+doc(838,105,70,91,C.green)+arrow(924,151,950,151)+circle(982,120,19,C.teal)+text(982,127,'真',19)+circle(1038,161,19,C.gold)+text(1038,168,'假',19)+circle(1095,120,19,C.purple)+text(1095,127,'真',19)+line(997,130,1023,150)+line(1052,150,1082,131);
  s+=arrow(990,231,990,261)+rect(816,270,348,142,'white','#D0D5D5',18)+stack(841,280,91)+arrow(946,337,976,337)+circle(1008,337,25,C.teal)+text(1008,345,'且',22)+arrow(1038,337,1070,337)+doc(1080,290,57,88,C.teal)+text(990,403,'答案与证据链',21);
  saveSvg('机制一_总体结构',s,1200,460);
  s=frame(15,18,358,420,'候选召回')+frame(405,18,358,420,'窗口重排')+frame(795,18,390,420,'父上下文恢复');
  s+=doc(44,93,71,103,C.pink)+text(83,227,'词项',20)+network(155,93,.84)+text(211,227,'图谱',20)+stack(262,104,81)+text(300,227,'向量',20);
  s+=arrow(192,247,192,280)+bars(73,303,238,23,C.green)+bars(73,344,238,23,C.gold)+text(193,400,'排名融合',23)+arrow(374,227,403,227);
  s+=doc(432,103,61,95,C.blue)+doc(493,127,61,95,C.pink)+doc(554,151,61,95,C.purple)+arrow(639,184,704,184)+stack(651,252,74)+text(584,398,'相关窗口优先',23);
  s+=arrow(765,227,793,227)+winDoc(823,97,175,238)+arrow(1014,217,1046,217)+rect(1056,107,95,218,'white','#AEB9BD',12);
  for(let i=0;i<9;i++)s+=line(1067,126+i*21,1140,126+i*21,'#A6B0B4',1.6);
  s+=`<rect x="1065" y="164" width="78" height="65" fill="${C.blue}" opacity="0.7"/><rect x="1065" y="244" width="78" height="44" fill="${C.pink}" opacity="0.7"/>`+text(989,397,'扩展　合并　补全',23);
  saveSvg('机制二_检索重组',s,1200,460);
  s=frame(15,18,358,420,'题意分解')+frame(405,18,358,420,'独立事实核查')+frame(795,18,390,420,'三值逻辑组合');
  s+=doc(146,88,76,100,C.pink)+arrow(190,204,190,244);
  for(const [i,x]of [82,190,298].entries()){s+=circle(x,290,30,[C.blue,C.gold,C.purple][i])+text(x,298,['甲','乙','丙'][i],24);if(i!==1)s+=line(190,248,x,257);}
  s+=text(190,394,'保留来源与否定',22)+arrow(375,231,403,231)+doc(435,94,66,100,C.blue)+doc(518,120,66,100,C.gold)+doc(602,94,66,100,C.purple);
  for(const [i,x]of [470,557,644].entries())s+=arrow(x,243,x,274)+circle(x,312,29,[C.teal,C.gold,'#F0F0F0'][i])+text(x,320,['真','假','未知'][i],i===2?18:23);
  s+=text(584,394,'候选答案不进入',22)+arrow(766,231,793,231)+stack(824,107,99)+arrow(943,155,979,155)+`<polygon points="1025,108 1072,155 1025,202 978,155" fill="${C.teal}" stroke="${C.ink}" stroke-width="1.5"/>`+text(1025,164,'且',24)+route('M1025,215 L1025,254 L955,254 L955,284')+doc(915,296,87,104,C.teal)+text(1061,315,'是／否',25)+text(1061,355,'引用原文',23);
  saveSvg('机制三_逻辑核验',s,1200,460);
  s=doc(22,171,76,100,C.purple)+arrow(114,218,154,218)+circle(196,218,37,C.teal)+text(196,226,'审查',23);
  s+=frame(273,20,618,125,'证据支持')+frame(273,171,618,125,'证据缺失')+frame(273,322,618,125,'候选被反驳');
  s+=route('M235,218 L252,218 L252,94 L276,94')+arrow(236,218,276,218)+route('M235,218 L252,218 L252,393 L276,393');
  s+=network(311,55,.55)+arrow(400,93,451,93)+bars(466,70,174,21,C.teal)+bars(466,102,174,21,C.green)+arrow(657,93,736,93)+circle(779,93,25,C.teal)+text(779,101,'真',22);
  s+=doc(306,206,47,63,C.blue)+arrow(378,244,423,244)+doc(444,206,47,63,C.pink)+doc(497,206,47,63,C.gold)+arrow(567,244,624,244)+bars(640,233,194,22,C.blue);
  s+=doc(307,357,47,63,C.purple)+arrow(378,393,433,393)+`<path d="M450,382 L475,407 L509,363" stroke="${C.red}" stroke-width="4" fill="none"/>`+arrow(534,393,584,393)+doc(607,357,47,63,C.green)+arrow(682,393,733,393)+bars(748,382,87,22,C.teal);
  s+=route('M894,93 L957,93 L957,218 L1000,218')+arrow(893,244,1000,244)+route('M894,393 L957,393 L957,271 L1000,271')+doc(1020,188,122,131,C.teal)+text(1082,355,'答案与轨迹',24)+text(583,485,'保留初始证据　　最多两次生成　　最多四次图检索',22);
  saveSvg('机制四_有界纠错',s,1200,515);
  s=frame(20,20,1160,200,'推理阶段')+frame(20,247,1160,190,'评分阶段');
  s+=doc(62,89,70,91,C.blue)+text(100,199,'新闻原文',20)+arrow(152,134,218,134)+network(246,78,.75)+arrow(360,134,427,134)+doc(452,89,70,91,C.pink)+text(490,199,'问题',20)+arrow(543,134,610,134)+stack(641,92,142)+arrow(801,134,870,134)+doc(903,89,70,91,C.teal)+text(943,199,'预测答案',20);
  s+=doc(189,303,70,91,C.gold)+text(226,424,'标准答案',20)+arrow(280,345,483,345)+circle(552,345,34,C.teal)+text(552,353,'比对',22)+arrow(596,345,759,345)+bars(792,320,233,24,C.teal)+text(909,389,'逐题得分',22)+route('M941,223 L941,260 L553,260 L553,302');
  s+=route('M225,299 L225,233',true)+line(212,235,238,259,C.red,3)+line(238,235,212,259,C.red,3)+text(151,252,'不作输入',20,'middle',C.red);
  saveSvg('机制五_数据角色',s,1200,460);
  s=frame(20,20,716,414,'两篇真实报道')+frame(770,20,410,414,'命题组合与答案纠正');
  s+=doc(54,100,65,87,C.blue)+text(242,104,'卡多索',25)+circle(162,152,17,C.pink)+arrow(184,152,265,152)+circle(291,152,17,C.green)+arrow(314,152,400,152)+circle(427,152,17,C.teal)+text(162,195,'受伤',21)+text(291,195,'恢复',21)+text(427,195,'入选',21)+bars(515,128,159,22,C.blue)+text(593,193,'命题为真',21);
  s+=doc(54,273,65,87,C.gold)+text(242,278,'卡瓦利尼',25)+circle(162,326,17,C.pink)+arrow(184,326,400,326)+circle(427,326,17,C.gold)+text(162,370,'受伤',21)+text(427,370,'退出',21)+bars(515,300,159,22,C.gold)+text(593,365,'命题为真',21);
  s+=route('M740,152 L789,152 L789,228 L827,228')+route('M740,326 L789,326 L789,244 L827,244')+circle(868,236,33,C.teal)+text(868,244,'且',27)+arrow(909,236,949,236)+doc(968,180,91,114,C.teal)+text(1114,218,'否',29,'middle','#999')+line(1091,197,1136,231,C.red,3)+arrow(1114,243,1114,276)+text(1114,315,'是',34,'middle','#2B8F76');
  saveSvg('机制六_真实案例',s,1200,460);
  s=frame(20,20,600,414,'本地服务器')+frame(661,20,519,414,'语言模型接口');
  s+=rect(51,101,225,238,'#FAFAFA','#ADB8BB',12)+rect(72,122,183,60,C.blue,C.line,6)+rect(72,199,183,60,C.green,C.line,6)+rect(72,275,183,42,'white',C.line,6);
  for(const y of [151,229]){s+=circle(110,y,17,'white',C.line);for(let i=0;i<4;i++){const z=i*Math.PI/2;s+=line(110, y,110+Math.cos(z)*13,y+Math.sin(z)*13,C.line,2);}}
  s+=text(194,159,'嵌入',21)+text(194,237,'重排',21)+text(164,382,'单张显卡',23)+network(351,110,1.15)+doc(392,290,70,91,C.gold)+arrow(293,222,342,222)+text(439,382,'图谱与语料',23);
  s+=arrow(621,201,655,201)+arrow(656,273,623,273)+doc(703,115,64,85,C.pink)+doc(830,115,64,85,C.purple)+doc(960,115,64,85,C.teal)+text(741,240,'分解',22)+text(868,240,'生成',22)+text(997,240,'核查',22)+stack(758,287,292)+text(929,408,'保存原始响应与证据',23);
  saveSvg('机制七_协同部署',s,1200,460);
}
const plots=JSON.parse(fs.readFileSync(OLD+'/figures/chart_options.json','utf8'));
const translation={
 '(A) Held-out EM':'（甲）留出集匹配率','(B) Answerable EM':'（乙）可回答题匹配率','EM (%)':'完全匹配率（%）','80% target':'80%目标',
 'Base':'基础','Recovery':'补检索','Context':'候选','Verify':'验证','Full':'完整','Question-type performance on the same held-out 100':'各类问题的完全匹配率',
 'Comparison (27)':'比较（27）','Inference (36)':'推断（36）','Temporal (25)':'时间（25）','No-answer (12)':'无答案（12）',
 '(A) Verification trade-off':'（甲）验证的取舍','(B) Paired changes':'（乙）同题变化','Verify / Full':'验证／完整','Coverage':'作答率','Answered EM':'已作答匹配率','Percent (%)':'百分比（%）','Questions':'题数','Gained':'新增答对','Lost':'丢失正确',
 'Development history on a fixed 24-question set':'固定开发集的四轮迭代','Trial 1':'第一轮','Trial 2':'第二轮','Trial 3':'第三轮','Trial 4':'第四轮','Dev EM (%)':'开发匹配率（%）',
 '(A) Test-stage GPU memory':'（甲）测试显存占用','(B) GPU utilization':'（乙）计算利用率','Time (s)':'时间／秒','Memory (GiB)':'显存／吉字节','Utilization (%)':'利用率（%）'
};
function translate(o){if(typeof o==='string')return translation[o]??o;if(Array.isArray(o))return o.map(translate);if(o&&typeof o==='object')return Object.fromEntries(Object.entries(o).map(([k,v])=>[k,translate(v)]));return o;}
const plotNames={'05_overall':'数据一_总体性能','06_types':'数据二_分题型','07_ablation':'数据三_消融','08_iteration':'数据四_开发迭代','11_gpu':'数据五_显存利用率'};
const pages=[];
const p=(s,cls='')=>`<p class="${cls}">${s}</p>`;
const h=s=>`<h2>${s}</h2>`;
function tab(head,rows,w){return `<table>${w?'<colgroup>'+w.map(x=>`<col style="width:${x}%">`).join('')+'</colgroup>':''}<thead><tr>${head.map(x=>'<th>'+x+'</th>').join('')}</tr></thead><tbody>${rows.map(r=>'<tr>'+r.map((x,i)=>`<td class="${i?'':'left'}">${x}</td>`).join('')+'</tr>').join('')}</tbody></table>`;}
const fig=(name,caption,cls='')=>`<figure class="${cls}">${figures[name]}<figcaption>${caption}</figcaption></figure>`;
const formula=s=>`<div class="formula">${s}</div>`;
function page(id,title,body,chapter=''){pages.push({id,title,body,chapter});}
const refs=[
 ['开放域问答中的稠密段落检索','研究论文，2020年','https://arxiv.org/abs/2004.04906'],
 ['面向知识密集任务的检索增强生成','研究论文，2020年','https://arxiv.org/abs/2005.11401'],
 ['结合段落检索与生成模型的开放域问答','研究论文，2020年','https://arxiv.org/abs/2007.01282'],
 ['简洁高效的检索增强生成','轻量图谱检索研究，2024年','https://arxiv.org/abs/2410.05779'],
 ['从局部到全局的图谱增强查询摘要','研究论文，2024年','https://arxiv.org/abs/2404.16130'],
 ['检索与思维链交替进行的多步问答','研究论文，2023年','https://arxiv.org/abs/2212.10509'],
 ['纠错式检索增强生成','研究论文，2024年','https://arxiv.org/abs/2401.15884'],
 ['验证链减少语言模型幻觉','研究论文，2023年','https://arxiv.org/abs/2309.11495'],
 ['通过自我反思学习检索生成与批判','研究论文，2023年','https://arxiv.org/abs/2310.11511'],
 ['智源多语种重排序模型','官方模型说明','https://huggingface.co/BAAI/bge-reranker-v2-m3'],
 ['倒数排名融合检索器','开源实现','https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/retrievers/fusion_retriever.py'],
 ['跨文档多跳问答数据集','数据集与评估项目，2024年','https://github.com/yixuantt/MultiHop-RAG'],
 ['本项目算法仓库','竞赛工程实现','https://github.com/zyyyz-a/LightRAG']
];
function authorPages(){
 page('cover','证据链重组提升多跳问答质量',`<div class="school">河南大学　观微算法队</div><div class="report-type">人工智能算法竞赛技术报告</div><h1 class="cover-title">证据链重组<br>提升多跳问答质量</h1><h2 class="cover-sub">父文档融合与三值逻辑核验方法</h2><div class="cover-figure">${figures['机制一_总体结构']}</div><div class="metrics"><div><strong>86.00<span>%</span></strong><small>留出集完全匹配率</small></div><div><strong>＋31</strong><small>相对基础方案提升百分点</small></div><div><strong>609</strong><small>真实新闻文档</small></div></div><div class="cover-meta">${p('<b>参赛团队</b>　观微算法队')}${p('<b>团队成员</b>　韩昌达　张中瑜　李嘉栋')}${p('<b>所属学校</b>　河南大学')}${p('<b>提交日期</b>　2026年10月15日')}</div>`);
 const toc=[['摘要','abstract',3],['一　引言','intro',4],['二　相关工作','related',5],['三　问题设定','problem',6],['四　方法设计','method',7],['　4.1　多路召回与父文档融合','retrieval',8],['　4.2　原子事实与三值逻辑','verification',9],['　4.3　有限预算下的纠错','repair',10],['五　实验设置','setup',11],['　5.1　数据集与证据角色','setup',11],['　5.2　运行参数与对照方案','parameters',12],['　5.3　开发筛选与冻结流程','development',13],['六　实验结果','overall',14],['　6.1　整体性能','overall',14],['　6.2　分题型表现','types',15],['　6.3　消融与错误取舍','ablation',16],['　6.4　真实证据链案例','case',17],['七　工程实现与资源','engineering',18],['　7.1　模块协同与结果留存','engineering',18],['　7.2　显存与运行记录','resources',19],['八　结论','conclusion',20],['参考文献','references',21],['附录甲　评估定义与逻辑规则','appendix-a',22],['附录乙　复现材料与验证结果','appendix-b',23]];
 page('contents','目录',`<h1>目录</h1><nav class="toc">${toc.map(([name,id,n])=>`<a href="#${id}"><span>${name}</span><i></i><b>${n}</b></a>`).join('')}</nav>`);
 page('abstract','摘要',`<h1>摘要</h1>
 ${p('多跳问答需要从不同文档中找齐事实，再判断它们是否共同支持一个结论。现有段落检索、图谱检索和生成后核验分别改善了相关性、关系发现或事实检查，却仍容易在原文截断、来源限定和否定组合之间留下衔接缺口。同题实验显示，单纯补检索在100道留出题上的完全匹配率为57.00%，而重组证据并配合结构化推理后，完整流程达到86.00%。')}
 ${p('据此，我们提出观微证据链问答方法，将文档级融合、父上下文恢复与显式逻辑核验接成一条推理链。方法先按问题需求组织多路候选，再用相关性重排与原文区间合并恢复上下文，并把真假事实的判断与最终“是／否”的组合分开处理。实验围绕609篇新闻构建知识库，采用24题开发集、40题验证集和排除既往测试题的新100题留出集。最终方案确定后冻结源码与题目划分，并在同题候选、初始证据配对的条件下比较五种流程。')}
 ${p('完整流程取得86.00%的完全匹配率和86.80%的词元重合分数，相对基础方案提高31个百分点；88道可回答题的完全匹配率为84.09%，40题验证集为87.50%。比较题由14.81%升至77.78%，时间题由40.00%升至80.00%，体现了证据组织对跨来源组合的帮助。项目交付包含真实模型响应、逐题评分、原文定位和源码快照，可直接用于运行演示与结果复核。')}
 ${h('核心思路')}${p('先把问题拆成需要核对的事实，再把每条事实放回完整的报道语境，最后依据事实状态组合答案。这样，相关材料、可用证据和最终结论有了清楚的衔接。')}
 ${h('关键词')}${p('多跳问答　检索增强生成　父文档融合　证据链　三值逻辑')}
 `);
 page('intro','一 引言',`<h1>一　引言</h1>
 ${p('在609篇新闻构成的知识库中，我们抽取的100道留出题有27道比较题，基础流程只答对其中4道。对“两个来源是否表达同一件事”这样的提问，检索到同一主题并不够：报道对象、时间和归因只要有一处错位，几段看似相关的文字也无法给出正确关系。')}
 ${p('我们把这类问题称为“证据衔接缺口”：材料已经进入候选集合，能够连成答案的事实却没有完整进入推理过程。缺口既可能来自片段截断，也可能来自重复片段挤占上下文，还可能来自把“题干命题为假”误判成“否定答案不成立”。')}
 ${p('已有工作大致沿三条路线推进：稠密检索与多段融合改善候选文本获取，但不直接保证父文档语境完整[1–3]；图谱和交替检索推理加强实体关系与多步搜索，但仍需处理原文来源和问题限定之间的对齐[4–6]；纠错、验证链与自反思方法增加检查步骤，但事实判定与最终答案组合不一定显式分开[7–9]。三条路线提供了重要基础，也提示我们应把证据交接过程单独设计。')}
 ${p('观微证据链以问题和原始文档为输入，先分解证据需求，再融合词项、图谱与向量候选；重排后按字符偏移展开父文档，生成短答案与来源事实。对于能解析为布尔关系的问题，核验器在看不到候选答案的条件下判断原子事实，程序再组合“且、或、非”得到结论；证据不足时，仅按缺失内容做一次受控修复。输出同时包含答案、引用和执行轨迹。')}
 ${p('本项目的贡献集中在以下三个可交付部件：')}
 <ul><li><b>父文档证据组织器</b>：多路文档融合、按子问题选证及原文区间恢复。</li><li><b>事实与答案解耦核验器</b>：来源限定命题、候选不可见核查及三值逻辑组合。</li><li><b>可复核实验工件</b>：固定划分、配对候选、来源偏移、真实响应与冻结快照。</li></ul>
 `,'引言');
 page('related','二 相关工作',`<h1>二　相关工作</h1>
 ${p('<b>段落检索与生成融合。</b> 稠密段落检索通过双编码器获取语义相关文本[1]，检索增强生成把外部索引接入语言模型[2]，多段融合生成则在解码时汇集多条段落的信息[3]。这些方法解决了“从哪里取材料”和“怎样读取多段文字”，本项目进一步处理“局部命中怎样恢复成可组合的父文档证据”。')}
 ${p('<b>图谱组织与多步搜索。</b> 轻量图谱检索结合实体关系和向量表示[4]，全局图谱摘要通过社区结构汇聚文档信息[5]，交替检索推理让新推理步骤继续引导搜索[6]。它们分别扩展关系组织和搜索过程，本项目把这些能力接入原文层，并以来源、时间和精确偏移约束证据交接。')}
 ${p('<b>纠错与生成后核验。</b> 纠错式检索根据证据质量选择后续动作[7]，验证链通过相对独立的检查问题修订回答[8]，自反思式检索学习何时检索以及怎样评价生成[9]。这条路线强调检查与反馈，本项目则把原子事实的真假判断交给核验步骤，把答案的逻辑组合交给程序。')}
 ${h('最近邻方法的具体分工')}
 ${p('轻量图谱检索是本项目直接复用的底座，我们保留其图向量召回，把新增工作放在父文档恢复与命题组合上。纠错式检索提供质量驱动路由的启发，我们在固定语料内按缺失事实补证，并保存每次修复的原文变化。')}
 ${tab(['文献路线','已有机制','本项目的接续位置'],[['段落检索与融合','相关文本获取及多段读取','父文档语境与子问题选证'],['图谱与多步搜索','关系结构及渐进式检索','来源限定与原文区间对齐'],['纠错与验证','质量判断及生成修订','事实判定与逻辑组合分离']],[25,35,40])}
 `,'相关工作');
 page('problem','三 问题设定',`<h1>三　问题设定</h1>
 ${p('设想研究人员需要核对两篇报道：其中一篇说某球员伤后入选，另一篇说另一球员因伤退出。系统应分别找到这两条来源事实，再判断题目要求的对应关系，而不是仅因两篇都出现“伤病”就给出肯定答案。')}
 ${p('为避免符号混用，以“问”表示输入问题，“文”表示可检索文档全集，“证”表示被选中的原文片段及来源，“答”表示最终短答案，“迹”表示检索、核查和修复记录。每条“证”都记录父文档、正文起点、终点和正文总长度。')}
 ${formula('输入〔问，文〕　→　组织证据〔证〕　→　输出〔答，证，迹〕')}
 ${fig('机制五_数据角色','图1　数据角色。上层为推理时可见的原文和问题，下层为预测完成后的标准答案比对；标准答案不进入上层推理。')}
 ${h('成功判据')}
 ${formula('有效作答＝答案非空 ∧ 生成格式有效 ∧ 审查支持 ∧ 引用可定位')}
 ${formula('效果达标＝完全匹配题数 ÷ 留出题数 ≥ 80%')}
 ${p('“未知”表示现有证据不足以决定命题真假，不等同于“假”。无答案题以正确拒答计分，格式无效输出计零；具体评分和逻辑规则见附录甲。')}
 `,'问题设定');
 page('method','四 方法设计',`<h1>四　方法设计</h1>
 ${p('整个方法分为证据汇聚、父文档重组和事实组合三段。前两段决定哪些内容真正进入推理，后一段决定怎样从这些内容得到题目所问的结论。')}
 ${fig('机制一_总体结构','图2　方法总览。左侧汇聚不同检索路径，中部展开并合并原文区间，右侧核查事实并组合答案；节点、文档和向量条为结构示意。')}
 ${h('从输入到输出')}
 ${p('<b>输入。</b> 自然语言问题与既有新闻知识库。<b>处理。</b> 分解问题、多路召回、重排窗口、展开父文档、生成候选、核验事实及按需修复。<b>输出。</b> 短答案、原文引用、逻辑判断和执行轨迹。')}
 ${p('证据组织器放在生成之前，是因为缺失的来源或时间限定无法由后置核验凭空补回。逻辑组合放在事实核查之后，是为了避免把“题干被反驳”和“否定答案被反驳”混为一谈。修复器只在审查指出具体问题时启动，使额外调用有明确目标。')}
 ${h('三段之间传递什么')}
 ${p('检索段传递候选父文档；证据段传递带偏移和完整性标记的原文；核验段传递“真、假、未知”等状态以及决定结论的引用。每次传递都保留对应来源，便于在结果页回到原文。')}
 `,'方法设计');
 page('retrieval','4.1 多路召回与父文档融合',`<h1>4.1　多路召回与父文档融合</h1>
 ${p('<b>输入。</b> 原问题、最多4个证据需求以及原始文档。<b>处理。</b> 分别运行词项概率检索、图谱混合检索和向量检索，在文档层面融合排名，再对局部窗口做相关性重排[10–11]。<b>输出。</b> 按证据需求组织的父文档原文区间。')}
 ${fig('机制二_检索重组','图3　从多路候选到父文档。左侧保留互补命中，中部比较局部窗口，右侧按原文位置扩展、合并，并在预算内补全短文。图中的向量条仅示意排序。')}
 ${formula('融合分数＝各检索路径中〔1 ÷（60＋文档名次）〕之和')}
 ${p('父文档融合的存在理由很直接：命中句附近往往还有主体、时间或归因信息。若只把句子拿出来，关系可能被读错；若不加选择地增加片段，又可能让重复内容挤占另一个来源。')}
 ${p('因此，流程先按子问题保留相关窗口，再根据原文偏移向两侧展开并合并重叠区间。初始上下文不超过64,000字符；正文不超过12,000字符的已选父文档可在余量允许时补全。标题、作者、发布时间与来源同原文一起传递。')}
 ${p('最终证据保留父文档编号和起止位置，不依赖每轮临时排序编号。这样，后续核查和修复仍能定位到同一条原文。')}
 `,'方法设计');
 page('verification','4.2 原子事实与三值逻辑',`<h1>4.2　原子事实与三值逻辑</h1>
 ${p('<b>输入。</b> 问题限定的原子命题、原文证据与文档完整性标记。<b>处理。</b> 在核验输入中隐藏候选答案，独立判断命题状态，再由程序计算“且、或、非”。<b>输出。</b> 确定的肯定或否定结论，以及决定该结论的证据。')}
 ${fig('机制三_逻辑核验','图4　事实判断与答案组合分离。命题先与原文对应，核验结果进入三值逻辑，候选答案只在最后用于对照或纠正。未知状态不会直接转成假。')}
 ${p('这一组件专门处理答案极性：如果原文说“输了三场”，它反驳的是“赢了三场”这个命题，因此可以支持题目的否定答案。直接给整段候选打分，容易漏掉这一步转换。')}
 ${tab(['运算','可确定的情况','保留未知的情况'],[['且','任一项为假，则整体为假','没有假，但仍有未知'],['或','任一项为真，则整体为真','没有真，但仍有未知'],['非','真与假互换','未知仍为未知']],[17,40,43])}
 ${p('布尔形式最多8个原子命题、32个语法节点。对命名实体类问题，或布尔解析与原子证据尚不能给出结论的问题，联合证据审查可按来源事实直接重建相关证明。完整文档覆盖用于约束显式的“未提及”证明。')}
 `,'方法设计');
 page('repair','4.3 有限预算下的纠错',`<h1>4.3　有限预算下的纠错</h1>
 ${p('<b>输入。</b> 候选答案、已选证据和核验意见。<b>处理。</b> 支持则返回；缺证据则按缺失需求补检索；候选被反驳则携带审查反馈重新生成。<b>输出。</b> 修复后的答案，或保留原因的拒答。')}
 ${fig('机制四_有界纠错','图5　审查结果驱动不同动作。三条支路分别对应直接支持、缺失事实与候选反驳，最终保留答案及完整轨迹；补证不删除首轮证据。','repair')}
 ${p('修复器放在审查之后，是为了让新增查询指向真正缺少的事实，而不是反复用同一问题扩大候选数。桥接实体只有在原文里出现过，才可加入补充查询。')}
 ${p('整个流程最多补2条查询、生成2次、核验2轮，图检索总数不超过4次；最终证据不超过96,000字符和32段。若合并后没有新增内容，不因重复片段再生成一次。')}
 `,'方法设计');
 page('setup','五 实验设置',`<h1>五　实验设置</h1><h2>5.1　数据集与证据角色</h2>
 ${p('实验使用跨文档多跳问答数据集[12]。本次知识库含609篇英语新闻，处理后得到1,650个文本块、28,423个实体节点和43,733条关系边。原始新闻及其元数据用于检索，问题用于触发推理，标准答案与参考证据用于事后评分。')}
 ${tab(['数据部分','规模','用途'],[['新闻语料','609篇','建立图谱、向量与父文档索引'],['开发集','24题','定位错误并筛选四轮实现'],['独立验证集','40题','检查已选方案'],['新留出测试集','100题','冻结后的最终比较']],[30,20,50])}
 ${h('前瞻证据与事后证据分离')}
 ${p('<b>前瞻使用。</b> 题目划分与预算在测试前固定；推理只接收问题、新闻原文、文档元数据和此前产生的审查意见。<b>事后使用。</b> 标准答案、参考事实和逐题得分在预测生成后参与评分与误差分析，不回流为该轮输入。图1给出了两种角色的分流。')}
 ${p('新测试集从既有测试划分中抽取，排除已使用的200道测试题。与旧测试、开发及验证题的规范化题面完全重复数为0。每题保留全部五个流程的记录，不因失败替换样本。')}
 ${h('对照组织')}
 ${p('五组分别是基础方案、上一轮补检索、改进候选、改进验证和完整流程。后三组共享首轮候选与初始证据，因此“加验证”和“再修复”的变化可以逐题比较；基础与补检索方案也在同一批新题上重跑。')}
 `,'实验设置');
 page('parameters','5.2 运行参数与对照方案',`<h1>5.2　运行参数与对照方案</h1>
 ${p('语言模型采用深度求索的闪速接口模型，本地使用智源多语种嵌入与重排序模型。程序运行在单张4090显卡服务器上，图谱、向量与父文档索引保留在本地。原始依赖清单、模型修订标识和冻结材料见附录乙。')}
 ${tab(['环节','固定设置'],[['生成','温度为0，单次超时90秒'],['问题分解','最多4个证据需求'],['排名融合','倒数排名常数60'],['窗口与步长','1,100字符与850字符'],['重排','每查询32个候选，批量8，最长512词元'],['父文档补全','正文不超过12,000字符'],['上下文预算','初始64,000字符，最终96,000字符'],['纠错预算','2次生成、2轮核验、至多4次图检索']],[29,71])}
 ${h('五组流程的可比关系')}
 ${p('基础和补检索流程沿用原生成器；三个改进流程使用相同的结构化生成器。候选流程相对基础方案的变化包括检索、上下文与生成提示，验证流程相对候选流程只新增事实核验及逻辑纠正，完整流程再允许一次有目标的修复。')}
 ${h('可复现执行')}
 ${p('每个阶段保存题目索引、源码哈希和参数。精确输入缓存让配对分支复用同一候选与原始响应；逐题记录同时保存答案、引用和尝试次数。缓存服务于比较一致性，运行时间另以真实资源记录展示。')}
 ${p('104项工程测试覆盖来源编号、逻辑状态与执行预算，25项真实接口控制用例覆盖否定、错误年份、无关实体和证据缺失。它们与问答测试分开保存。')}
 `,'实验设置');
 page('development','5.3 开发筛选与冻结流程',`<h1>5.3　开发筛选与冻结流程</h1>
 ${p('四轮调试回答的是：严格核查是否足够，还是需要互补的证据路径？开发始终使用同一组24题，失败轮次也保留。')}
 ${fig('数据四_开发迭代','图6　固定24题开发集上的四轮变化。灰线为基础方案，黄线为改进候选，蓝线为验证流程，绿线为完整流程；各轮使用相同题目。')}
 ${tab(['轮次','主要变化','候选匹配率','完整匹配率'],[['一','事实与关系审查','91.67%','83.33%'],['二','否定措辞、作者信息及格式约束','87.50%','75.00%'],['三','严格原子命题与布尔核查','79.17%','54.17%'],['四','互补证明及解析失败保留分解','79.17%','83.33%']],[12,44,22,22])}
 ${p('第三轮的下降表明，题干解析和原子事实过于细碎时，未知状态会放大误拒。第四轮保留逻辑纠正，并允许来源明确的联合证明补充判断，完整流程回到83.33%。随后确定实现、完成40题验证、冻结源码，再运行100题留出测试。开发分数仅用于筛选，后文只把冻结后的留出结果作为主结论。')}
 `,'实验设置');
 page('overall','六 实验结果',`<h1>六　实验结果</h1><h2>6.1　整体性能</h2>
 ${p('重组证据并加入显式推理后，同一批题能多答对多少？我们同时看全量完全匹配率和可回答题匹配率，避免只用拒答结果判断效果。')}
 ${fig('数据一_总体性能','图7　新留出100题的整体表现。甲图为全量完全匹配率，乙图仅统计88道可回答题；甲图虚线为80%目标，五种流程均在同一批题目上运行。')}
 ${tab(['方案','完全匹配率','词元重合分数','可回答题匹配率'],variants.map((v,i)=>[names[i],pct(T[v].em),pct(T[v].f1),pct(T[v].answerable_em)]),[31,23,23,23])}
 ${p('完整流程达到86.00%，基础方案为55.00%，净提升31个百分点；同题配对中新增答对33题、丢失2题。可回答题匹配率为84.09%，词元重合分数为86.80%；独立验证集为87.50%，完整表见附录乙。')}
 ${p('这些结果支持证据组织与结构化推理的整体改进。由于候选流程也更换了生成提示，31个百分点不能单独归给重排序或验证器；后两者的作用需看消融比较。')}
 `,'实验结果');
 const kinds=['comparison_query','inference_query','temporal_query','null_query'];
 page('types','6.2 分题型表现',`<h1>6.2　分题型表现</h1>
 ${p('提升是否落在真正需要跨来源组合的问题上？我们将100题拆成比较、推断、时间和无答案四类，观察同题对照的变化。')}
 ${fig('数据二_分题型','图8　四类问题的完全匹配率，括号内为各类题数。灰、黄、绿三组柱分别对应基础方案、改进候选和完整流程。')}
 ${tab(['题型','题数','基础匹配率','完整匹配率','提升百分点'],kinds.map((k,i)=>[['比较','推断','时间','无答案'][i],T.v2_full.by_kind[k].n,pct(T.baseline.by_kind[k].em),pct(T.v2_full.by_kind[k].em),(100*(T.v2_full.by_kind[k].em-T.baseline.by_kind[k].em)).toFixed(2)]),[18,12,23,23,24])}
 ${p('比较题由14.81%升至77.78%，提高62.96个百分点；时间题由40.00%升至80.00%。推断题达到91.67%，12道无答案题均正确拒答。最大的改善落在需要保留多篇报道限定条件的题型，与父上下文和按需求选证的设计相吻合。')}
 ${p('分题型结果说明整体收益并非平均分摊，但样本数不同，不能据此排出所有题型的稳定难度；这里比较的是同一批问题上的流程变化。')}
 `,'实验结果');
 page('ablation','6.3 消融与错误取舍',`<h1>6.3　消融与错误取舍</h1>
 ${p('验证器是在提高整体正确率，还是在减少已经输出的错误？这两个目标需要分开看。我们比较共享候选和初始证据的改进候选流程与验证流程。')}
 ${fig('数据三_消融','图9　验证的收益与代价。甲图纵轴从70%起，展示作答率与已作答匹配率；乙图为相对候选流程新增答对及丢失正确的题数。')}
 ${p('加验证后，全量完全匹配率由88.00%变为86.00%，非空错答由10题减至8题；已作答匹配率由88.37%升至90.24%，作答率由86%降至82%。验证新增答对3题，同时丢失5题；完整流程额外补证后，净分数仍为86.00%。')}
 ${p('因此，验证器本轮主要换来了错误抑制与可核查轨迹，而没有净提高匹配率。整体提升首先来自前端证据组织及生成的组合升级，后续应围绕来源限定和否定判断减少误拒，而不是继续一味收紧审查。')}
 `,'实验结果');
 page('case','6.4 真实证据链案例',`<h1>6.4　真实证据链案例</h1>
 ${p('核验器能否纠正一次具体的否定判断？测试题1960询问，两篇体育报道中“卡多索伤后入选”和“卡瓦利尼因伤退出”是否形成题目所说的对应关系。以下是两条证据的中文转述，原文定位见附录乙。')}
 ${fig('机制六_真实案例','图10　真实题1960的证据组合。卡多索的受伤、恢复和入选来自文档231；卡瓦利尼因伤退出来自文档232；两项核查支持题干，候选“否”被纠正为“是”。')}
 ${p('第一条报道写明，卡多索因脚踝伤退出此前集训，恢复俱乐部比赛后入选名单；第二条写明，加拿大队当时唯一的伤病缺席是卡瓦利尼，他在两场比赛前退出。首轮候选为“否”，原子核查重建两项来源事实后，最终答案为“是”，与标准答案一致。')}
 ${p('这个样例展示的是独立重建证据如何纠正候选，而不是看到否定答案就将其放行。全测试中共有6次候选极性纠正，其中3次符合标准答案，因此仍要用完整消融结果评价该机制。')}
 `,'实验结果');
 page('engineering','七 工程实现与资源',`<h1>七　工程实现与资源</h1><h2>7.1　模块协同与结果留存</h2>
 ${p('服务器只承担本地嵌入、重排和知识计算，语言生成与事实检查通过深度求索接口完成。检索期间不接入外部网页搜索，所有引用都映射到固定语料中的原文。')}
 ${fig('机制七_协同部署','图11　本地计算与模型接口的协同。左侧显卡与语料承担嵌入、重排和图谱计算，右侧完成分解、生成与核查，原始响应和证据轨迹分别留存。')}
 ${p('程序按父文档组织器、事实核验器、逻辑组合器、纠错控制器和实验驱动器拆分。模块之间传递带来源的结构化记录，避免每次查询临时重编号；最终答案可以沿着引用、正文偏移和审查结果回溯。')}
 ${h('测试与复核')}
 ${p('104项工程测试已通过，覆盖来源编号、逻辑组合、完整性判断和预算；25项真实模型接口控制用例全部通过。实验阶段共保存700条独立验证及测试记录，连同开发集共复算1,180条完全匹配率与词元重合分数。')}
 ${p('交付保留完整源码、失败轮次、精确输入缓存和每个文件的哈希。原始实验材料与报告图表分开保存，修改展示文字不会改变已冻结的成绩。')}
 `,'工程与资源');
 page('resources','7.2 显存与运行记录',`<h1>7.2　显存与运行记录</h1>
 ${p('单卡方案的本地负担有多大？我们在验证和测试阶段约每秒记录一次显存与计算利用率，用连续采样观察模型加载、检索计算和接口等待期间的资源变化。')}
 ${fig('数据五_显存利用率','图12　真实测试阶段的显存与利用率。甲图单位为二进制吉字节，乙图灰线为采样值、蓝线为局部均值；时间轴单位为秒。')}
 ${tab(['指标','验证阶段','测试阶段'],[['显卡','4090显卡','4090显卡'],['采样次数','546','1,268'],['显存峰值／兆字节','5,245','5,129'],['计算利用率峰值','99%','100%'],['本地生成模型','不运行','不运行']],[44,28,28])}
 ${p('验证与测试的显存采样峰值为5,245兆字节，约5.12吉字节，单位均为二进制。全部开发、控制检查及主实验共记录1,386条模型响应，累计6,225,251词元。测试结束后显存已释放。')}
 ${p('这些记录覆盖本轮验证和测试，不含首次图谱入库。共享缓存用于同题配对，所以图中资源曲线可以说明实际运行负担，但不用于宣称各分支的独立速度差异。')}
 `,'工程与资源');
 page('conclusion','八 结论',`<h1>八　结论</h1>
 ${p('多跳问答的改进需要把相关材料组织成能共同支持结论的证据链。本文通过父文档融合、事实与答案组合分离及有限预算修复，把原文获取、上下文恢复和逻辑判断接成可追踪的流程。真实模型实验表明，这一组合显著改善了同题整体表现，尤其是跨来源比较与时间关系问题。下一步将在新的留出样本上校准来源限定和非提及判断，重点减少验证器对正确候选的损失。')}
 ${h('应用定位')}
 ${p('该方法适合需要回看依据的新闻研究、企业资料核对和知识助手。使用者不仅获得简短答案，也能看到支撑答案的原文区间与组合过程，便于判断哪些事实已经找到、哪些仍需补充。')}
 ${h('结论适用范围')}
 <ul><li>本文分数对应固定新闻语料和新100题留出集；其他领域应使用新的问题划分验证。</li><li>程序负责给定事实状态下的逻辑组合，题干解析与原子事实状态仍由模型判断。</li></ul>
 ${h('数据与使用责任')}
 ${p('语料采用公开数据集，报告不包含服务器口令或模型密钥。系统提供答案与证据供人核查，不承诺脱离人工审核的自主决策部署。')}
 ${h('团队')}${p('河南大学　观微算法队<br>韩昌达　张中瑜　李嘉栋')}
 `,'结论');
 page('references','参考文献',`<h1>参考文献</h1><div class="references">${refs.map(([title,info,url],i)=>p(`<b>[${i+1}] ${title}</b><br>${info}　<a href="${url}">原文链接</a>`)).join('')}</div>`);
 page('appendix-a','附录甲 评估定义与逻辑规则',`<h1>附录甲　评估定义与逻辑规则</h1>
 ${h('一　评分口径')}${p('完全匹配率：按既有归一化规则比较预测与标准答案，完全匹配记1，否则记0。词元重合分数：按重合词元计算精确率与召回率的调和均值。无答案题的标准答案为空，格式无效输出一律计零。')}
 ${formula('词元重合分数＝2×精确率×召回率÷（精确率＋召回率）')}
 ${p('作答率为输出非空答案的比例；已作答匹配率仅在作答题上计算；可回答题匹配率仅在非空标准答案题上计算。报告中的肯定与否定答案统一写成“是／否”，对应日志中的原始答案标签。')}
 ${h('二　三值组合为何成立')}${p('对合取关系，只要有一项确定为假，整体即为假；其余项不会改变该结论。对析取关系，只要有一项为真，整体即为真。若没有决定性项而仍存在未知，则结果保持未知。程序保存造成决定性结论的命题集合，形成证据证书。')}
 ${p('这保证了已给定原子状态之间的组合一致性。完整父文档判断通过合并正文区间完成：覆盖从0到正文总长度且不存在间隙时，才标记为完整。')}
 ${h('三　补充统计')}${p('完整流程完全匹配率的威尔逊95%区间为77.86%至91.47%；相对基础流程的配对自助法差值区间为增加21至41个百分点。精确配对检验的双侧概率约为0.0000000367，统计对象为本次100题。')}
 ${h('四　样本与失败保留')}${p('开发共480条方案记录、独立验证200条、测试500条，合计1,180条。原基础测试流程有4条生成格式错误，完整流程为0条；全部按统一口径保留，不替换题目。')}
 `,'附录');
 page('appendix-b','附录乙 复现材料与验证结果',`<h1>附录乙　复现材料与验证结果</h1>
 ${h('一　原始材料')}
 ${tab(['材料','可核查内容'],[['实验协议与冻结文件','题目索引、预算、源码哈希及冻结时间'],['逐题结果','答案、候选、原文、偏移和评分'],['模型响应缓存','精确输入与原始输出'],['依赖与模型记录','运行环境、模型修订和参数'],['失败轮次源码','四轮开发的实现与对应结果']],[38,62])}
 ${p('运行环境采用解释器3.12.3、张量计算框架2.7.0、图检索库1.5.7、句向量库5.7.0。开发、验证与测试抽样种子分别为2026101511、2026101512和2026101513；补丁、模型标识及完整依赖写在原始交付材料内。')}
 ${p('案例1960的两项来源分别定位到文档231的正文0至6374字符，以及文档232的正文9950至13373字符。报告作中文转述，原始英文和核查响应在逐题材料中保留。')}
 ${h('二　独立验证集尾表')}
 ${tab(['流程','完全匹配率','作答率','已作答匹配率'],variants.map((v,i)=>[names[i],pct(V[v].em),pct(V[v].coverage),pct(V[v].selective_accuracy)]),[34,22,22,22])}
 ${p('验证集共40题，其中32题可回答。完整流程答对35题，作答30题，非空错答3题。该表对应测试前已完成的独立验证，不与主测试题目混合计分。')}
 `,'附录');
}
async function main(){
 mechanisms();
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const chartPage=await browser.newPage({viewport:{width:1200,height:800}});
  await chartPage.setContent('<html><body style="margin:0"><div id="chart"></div></body></html>');
  await chartPage.addScriptTag({path:OLD+'/echarts-5.6.0.min.js'});
  const hanPlots={};
  for(const [oldName,spec]of Object.entries(plots)){
   const translated=translate(spec);translated.option.textStyle.fontFamily='Microsoft YaHei';
   for(const axis of (Array.isArray(translated.option.yAxis)?translated.option.yAxis:[translated.option.yAxis])){
    if(axis&&axis.name){axis.nameGap=14;axis.nameTextStyle={...(axis.nameTextStyle||{}),fontSize:14};}
   }
   if(JSON.stringify(spec.option.series.map(s=>s.data))!==JSON.stringify(translated.option.series.map(s=>s.data)))throw Error('Data changed '+oldName);
   hanPlots[plotNames[oldName]]=translated;
   const source=await chartPage.evaluate(({width,height,option})=>{const d=document.getElementById('chart');echarts.getInstanceByDom(d)?.dispose();d.style.width=width+'px';d.style.height=height+'px';const c=echarts.init(d,null,{renderer:'svg',width,height});c.setOption(option);const s=d.querySelector('svg');s.removeAttribute('style');s.setAttribute('viewBox',`0 0 ${width} ${height}`);s.setAttribute('xmlns','http://www.w3.org/2000/svg');return s.outerHTML;},translated);
   figures[plotNames[oldName]]=source;fs.writeFileSync(FIG+'/'+plotNames[oldName]+'.svg',source);
  }
  fs.writeFileSync(FIG+'/数据图配置.json',JSON.stringify(hanPlots,null,2));
  authorPages();
  const css=`@page{size:A4;margin:0}*{box-sizing:border-box;letter-spacing:0}body{margin:0;background:#e7e7e7;color:#202020;font:10.7pt/1.8 SimSun,serif}.page{position:relative;width:210mm;height:297mm;padding:23mm 22mm 19mm;margin:7mm auto;background:white;break-after:page;page-break-after:always}.page:last-child{break-after:auto;page-break-after:auto}.body{height:254mm}h1,h2{font-family:'Microsoft YaHei',sans-serif;color:black}h1{font-size:21pt;line-height:1.35;margin:0 0 5mm}h2{font-size:12.1pt;line-height:1.5;margin:4mm 0 2mm}p{margin:0 0 3.8mm;text-align:justify;overflow-wrap:anywhere}b{font-weight:700}a{color:inherit;text-decoration:none}.running,.footer{position:absolute;left:22mm;right:22mm;display:flex;justify-content:space-between;font:8pt 'Microsoft YaHei',sans-serif;color:#666}.running{top:10mm}.footer{bottom:9mm}.formula{text-align:center;font-size:11.2pt;line-height:1.8;margin:4mm 0}figure{margin:4.2mm 0}figure svg{display:block;width:100%;height:auto;max-height:91mm}figure.repair svg{max-height:99mm}figcaption{font-size:9pt;line-height:1.6;color:#444;margin-top:2.2mm}table{border-collapse:collapse;table-layout:fixed;width:100%;margin:3.2mm 0 4.2mm;font-size:9.4pt;line-height:1.5}th,td{border:.6pt solid #D9D9D9;padding:2.2mm 2.4mm;text-align:center;vertical-align:middle;overflow-wrap:anywhere}th{background:#ECEFF0;font:600 9.1pt/1.5 'Microsoft YaHei',sans-serif}td.left{text-align:left}tbody tr:nth-child(even){background:#F7F8F8}ul{margin:2mm 0 4mm;padding-left:6mm}li{margin-bottom:3mm}.toc a{display:flex;gap:3mm;align-items:baseline;line-height:1.92;font-size:10.7pt}.toc i{flex:1;border-bottom:1px dotted #BBB}.toc b{font:10pt SimSun}.references p{font-size:10pt;line-height:1.55;margin-bottom:3.7mm}.references a{color:#555}.cover .body{height:254mm}.school{font:11pt 'Microsoft YaHei',sans-serif;margin-bottom:10mm}.report-type{font:12pt 'Microsoft YaHei',sans-serif;margin-bottom:7mm}.cover-title{font:700 30pt/1.5 'Microsoft YaHei',sans-serif;margin:0 0 5mm}.cover-sub{font:700 16pt/1.6 'Microsoft YaHei',sans-serif;margin:0 0 7mm}.cover-figure{margin:8mm -3mm}.cover-figure svg{width:100%;height:auto;max-height:78mm}.metrics{display:flex;justify-content:space-between;margin:10mm 0 10mm}.metrics strong{display:block;font:700 26pt 'Microsoft YaHei',sans-serif}.metrics strong span{font-size:13pt}.metrics small{display:block;font:9pt 'Microsoft YaHei',sans-serif;color:#444;margin-top:2mm}.cover-meta p{line-height:2.4;margin:0;text-align:left}.cover-meta b{font-family:'Microsoft YaHei',sans-serif}@media print{body{background:white}.page{margin:0}}`;
  const html=`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>证据链重组提升多跳问答质量 观微算法队</title><style>${css}</style></head><body>${pages.map((r,i)=>`<section class="page ${i?'':'cover'}" id="${r.id}">${i?'<header class="running"><span>观微证据链问答方法</span><span>河南大学　观微算法队</span></header>':''}<main class="body">${r.body}</main>${i?`<footer class="footer"><span>${r.chapter||'参赛技术报告'}</span><span>${i+1}／${pages.length}</span></footer>`:''}</section>`).join('')}</body></html>`;
  const htmlPath=OUT+'/观微证据链参赛报告.html',pdfPath=OUT+'/观微证据链参赛报告.pdf';
  fs.writeFileSync(htmlPath,html);
  const report=await browser.newPage({viewport:{width:1000,height:1250}});
  await report.goto(pathToFileURL(htmlPath).href);await report.evaluate(()=>document.fonts.ready);
  const check=await report.evaluate(()=>{const visible=document.body.innerText;return{latin:visible.match(/[A-Za-z]+/g)||[],version:visible.includes('版本'),layout:[...document.querySelectorAll('.page')].map((p,i)=>{const b=p.querySelector('.body');return{page:i+1,id:p.id,height:b.clientHeight,scrollHeight:b.scrollHeight,overflow:b.scrollHeight>b.clientHeight+2};})};});
  fs.writeFileSync(QA+'/文字与版式检查.json',JSON.stringify(check,null,2));
  if(check.latin.length||check.version)throw Error('Non-Chinese visible text '+JSON.stringify(check.latin));
  if(check.layout.some(p=>p.overflow))throw Error('Overflow '+JSON.stringify(check.layout.filter(p=>p.overflow)));
  await report.pdf({path:pdfPath,format:'A4',printBackground:true,preferCSSPageSize:true,tagged:true,outline:true,margin:{top:0,bottom:0,left:0,right:0}});
  const pdf=await PDFDocument.load(fs.readFileSync(pdfPath));if(pdf.getPageCount()!==pages.length)throw Error('Wrong pagination');
  pdf.setTitle('证据链重组提升多跳问答质量');pdf.setAuthor('河南大学 观微算法队 韩昌达 张中瑜 李嘉栋');pdf.setSubject('父文档融合与三值逻辑核验方法');fs.writeFileSync(pdfPath,await pdf.save());
  const poppler='C:/Users/fanzhen/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe';
  const r=spawnSync(poppler,['-r','110','-png',pdfPath,QA+'/page'],{encoding:'utf8',timeout:120000,windowsHide:true});if(r.status!==0)throw Error(r.stderr);
  const pngs=fs.readdirSync(QA).filter(x=>/^page-\d+\.png$/.test(x)).sort();
  for(let first=0;first<pngs.length;first+=4){const inputs=[];for(let i=0;i<Math.min(4,pngs.length-first);i++)inputs.push({input:await sharp(QA+'/'+pngs[first+i]).resize({width:500}).png().toBuffer(),left:i%2*520,top:Math.floor(i/2)*727});await sharp({create:{width:1040,height:1454,channels:3,background:'#DDD'}}).composite(inputs).png().toFile(QA+'/总览'+(first/4+1)+'.png');}
  for(const [name,s]of Object.entries(figures))await sharp(Buffer.from(s)).resize({width:2400}).flatten({background:'white'}).png().toFile(FIG+'/'+name+'.png');
  const manifest={页数:pages.length,机制图:7,数据图:5,正文英文字母:check.latin.length,版本标记:false,数据图数值保持原样:true,排版溢出页:[],文件哈希:crypto.createHash('sha256').update(fs.readFileSync(pdfPath)).digest('hex')};
  fs.writeFileSync(OUT+'/报告核对记录.json',JSON.stringify(manifest,null,2));
  const zip=new JSZip();for(const f of ['观微证据链参赛报告.pdf','观微证据链参赛报告.html','报告核对记录.json'])zip.file(f,fs.readFileSync(OUT+'/'+f));for(const f of fs.readdirSync(FIG))zip.file('图表/'+f,fs.readFileSync(FIG+'/'+f));zip.file('生成脚本.cjs',fs.readFileSync(__filename));zip.file('原始统计.json',fs.readFileSync(INPUT+'/results/audit_and_comparison.json'));fs.writeFileSync(OUT+'/参赛报告与图表素材.zip',await zip.generateAsync({type:'nodebuffer',compression:'DEFLATE',compressionOptions:{level:6}}));
  console.log(JSON.stringify(manifest));
 }finally{await browser.close();}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
