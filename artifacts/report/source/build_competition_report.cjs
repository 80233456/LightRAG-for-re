/* Data-driven competition report. Node, Graphviz, ECharts and Chromium only. */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { createRequire } = require('module');
const { spawnSync } = require('child_process');
const req = createRequire('C:/Users/fanzhen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_report.cjs');
const { chromium } = req('playwright');
const { instance } = req('@viz-js/viz');
const { PDFDocument } = req('pdf-lib');
const sharp = req('sharp');
const JSZip = req('jszip');
const BASE = 'D:/project/ai算法';
const INPUT = path.join(BASE, 'deliverables/20261015_v2/lightrag_v2_20261015');
const OUT = path.join(BASE, 'deliverables/competition_report_20261015');
const FIG = path.join(OUT, 'figures');
const QA = path.join(OUT, 'qa');
for (const p of [OUT, FIG, QA]) fs.mkdirSync(p, { recursive: true });
const read = p => JSON.parse(fs.readFileSync(path.join(INPUT, p), 'utf8'));
const jsonl = p => fs.readFileSync(path.join(INPUT,p),'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
const audit = read('results/audit_and_comparison.json');
const test = jsonl('results/test/records.jsonl');
const val = audit.validation;
const T = audit.test;
const protocol = read('protocol.json');
const esc = s => String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const percent = n => (100*n).toFixed(2)+'%';
const cols = { base:'#8D939D', previous:'#B5A2C6', context:'#E9C966', verify:'#78A8C8', full:'#41A697', wrong:'#D57869' };
const labels = ['基础方案','上一轮补检索','V2候选流程','V2验证流程','V2完整流程'];
const variants = ['baseline','previous_recovery','v2_context','v2_verify','v2_full'];
const colors = [cols.base,cols.previous,cols.context,cols.verify,cols.full];
const figures = new Map();
const configs = {};

function svg(name, source) {
  source = source.replace(/<svg /, '<svg role="img" ');
  fs.writeFileSync(path.join(FIG,name+'.svg'), source);
  figures.set(name, source);
}
function fig(name, caption, cls='') {
  return `<figure class="${cls}">${figures.get(name)}<figcaption>${caption}</figcaption></figure>`;
}
function p(text, cls='') { return `<p class="${cls}">${text}</p>`; }
function h2(text) { return `<h2>${text}</h2>`; }
function table(headers, rows, widths=null) {
  return `<table>${widths?'<colgroup>'+widths.map(w=>`<col style="width:${w}%">`).join('')+'</colgroup>':''}<thead><tr>${headers.map(h=>'<th>'+h+'</th>').join('')}</tr></thead><tbody>${rows.map(r=>'<tr>'+r.map((v,i)=>`<td class="${i===0?'left':''}">${v}</td>`).join('')+'</tr>').join('')}</tbody></table>`;
}
const pages = [];
function page(id, title, body, chapter='') { pages.push({id,title,body,chapter}); }
function panel(text) { return `<div class="formula">${text}</div>`; }
function bullet(title, text) { return `<p><b>${title}</b>　${text}</p>`; }

async function main() {
  const viz = await instance();
  const graph = (name, body, direction='LR') => svg(name, viz.renderString(`digraph G {
    graph [rankdir=${direction}, bgcolor="transparent", pad="0.16", nodesep="0.26", ranksep="0.48", fontname="Arial", fontsize=17, compound=true];
    node [shape=box, style="rounded,filled", fillcolor="white", color="#777777", penwidth=1.15, fontname="Arial", fontsize=17, margin="0.14,0.12"];
    edge [color="#767676", arrowsize=0.7, penwidth=1.15, fontname="Arial", fontsize=12];
    ${body}
  }`, {format:'svg', engine:'dot'}));

  graph('01_architecture', `
    q [label="Question q", fillcolor="#F4F4F4"];
    subgraph cluster_a { label="A   Evidence acquisition"; style="rounded,dashed"; color="#777777";
      plan [label="Facet planner\nsource / entity / time", fillcolor="#F3E4DA"];
      bm [label="BM25", fillcolor="#F4E9B7"]; g [label="LightRAG\ngraph + vector", fillcolor="#D9EAF0"];
      rrf [label="RRF + BGE reranking", fillcolor="#E1ECD5"]; parent [label="Parent-body expansion\nmetadata + exact spans", fillcolor="#E1ECD5"];
      plan -> {bm g}; {bm g} -> rrf; rrf -> parent;
    }
    subgraph cluster_b { label="B   Evidence-grounded inference"; style="rounded,dashed"; color="#777777";
      gen [label="Structured candidate\nanswer + facts + source IDs", fillcolor="#EAE0F0"];
      atom [label="Candidate-blind\natomic checks", fillcolor="#DAEBE6"];
      logic [label="Three-valued logic\nAND / OR / NOT", fillcolor="#DAEBE6"];
      joint [label="Joint evidence audit", fillcolor="#F4E9B7"];
      gen -> atom -> logic; atom -> joint [label="unresolved",style=dashed];
    }
    out [label="Answer + evidence trace", fillcolor="#D1E8E1"];
    repair [label="Bounded repair\nretrieval / regeneration", fillcolor="#F3E4DA"];
    q -> plan; parent -> gen; {logic joint} -> out; joint -> repair [label="missing facts",style=dashed]; repair -> parent [style=dashed,constraint=false];
  `);
  graph('02_retrieval', `
    subgraph cluster_a {label="Multi-route document retrieval";style="rounded,dashed";color="#777777";
      q [label="Question + up to 4 facets",fillcolor="#F3E4DA"];
      b [label="Lexical BM25",fillcolor="#F4E9B7"]; g [label="Graph mix retrieval",fillcolor="#D9EAF0"]; v [label="Naive vector retrieval",fillcolor="#E4DFEE"];
      q -> {b g v};
    }
    fuse [label="Document RRF\nk = 60",fillcolor="#DAEBE6"];
    win [label="Literal sliding windows\n1100 chars / 850 stride",fillcolor="#D9EAF0"];
    rank [label="BGE cross-encoder\n32 candidates / query",fillcolor="#E1ECD5"];
    expand [label="Expand + merge body spans\ncomplete short parents",fillcolor="#F4E9B7"];
    result [label="Balanced evidence context\n64k initial / 96k final",fillcolor="#DAEBE6"];
    {b g v} -> fuse; fuse -> win -> rank -> expand -> result;
  `);
  graph('03_verifier', `
    subgraph cluster_a {label="Question semantics";style="rounded,dashed";color="#777777";
      q [label="Question as asked",fillcolor="#F3E4DA"];
      ast [label="Source-qualified atoms\nbounded Boolean AST",fillcolor="#EAE0F0"]; q -> ast;
    }
    e [label="Cited source passages\ncomplete-body flags",fillcolor="#D9EAF0"];
    check [label="Atomic evidence checker\nno candidate answer supplied",fillcolor="#DAEBE6"];
    truth [label="True / False / Unknown",fillcolor="#F4E9B7"];
    compose [label="Programmatic composition\nproof certificate",fillcolor="#DAEBE6"];
    yes [label="Resolved Yes / No",fillcolor="#D1E8E1"];
    joint [label="Joint proof audit\nfor unresolved evidence",fillcolor="#F3E4DA"];
    ast -> check; e -> check -> truth -> compose -> yes;
    truth -> joint [label="unknown",style=dashed];
    candidate [label="Original candidate\nkept for comparison",fillcolor="#F4F4F4"];
    candidate -> yes [label="accept / correct",style=dashed];
  `);
  graph('04_repair', `
    start [label="Initial candidate + evidence",fillcolor="#EAE0F0"];
    judge [label="Evidence audit",fillcolor="#DAEBE6"];
    ok [label="Supported\nreturn answer + citations",fillcolor="#D1E8E1"];
    missing [label="Insufficient\nup to 2 missing-facet queries",fillcolor="#F4E9B7"];
    refute [label="Refuted candidate\naudit-informed regeneration",fillcolor="#F3E4DA"];
    stop [label="Invalid / unresolved conflict\nreturn abstention",fillcolor="#E5E5E5"];
    merge [label="Preserve initial evidence\nmerge new parent spans",fillcolor="#D9EAF0"];
    again [label="One repair attempt\nsecond audit",fillcolor="#DAEBE6"];
    start -> judge; judge -> {ok missing refute stop}; missing -> merge -> again; refute -> again;
    again -> ok; again -> stop [label="still unresolved"];
  `,'TB');
  graph('09_case', `
    subgraph cluster_sources {label="Retrieved original evidence";style="rounded,dashed";color="#777777";
      a [label="Sporting News   USA squad\nCardoso: ankle injury -> return -> inclusion",fillcolor="#D9EAF0"];
      b [label="Sporting News   Canada squad\nCavallini: withdrawal due to injury",fillcolor="#F4E9B7"];
    }
    facts [label="Independent atomic checks\nA: supported    B: supported",fillcolor="#DAEBE6"];
    op [label="Question-level composition\nA AND B = True",fillcolor="#EAE0F0"];
    answer [label="Candidate No -> Final Yes\ngold answer: Yes",fillcolor="#D1E8E1"];
    {a b} -> facts -> op -> answer;
  `);
  graph('10_deployment', `
    subgraph cluster_local {label="Single GPU server   RTX 4090";style="rounded,dashed";color="#777777";
      emb [label="GPU   BGE-M3\nlocal embeddings",fillcolor="#D9EAF0"];
      rank [label="GPU   BGE reranker\nlocal cross-encoder",fillcolor="#E1ECD5"];
      store [label="CPU / disk   LightRAG\ngraph + vector + parent corpus",fillcolor="#F4E9B7"];
      orchestrator [label="EvidenceChain controller\nretrieve / compose / repair",fillcolor="#EAE0F0"];
      trace [label="Evidence and experiment logs\nJSONL / hashes / provenance",fillcolor="#F4F4F4"];
      emb -> store; store -> rank -> orchestrator; orchestrator -> trace;
    }
    api [label="DeepSeek-flash API\nplanning / generation / fact checks",fillcolor="#DAEBE6"];
    user [label="User question"];
    user -> orchestrator; orchestrator -> api [dir=both];
  `);

  // Use compact multi-stage panels so labels remain legible at A4 print size.
  const stage=(rows)=>`<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="8" CELLPADDING="10" COLOR="#B9B9B9">${rows.map(([text,color])=>`<TR><TD BGCOLOR="${color}">${text}</TD></TR>`).join('')}</TABLE>>`;
  const modular=(name,definitions,edges)=>graph(name,definitions.map((s,i)=>`subgraph cluster_${i} {label="${s.title}";style="rounded,dashed";color="#777777"; n${i} [shape=plain,style="",fontsize=20,label=${stage(s.rows)}];}`).join('\n')+edges);
  modular('01_architecture',[
    {title:'A   Hybrid evidence retrieval',rows:[['Question + evidence facets','#F3E4DA'],['BM25 / Graph / Vector','#D9EAF0'],['Document-level RRF','#F4E9B7']]},
    {title:'B   Parent-context organization',rows:[['BGE window reranking','#E1ECD5'],['Literal parent-body spans','#D9EAF0'],['Source metadata + provenance','#E1ECD5']]},
    {title:'C   Verified inference',rows:[['Structured candidate','#EAE0F0'],['Atomic facts / joint proof','#DAEBE6'],['Three-valued logic + citations','#DAEBE6']]}
  ],'n0 -> n1 -> n2; n2 -> n1 [label="bounded repair",style=dashed,constraint=false];');
  modular('02_retrieval',[
    {title:'A   Candidate acquisition',rows:[['Question + up to 4 facets','#F3E4DA'],['BM25 / Graph mix / Vector','#D9EAF0'],['Document RRF    k = 60','#F4E9B7']]},
    {title:'B   Relevance selection',rows:[['Windows: 1100 chars','#D9EAF0'],['BGE cross-encoder ranking','#E1ECD5'],['32 candidates per query','#E1ECD5']]},
    {title:'C   Evidence reconstruction',rows:[['Expand and merge body spans','#F4E9B7'],['Complete short parent texts','#E1ECD5'],['64k initial / 96k final context','#DAEBE6']]}
  ],'n0 -> n1 -> n2;');
  modular('03_verifier',[
    {title:'A   Input decomposition',rows:[['Source-qualified claims','#F3E4DA'],['Bounded Boolean expression','#EAE0F0'],['Original passages + coverage','#D9EAF0']]},
    {title:'B   Independent atomic checks',rows:[['Candidate answer NOT supplied','#DAEBE6'],['True / False / Unknown','#F4E9B7'],['Known source IDs only','#DAEBE6']]},
    {title:'C   Answer composition',rows:[['Programmatic AND / OR / NOT','#EAE0F0'],['Resolved answer + proof trace','#DAEBE6'],['Joint audit if unresolved','#F3E4DA']]}
  ],'n0 -> n1 -> n2;');
  modular('10_deployment',[
    {title:'A   Single GPU server',rows:[['BGE-M3 embeddings','#D9EAF0'],['BGE cross-encoder reranker','#E1ECD5'],['Graph / vector / parent corpus','#F4E9B7']]},
    {title:'B   EvidenceChain controller',rows:[['Retrieve / generate / audit','#EAE0F0'],['Logic composition + repair','#DAEBE6'],['Evidence and experiment logs','#F4F4F4']]},
    {title:'C   DeepSeek-flash API',rows:[['Question planning','#DAEBE6'],['Structured answer generation','#EAE0F0'],['Source-grounded fact checks','#DAEBE6']]}
  ],'n0 -> n1; n1 -> n2 [dir=both];');

  const echartsFile = path.join(OUT,'echarts-5.6.0.min.js');
  if (!fs.existsSync(echartsFile)) {
    const response = await fetch('https://cdnjs.cloudflare.com/ajax/libs/echarts/5.6.0/echarts.min.js');
    if (!response.ok) throw new Error('Cannot obtain ECharts: '+response.status);
    fs.writeFileSync(echartsFile, Buffer.from(await response.arrayBuffer()));
  }
  const browser = await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const chartPage = await browser.newPage({viewport:{width:1200,height:800}});
    await chartPage.setContent('<html><body style="margin:0"><div id="chart"></div></body></html>');
    await chartPage.addScriptTag({path:echartsFile});
    const axis = {axisLine:{show:true,lineStyle:{color:'#444',width:1}},axisTick:{show:true},axisLabel:{fontSize:18,color:'#222'},splitLine:{lineStyle:{color:'#e4e4e4',type:'dashed'}}};
    const chart = async (name, option, width=1000,height=470) => {
      option = {animation:false,textStyle:{fontFamily:'Arial',fontSize:18,color:'#222'},...option};
      configs[name]={width,height,option};
      const source = await chartPage.evaluate(({option,width,height})=>{
        const dom=document.getElementById('chart');
        echarts.getInstanceByDom(dom)?.dispose();
        dom.style.width=width+'px';dom.style.height=height+'px';
        const c=echarts.init(dom,null,{renderer:'svg',width,height});c.setOption(option);
        const s=dom.querySelector('svg');s.removeAttribute('style');
        s.setAttribute('viewBox',`0 0 ${width} ${height}`);
        s.setAttribute('xmlns','http://www.w3.org/2000/svg');
        return s.outerHTML;
      },{option,width,height});
      svg(name,source);
    };
    await chart('05_overall',{
      title:[{text:'(A) Held-out EM',left:40,top:10,textStyle:{fontSize:23}},{text:'(B) Answerable EM',left:545,top:10,textStyle:{fontSize:23}}],
      grid:[{left:75,top:65,width:400,bottom:85},{left:580,top:65,width:390,bottom:85}],
      xAxis:[{...axis,type:'category',data:['Base','Recovery','Context','Verify','Full'],axisLabel:{fontSize:17,rotate:20}},{...axis,type:'category',gridIndex:1,data:['Base','Recovery','Context','Verify','Full'],axisLabel:{fontSize:17,rotate:20}}],
      yAxis:[{...axis,min:0,max:100,interval:20,name:'EM (%)',nameTextStyle:{fontSize:18}},{...axis,min:0,max:100,interval:20,gridIndex:1,name:'EM (%)',nameTextStyle:{fontSize:18}}],
      series:[{type:'bar',barWidth:45,data:variants.map((v,i)=>({value:+(100*T[v].em).toFixed(2),itemStyle:{color:colors[i],borderColor:'#555',borderWidth:0.7}})),label:{show:true,position:'top',fontSize:22,formatter:'{c}'},markLine:{symbol:'none',label:{formatter:'80% target',position:'insideEndTop',fontSize:16},lineStyle:{type:'dashed',color:'#ab6958'},data:[{yAxis:80}]}},
        {type:'bar',xAxisIndex:1,yAxisIndex:1,barWidth:45,data:variants.map((v,i)=>({value:+(100*T[v].answerable_em).toFixed(2),itemStyle:{color:colors[i],borderColor:'#555',borderWidth:0.7}})),label:{show:true,position:'top',fontSize:18,formatter:'{c}'}}]
    });
    const kinds=['comparison_query','inference_query','temporal_query','null_query'];
    await chart('06_types',{
      title:{text:'Question-type performance on the same held-out 100',left:'center',top:8,textStyle:{fontSize:23}},
      legend:{top:44,data:['Base','Context','Full'],textStyle:{fontSize:19}},
      grid:{left:75,right:35,top:100,bottom:65},
      xAxis:{...axis,type:'category',data:['Comparison (27)','Inference (36)','Temporal (25)','No-answer (12)'],axisLabel:{fontSize:18}},
      yAxis:{...axis,min:0,max:100,interval:20,name:'EM (%)',nameTextStyle:{fontSize:18}},
      series:[['Base','baseline',cols.base],['Context','v2_context',cols.context],['Full','v2_full',cols.full]].map(([name,v,color])=>({name,type:'bar',barWidth:45,itemStyle:{color,borderWidth:0.7,borderColor:'#555'},data:kinds.map(k=>+(100*T[v].by_kind[k].em).toFixed(1)),label:{show:true,position:'top',fontSize:17,formatter:'{c}'}}))
    },1000,470);
    await chart('07_ablation',{
      title:[{text:'(A) Verification trade-off',left:35,top:8,textStyle:{fontSize:22}},{text:'(B) Paired changes',left:555,top:8,textStyle:{fontSize:22}}],
      legend:{data:['Context','Verify / Full'],left:80,top:44,textStyle:{fontSize:18}},
      grid:[{left:70,top:100,width:410,bottom:75},{left:610,top:100,width:350,bottom:75}],
      xAxis:[{...axis,type:'category',data:['Coverage','Answered EM'],axisLabel:{fontSize:18}},{...axis,type:'category',gridIndex:1,data:['Gained','Lost'],axisLabel:{fontSize:18}}],
      yAxis:[{...axis,min:70,max:100,interval:10,name:'Percent (%)',nameTextStyle:{fontSize:18}},{...axis,gridIndex:1,min:0,max:6,interval:1,name:'Questions',nameTextStyle:{fontSize:18}}],
      series:[{name:'Context',type:'bar',barWidth:55,itemStyle:{color:cols.context,borderColor:'#555',borderWidth:0.7},data:[86,88.37],label:{show:true,position:'top',fontSize:20}},
        {name:'Verify / Full',type:'bar',barWidth:55,itemStyle:{color:cols.full,borderColor:'#555',borderWidth:0.7},data:[82,90.24],label:{show:true,position:'top',fontSize:20}},
        {type:'bar',xAxisIndex:1,yAxisIndex:1,barWidth:80,data:[{value:audit.paired_comparisons[2].gains,itemStyle:{color:cols.full}},{value:audit.paired_comparisons[2].losses,itemStyle:{color:cols.wrong}}],label:{show:true,position:'top',fontSize:25}}]
    },1000,430);
    const trials=Object.keys(audit.dev).sort();
    await chart('08_iteration',{
      title:{text:'Development history on a fixed 24-question set',left:'center',top:8,textStyle:{fontSize:23}},
      legend:{top:45,data:['Base','Context','Verify','Full'],textStyle:{fontSize:18}},
      grid:{left:80,right:50,top:100,bottom:65},
      xAxis:{...axis,type:'category',data:['Trial 1','Trial 2','Trial 3','Trial 4'],boundaryGap:true},
      yAxis:{...axis,min:30,max:100,interval:10,name:'Dev EM (%)',nameTextStyle:{fontSize:18}},
      series:[['Base','baseline',cols.base],['Context','v2_context',cols.context],['Verify','v2_verify',cols.verify],['Full','v2_full',cols.full]].map(([name,v,color],i)=>({name,type:'line',data:trials.map(k=>+(audit.dev[k][v].em*100).toFixed(2)),symbol:i===3?'diamond':'circle',symbolSize:i===3?13:9,lineStyle:{width:i===3?4:2,type:i===2?'dashed':'solid'},itemStyle:{color},label:{show:i===3,position:'bottom',fontSize:19,formatter:'{c}'}}))
    },1000,460);
    const samples=jsonl('results/gpu_test_samples.jsonl');
    const t0=samples[0].time;
    const selected=samples.filter((r,i)=>i%3===0 || i===samples.length-1);
    const smoothUtil=selected.map((r,i)=>{const j=i*3;const group=samples.slice(Math.max(0,j-5),Math.min(samples.length,j+6));return [+(r.time-t0).toFixed(1), +(group.reduce((s,x)=>s+x.utilization_percent,0)/group.length).toFixed(1)];});
    await chart('11_gpu',{
      title:[{text:'(A) Test-stage GPU memory',left:40,top:8,textStyle:{fontSize:22}},{text:'(B) GPU utilization',left:555,top:8,textStyle:{fontSize:22}}],
      grid:[{left:80,top:70,width:390,bottom:70},{left:590,top:70,width:370,bottom:70}],
      xAxis:[{...axis,type:'value',name:'Time (s)',nameLocation:'middle',nameGap:38,nameTextStyle:{fontSize:18},max:'dataMax'},{...axis,type:'value',gridIndex:1,name:'Time (s)',nameLocation:'middle',nameGap:38,nameTextStyle:{fontSize:18},max:'dataMax'}],
      yAxis:[{...axis,type:'value',min:0,max:6,interval:1,name:'Memory (GiB)',nameTextStyle:{fontSize:18}},{...axis,type:'value',gridIndex:1,min:0,max:100,interval:25,name:'Utilization (%)',nameTextStyle:{fontSize:18}}],
      series:[{type:'line',showSymbol:false,lineStyle:{width:2,color:cols.full},areaStyle:{color:'#DAEBE6',opacity:0.6},data:selected.map(r=>[+(r.time-t0).toFixed(1),+(r.memory_used_mib/1024).toFixed(3)])},
        {type:'line',xAxisIndex:1,yAxisIndex:1,showSymbol:false,lineStyle:{width:1,color:'#888'},data:selected.map(r=>[+(r.time-t0).toFixed(1),r.utilization_percent])},
        {type:'line',xAxisIndex:1,yAxisIndex:1,showSymbol:false,lineStyle:{width:2.4,color:cols.verify},data:smoothUtil}]
    },1000,420);
    fs.writeFileSync(path.join(FIG,'chart_options.json'),JSON.stringify(configs,null,2));
    console.log('FIGURES_READY',figures.size);

    // Each numbered sheet is authored as one A4 page; navigation follows these fixed pages.
    page('cover','EvidenceChain RAG',`
      <div class="cover-top">河南大学　·　观微算法队</div>
      <div class="cover-type">人工智能算法竞赛技术报告</div>
      <h1 class="cover-name">EvidenceChain RAG</h1>
      <h2 class="cover-title">面向多跳问答的证据链增强<br>检索与逻辑验证</h2>
      <p class="cover-en">Evidence-grounded Multi-hop Retrieval and Logical Verification</p>
      <div class="cover-visual">${figures.get('01_architecture')}</div>
      <div class="cover-metrics"><div><strong>86.00<span>%</span></strong><small>新留出集 EM</small></div><div><strong>+31<span>pp</span></strong><small>相对基础方案提升</small></div><div><strong>609</strong><small>真实新闻文档</small></div></div>
      <div class="cover-meta"><p><b>参赛团队</b>　观微算法队</p><p><b>团队成员</b>　韩昌达　张中瑜　李嘉栋</p><p><b>所属学校</b>　河南大学</p><p><b>报告版本</b>　V2.0　　<b>提交日期</b>　2026年10月15日</p></div>
    `);
    const toc=[['摘要','abstract',3],['1　问题定义与技术目标','problem',4],['2　总体架构与实现路径','architecture',5],['3　核心算法设计','retrieval',6],['　3.1　混合召回与父上下文','retrieval',6],['　3.2　原子事实与逻辑验证','verification',7],['　3.3　有限预算纠错','repair',8],['4　实验设计与评估协议','protocol',9],['5　实验结果与分析','results',10],['　5.1　总体性能','results',10],['　5.2　分题型能力','types',11],['　5.3　消融与收益归因','ablation',12],['　5.4　多轮开发迭代','iterations',13],['6　典型案例与证据链','case',14],['7　工程实现与资源效率','engineering',15],['　7.1　模块架构与交付','engineering',15],['　7.2　GPU资源与部署','resources',16],['8　项目价值与后续规划','conclusion',17],['参考文献','references',18],['附录　材料索引与评估定义','appendix',19]];
    page('contents','目录',`<h1>目录</h1><nav class="toc">${toc.map(([name,id,n])=>`<a href="#${id}"><span>${name}</span><i></i><b>${String(n).padStart(2,'0')}</b></a>`).join('')}</nav><div class="toc-note">主要图表：系统架构图 · 混合检索流程图 · 逻辑验证图 · 总体性能图 · 分题型对比图 · 消融分析图 · 开发迭代图 · 真实证据链案例 · GPU运行曲线</div>`);
    page('abstract','摘要',`<h1>摘要</h1>
      ${p('多跳问答要求系统从分散文档中定位多个事实，并在来源、时间和否定语义约束下完成组合推理。围绕检索证据不完整、上下文截断和答案验证极性混淆等问题，我们在LightRAG基础上构建EvidenceChain RAG，将文档级混合召回、父上下文恢复、原子事实核验和受控纠错组织为统一的证据推理流程。')}
      ${p('系统采用BM25与LightRAG图向量检索的互补召回，通过倒数排名融合与BGE交叉编码器重排获得高质量候选证据；随后根据原文字符偏移恢复父文档上下文。针对Yes/No问题，系统将题干转换为来源限定的原子命题，由候选答案不可见的核验步骤判断事实状态，再以三值逻辑完成答案组合与极性纠正。')}
      ${p('在609篇真实新闻构成的知识库上，我们使用DeepSeek-flash API与本地BGE模型完成真实模型验证。新留出100题的完整流程EM达到86.00%，F1达到86.80%，相对同批基础方案提升31个百分点；40题独立验证集EM为87.50%。在88道可回答题上，EM达到84.09%。系统同时保留答案、证据、原始响应和逻辑轨迹，实现了从结果展示到过程复核的完整闭环。')}
      ${h2('项目核心贡献')}
      ${bullet('一　证据组织能力升级','由单段截取转向文档级融合与父上下文恢复，显著改善跨文档比较和时间关系问题的证据覆盖。')}
      ${bullet('二　事实判断与答案组合解耦','将原子命题核验和程序逻辑计算分离，使否定、合取与来源约束具有显式的处理路径。')}
      ${bullet('三　面向交付的工程闭环','以有限预算控制修复流程，完成真实API验收、逐题复算、来源校验及源码哈希冻结。')}
      ${p('<b>关键词</b>　检索增强生成　多跳问答　知识图谱　证据链　逻辑验证','keywords')}
      <div class="abstract-en"><b>Abstract</b><p>EvidenceChain RAG integrates hybrid document retrieval, parent-context recovery, atomic fact checking and bounded corrective inference. On a new 100-question MultiHop-RAG holdout, the complete pipeline achieves 86.00% normalized EM and 86.80% F1, improving EM by 31 percentage points over the paired baseline. A separate 40-question validation reaches 87.50% EM. The implementation combines local BGE models with the DeepSeek-flash API and preserves auditable evidence traces.</p></div>
    `);
    page('problem','1 问题定义与技术目标',`<h1>1　问题定义与技术目标</h1>
      ${h2('1.1　从检索命中到多文档推理')}
      ${p('企业知识问答、新闻研究和专业资料分析通常不能依靠单条文本直接回答。一个问题可能同时要求识别实体、匹配报道来源、比较时间顺序，并判断“没有发生”“未提及”或“是否一致”等语义。系统不仅需要检索相关材料，还需要确保多个事实能够共同支持问题所要求的关系。')}
      ${p('我们将任务表示为：给定问题q和文档集合D，输出简洁答案a及其证据集合E，并保存从E到a的推理轨迹。对于证据不足的情形，流程允许拒答或开展一次有目标的补证，而不是依赖生成模型补全缺失事实。')}
      ${panel('输入　q，D　→　检索与证据组织　→　候选答案与事实　→　逻辑核验　→　输出　a，E，trace')}
      ${h2('1.2　历次调试暴露的三个瓶颈')}
      ${bullet('证据截断','旧流程主要读取片段前部，网页头部与无关段落占用上下文，关键事实即使命中原文也可能未进入生成器。')}
      ${bullet('跨源组合不足','同一主题的片段容易重复占据排名，独立子问题需要的另一来源未被充分覆盖；直接扩大top-k未必补齐缺失的一跳。')}
      ${bullet('验证目标混淆','“题干命题为假”和“候选No答案为假”是不同判断。将二者混为一谈，会使验证器拒绝原本正确的答案。')}
      ${h2('1.3　参赛版本的设计目标')}
      ${table(['目标维度','实现要求','本轮完成情况'],[['问答效果','新留出集EM达到80%目标','86.00%'],['证据追踪','答案可关联原文与来源编号','精确偏移与程序引用'],['运行方式','服务器承担本地检索与向量计算','DeepSeek API + 本地BGE'],['工程验收','真实模型运行与可复核数据','104项测试及25项API控制用例']],[18,45,37])}
      ${p('项目着眼于已有开源能力的深度整合和针对性算法改造，以实际问题驱动设计、以真实数据验证改进，形成可落地的多跳问答方案。')}
    `,'问题与目标');
    page('architecture','2 总体架构与实现路径',`<h1>2　总体架构与实现路径</h1>
      ${p('EvidenceChain RAG以“证据获取—证据组织—候选推理—验证与修复”为主链路。LightRAG提供图与向量检索基础[1]，BGE承担本地表征与重排序[2]，DeepSeek-flash完成问题分解、结构化生成和事实核验。新增控制层统一管理证据来源、逻辑表达式与修复预算。')}
      ${fig('01_architecture','图1　EvidenceChain RAG总体架构。虚线表示条件路由，实线表示主要数据流。','wide-diagram')}
      ${h2('2.1　离线知识组织与在线证据推理')}
      ${p('离线阶段，将609篇新闻文档构建为LightRAG知识库，并保留原始父文档、标题、作者、发布时间和来源。在线阶段，问题先拆解为最多4个证据需求，再由多路检索形成候选文档池，经重排序和父上下文恢复后进入推理模块。')}
      ${h2('2.2　双路径验证与受控反馈')}
      ${p('对可解析为布尔表达式的问题，优先执行候选不可见的原子事实核验，再由程序计算Yes/No。命名实体类问题采用联合证据审查；当布尔解析或原子证据未解决时，也可通过明确的联合证明补充判断。核验结果驱动补检索或重新生成，避免无限重试。')}
      ${table(['层级','核心职责','关键输出'],[['检索层','BM25、图检索、向量检索与RRF','候选父文档'],['证据层','交叉编码器重排、原文扩展与去重','带偏移的证据片段'],['推理层','结构化生成、原子核查与逻辑组合','候选及解析后的结论'],['控制层','预算、条件修复、来源校验与日志','可追踪的最终答案']],[16,53,31])}
    `,'总体架构');
    page('retrieval','3 核心算法设计',`<h1>3　核心算法设计</h1><h2>3.1　混合召回与父上下文恢复</h2>
      ${p('单一路径检索对问题表达与文本组织方式较为敏感。我们在文档层面融合BM25词项匹配与LightRAG图向量召回，并对原问题及子问题分别组织候选。倒数排名融合使用标准RRF形式[3]，无需直接比较不同检索器的原始分数。')}
      ${panel('RRF(d) = Σ<sub>r∈R</sub> 1 / (60 + rank<sub>r</sub>(d))')}
      ${fig('02_retrieval','图2　多路文档召回、重排序与父上下文恢复流程。','wide-diagram')}
      ${p('融合后的候选进入长度1100字符、步长850字符的原文滑窗。每个查询最多重排32个窗口，以BGE交叉编码器判断局部相关性。系统再按证据需求均衡保留片段，并根据精确偏移向两侧扩展、合并同文档的重叠区间。')}
      ${h2('父上下文为何关键')}
      ${p('多跳关系常在报道后半段、补充说明或相邻段落中出现。只保留局部命中句容易失去时间、主体和归因信息。父文档恢复将相关窗口还原为连贯原文，在预算允许时补全较短文章，同时纳入来源和发表时间，提升跨来源证据的可组合性。')}
      ${table(['参数','取值','作用'],[['初始上下文','≤64,000字符','扩展语义覆盖'],['最终上下文','≤96,000字符及32段','控制修复后的总预算'],['完整父文档升级','正文≤12,000字符','补全文档语境'],['证据标识','文档编号与起止偏移','稳定映射至真实原文']],[33,30,37])}
      ${p('这一步不仅增加上下文长度，也改变证据的组织方式：从“相似片段堆叠”转向“按问题需求分配的可定位证据”。')}
    `,'核心算法');
    page('verification','3.2 原子事实与逻辑验证',`<h1>3.2　原子事实与逻辑验证</h1>
      ${p('针对否定和跨来源比较问题，我们将“原子事实是否成立”与“问题应答Yes还是No”分开处理。规划器生成最多8个来源限定命题及有界布尔表达式；核验器仅接收命题和原文，不显示候选答案。程序随后使用True、False、Unknown三值状态计算结论。')}
      ${fig('03_verifier','图3　候选不可见的事实核验与显式逻辑组合。候选答案只参与最终对照，不进入原子核验输入。','wide-diagram')}
      ${table(['组合规则','有决定性证据时','证据尚不充分时'],[['A AND B','任一为False，可确定False','无False但存在Unknown，则Unknown'],['A OR B','任一为True，可确定True','无True但存在Unknown，则Unknown'],['NOT A','True与False互换','Unknown保持Unknown']],[22,34,44])}
      ${h2('从否定句到答案极性')}
      ${p('例如“报道是否称某队赢了三场”，若原文明确写的是“输了三场”，被反驳的是“赢了三场”这一命题，正确答案应为No。显式组合使系统不再把对题干命题的反驳直接解释为对No答案的反驳。')}
      ${h2('证据引用与来源完整性')}
      ${p('模型仅选择已有证据编号，程序从真实段落复制引用文本，保留父文档起止偏移。对于“文章未提及某事”的判断，显式非提及证明要求完整父文档覆盖；对于尚未解决的事实，可采用联合证据审查路径。该设计参考答案独立检查思想[5]，形成了适合本项目的可执行验证流程。')}
    `,'核心算法');
    page('repair','3.3 有限预算纠错',`<h1>3.3　有限预算纠错</h1>
      ${p('我们将验证结果直接转化为下一步行动，而不是只输出一个通过分数。受纠错式RAG思路启发[4]，流程区分证据缺失、候选被反驳和引用无效等情形，使每次修复都对应明确原因。')}
      ${fig('04_repair','图4　有限预算下的验证与修复控制。支持路径直接返回，缺证据与候选反驳分别触发有针对性的动作。','repair-diagram')}
      ${table(['核验状态','控制动作','预算规则'],[['Supported','输出答案与引用','不再增加调用'],['Insufficient','按缺失证据需求补查询','至多2条补充查询'],['Refuted','携带审查反馈重新生成','至多2次总生成'],['Invalid或未解决冲突','返回拒答与审查记录','不无限重试']],[23,43,34])}
      ${p('补检索不会丢弃首轮证据；新片段与原文区间合并后再进入第二轮推理。若使用候选实体构造桥接查询，该实体必须已真实出现在检索原文中。系统将总图检索次数限制为4次，验证至多2轮，每轮至多2种审查。')}
      ${p('该机制将可解释性和可控性落实到执行层：不仅保留“最后答了什么”，也保留“为何补检索、补了什么、是否改变候选”。')}
    `,'核心算法');
    page('protocol','4 实验设计与评估协议',`<h1>4　实验设计与评估协议</h1>
      ${h2('4.1　真实知识库与样本划分')}
      ${p('本轮评估使用MultiHop-RAG新闻语料[6]，知识库包含609篇已完成处理的文档、1,650个文本块、28,423个实体节点和43,733条关系边。算法只从语料原文建立父文档索引，推理输入不包含标准答案或参考证据标签。')}
      ${table(['集合','题数','用途','规则'],[['开发集','24','定位问题并比较4轮实现','仅开发阶段用于调整'],['验证集','40','验证固定方案','最终版本确定后运行一次'],['新留出测试集','100','最终效果评估','冻结代码后运行，排除旧200题']],[20,12,30,38])}
      ${h2('4.2　五组同题对照')}
      ${p('基础方案与上一轮补检索方案在同一批新题上重新运行。新版设置候选流程、验证流程和完整流程三个分支，使用相同首轮候选与初始证据进行配对比较，分别观察整体流程改进、验证取舍和补证修复的效果。')}
      ${table(['方案','检索与生成','验证与修复'],[['基础方案','原LightRAG适配与原生成器','无新增验证'],['上一轮补检索','原候选与适应性补检索','不启用V2验证'],['V2候选流程','混合召回、父上下文、新生成器','不加验证'],['V2验证流程','与V2候选流程共享首轮输入','原子逻辑或联合核验'],['V2完整流程','同上，允许有目标的补证','验证与一次有界修复']],[23,43,34])}
      ${h2('4.3　指标与执行记录')}
      ${p('主要指标为归一化token EM与F1，同时记录可回答题EM、作答率、已作答EM和非空错答。格式无效输出按预定规则计零，不剔除或替换题目。验证与测试共形成700条方案级记录；连同4轮开发共复算1,180条记录。')}
      ${p('本文主成绩对应新留出100题，反例检查单独统计；本轮未新增RAGBench得分。精确输入缓存服务于配对复用，分支耗时不作为独立在线延迟比较。','small')}
    `,'实验设计');
    page('results','5 实验结果与分析',`<h1>5　实验结果与分析</h1><h2>5.1　总体性能</h2>
      ${p('完整流程在新留出集取得86.00% EM与86.80% F1，超过本轮80%目标，相对基础方案提升31个百分点。与此同时，88道可回答题的EM达到84.09%，说明提升并不只来自无答案题的正确拒答。')}
      ${fig('05_overall','图5　新留出100题上的总体EM与可回答题EM。虚线为本轮80%目标线。')}
      ${table(['方案','EM','F1','验证集EM'],variants.map((v,i)=>[labels[i],percent(T[v].em),percent(T[v].f1),percent(val[v].em)]),[37,21,21,21])}
      ${h2('同题配对提升')}
      ${p('相对基础方案，V2完整流程新增答对33题、丢失2题，净增加31道正确答案；相对上一轮补检索，新增答对31题、丢失2题，净提升29个百分点。40题独立验证集EM为87.50%，与新留出结果呈现一致的整体提升方向。')}
      ${p('V2候选流程达到88.00% EM，是召回、上下文恢复与结构化生成共同改造的效果；完整流程进一步加入证据审查与纠错，在效果与审查能力之间形成可配置取舍。')}
    `,'实验结果');
    page('types','5.2 分题型能力',`<h1>5.2　分题型能力</h1>
      ${p('我们将新留出题目按比较、推断、时间和无答案四类分别统计。改进最明显的两类，恰好对应前期调试暴露的跨来源证据与时间上下文问题。')}
      ${fig('06_types','图6　分题型EM对比。括号内为各类题数，所有方案使用同一批问题。')}
      ${table(['题型','题数','基础EM','完整EM','提升'],kinds.map((k,i)=>{const a=T.baseline.by_kind[k].em,b=T.v2_full.by_kind[k].em;return [['比较','推断','时间','无答案'][i],T.v2_full.by_kind[k].n,percent(a),percent(b),(100*(b-a)).toFixed(2)+'pp'];}),[20,12,22,22,24])}
      ${h2('跨来源比较能力显著增强')}
      ${p('比较题由14.81%提升到77.78%，提升62.96个百分点。文档级多路召回与分问题均衡选证，降低了同主题重复片段对上下文的挤占；父上下文保留原报道的归因与限定，使系统能够比较不同来源的实际表述。')}
      ${h2('时间问题由局部命中转向语境判断')}
      ${p('时间题由40.00%提升到80.00%。标题、发表时间、主体与原文事件描述共同进入推理过程，减少了因文章片段不完整而造成的判断缺口。推断题达到91.67%，12道无答案题均正确拒答。')}
    `,'实验结果');
    page('ablation','5.3 消融与收益归因',`<h1>5.3　消融与收益归因</h1>
      ${p('消融实验将“整体性能增强”与“验证器贡献”分开呈现。新版候选流程为88.00% EM，启用验证后为86.00%；验证使非空错答由10题降至8题，已作答EM由88.37%提升至90.24%，同时作答率由86%降至82%。')}
      ${fig('07_ablation','图7　验证流程的效果取舍。左图从70%起展示作答率与已作答EM；右图为相对未验证流程新增答对与丢失的题数。')}
      ${table(['对照','新增答对','丢失正确','净EM变化'],[['基础 → 完整','33','2','+31pp'],['旧补检索 → 完整','31','2','+29pp'],['V2候选 → V2验证','3','5','−2pp'],['V2验证 → V2完整','0','0','0pp']],[46,18,18,18])}
      ${h2('验证器的实际价值与下一步')}
      ${p('验证器能够将部分极性错误纠正为有据答案，并提供可追踪的原子事实与引用。在本轮样本中，其主要作用体现为错误抑制和证据审查，而非净EM增加。6次Yes/No候选纠正中3次符合标准答案；仍有过于严格的来源或非提及判断，后续应重点改善语义校准。')}
      ${p('补证流程将平均图检索次数从2.00增加到2.34，本轮未产生额外净得分。比赛版本保留其有界执行与完整日志，便于在更复杂知识库中继续开展成本收益评估。')}
      ${p('因此，31个百分点的主收益应归于检索、上下文与生成的组合升级；验证模块是对可信推理和过程可解释性的进一步建设。')}
    `,'实验结果');
    page('iterations','5.4 多轮开发迭代',`<h1>5.4　多轮开发迭代</h1>
      ${p('我们没有将优化停留在参数调节，而是沿着真实失败案例逐层定位：先修复上下文与证据覆盖，再处理否定极性、解析丢失与过度拒答。固定24题开发集上的四轮结果如下。')}
      ${fig('08_iteration','图8　固定开发集的四轮迭代。曲线用于展示开发过程，不与独立留出集分数混合比较。')}
      ${table(['轮次','核心变化','候选EM','完整EM'],[['Trial 1','原子事实与关系审查','91.67%','83.33%'],['Trial 2','否定措辞、作者元数据、格式约束','87.50%','75.00%'],['Trial 3','严格原子命题与布尔审查','79.17%','54.17%'],['Trial 4','互补核验与解析失败保留分解','79.17%','83.33%']],[15,51,17,17])}
      ${h2('从严格过滤走向互补证据审查')}
      ${p('Trial 3表明，把复杂问题全部强制压入单一路径，会因题干解析偏差和原子证据未知而误拒正确候选。最终版本保留布尔路径的极性纠正能力，同时允许有效联合证据证明补充判断，并修复了逻辑形式失败时检索子问题一并丢失的问题。')}
      ${p('最终实现于验证前选定。完成40题验证后冻结源码及协议哈希，再运行新的100题留出测试，形成“开发定位—固定验证—独立测试”的完整迭代链路。')}
    `,'开发迭代');
    const example=test.find(r=>r.variant==='v2_full'&&r.index===1960);
    if(!example || example.em!==1 || example.output.answer!=='Yes')throw new Error('Case evidence mismatch');
    const citeTexts=example.output.verification.verdicts.flatMap(v=>v.citations);
    const extract=(term)=>{
      const c=citeTexts.find(x=>x.quote.toLowerCase().includes(term.toLowerCase()));
      if(!c)throw new Error('Missing case quote '+term);
      const at=c.quote.toLowerCase().indexOf(term.toLowerCase());
      const a=at;
      const sep=c.quote.indexOf('\n\n',at);
      const b=sep>=0&&sep-at<400?sep:Math.min(c.quote.length,at+320);
      return {id:c.id,text:c.quote.slice(a,b).trim()};
    };
    const ca=extract('Johnny Cardoso had'),cb=extract('The only injury absence for Canada');
    fs.writeFileSync(path.join(OUT,'case_evidence.json'),JSON.stringify({index:1960,query:example.query,scoring_gold:example.scoring_gold,candidate:example.output.candidate_answer,answer:example.output.answer,excerpts:[ca,cb],verification:example.output.verification},null,2));
    page('case','6 典型案例与证据链',`<h1>6　典型案例与证据链</h1>
      ${p('<b>真实测试样例　编号1960</b>　问题要求判断：Sporting News关于美国队阵容的报道，是否提到Johnny Cardoso伤后入选，与其关于加拿大队Lucas Cavallini因伤退出的报道形成对应。标准答案为Yes。')}
      <div class="quote"><b>原文证据A　${esc(ca.id)}</b><p>${esc(ca.text)} […]</p></div>
      <div class="quote"><b>原文证据B　${esc(cb.id)}</b><p>${esc(cb.text)} […]</p></div>
      ${fig('09_case','图9　真实样例的原子核查与答案纠正。英文摘录为原文局部，完整证据及偏移保存在逐题记录中。','case-diagram')}
      ${p('首轮候选为No。独立原子核查分别确认“Cardoso曾因脚踝伤势退出、恢复后入选”和“Cavallini因伤退出”两个来源事实。系统据此完成题目层面的关系组合，将答案纠正为Yes，与标准答案一致。')}
      ${p('该案例体现了验证器从“检查答案字面”转向“独立重建相关证据”的能力。题干、首轮候选、原子判断、最终答案和引用文本均被完整保留，可直接用于展示和答辩。')}
    `,'案例分析');
    page('engineering','7 工程实现与资源效率',`<h1>7　工程实现与资源效率</h1><h2>7.1　模块架构与交付</h2>
      ${p('系统采用本地知识计算与远端语言模型服务协同的部署方式。本地GPU运行BGE-M3和BGE reranker，CPU与磁盘维护图谱、向量及父文档；DeepSeek-flash API承担规划、生成和事实核查。无需在服务器部署本地Qwen生成模型。')}
      ${fig('10_deployment','图10　单卡本地计算与DeepSeek API协同架构。检索推理过程只使用实验语料，不接入外部网页搜索。','wide-diagram')}
      ${table(['模块','关键实现','职责'],[['parent_retrieval.py','BM25、RRF、重排与父文档','组织高质量证据'],['facet_verifier.py','问题分解与联合证据审查','结构化生成及证据证明'],['boolean_verifier.py','原子命题及三值逻辑','答案极性与逻辑组合'],['corrective.py','状态路由与修复预算','完整推理控制'],['v2_experiment.py','固定划分、缓存与冻结','可配对实验与数据留存']],[32,39,29])}
      ${h2('从算法运行到可复核交付')}
      ${p('104项工程测试覆盖逻辑边界、来源编号、完整性判断和修复预算；25项真实API控制用例覆盖错误年份、无关实体、注入文本、否定、跨源组合及未知事实。交付包保留原始响应缓存、逐题评分、源码快照和文件哈希，实现结果与实现的一一关联。')}
    `,'工程实现');
    const gpuVal=read('results/gpu_validation_summary.json'),gpuTest=read('results/gpu_test_summary.json');
    page('resources','7.2 GPU资源与部署',`<h1>7.2　GPU资源与部署</h1>
      ${p('实验在单张RTX 4090上完成。本地仅承担向量表征、交叉编码器重排与图算法，语言模型能力通过API调用获取。验证和测试阶段持续记录GPU资源，最高采样显存为5,245 MiB，约5.12 GiB，形成轻本地生成负担的部署形态。')}
      ${fig('11_gpu','图11　真实测试阶段GPU曲线。显存按原始数据降采样展示；利用率灰线为采样值，蓝线为局部均值。')}
      ${table(['指标','验证阶段','测试阶段'],[['GPU','RTX 4090','RTX 4090'],['采样记录数',gpuVal.samples,gpuTest.samples],['显存采样峰值','5,245 MiB','5,129 MiB'],['GPU利用率峰值','99%','100%'],['本地生成模型','不部署','不部署']],[42,29,29])}
      ${h2('运行环境与调用量')}
      ${p('环境采用Python 3.12.3、PyTorch 2.7.0+cu128、LightRAG 1.5.7与sentence-transformers 5.7.0。全开发、控制检查及主实验日志共记录1,386条API响应，累计6,225,251 token；共享缓存用于配对复用，交互问答另记。')}
      ${p('资源数据来自约每秒采样，覆盖本轮验证和测试，不包含首次图谱入库；实际部署可根据上下文预算、重排批量和并发量进行配置。测试完成后GPU已释放。','small')}
      ${p('该架构将本地计算重点放在知识检索和证据组织上，使项目能够以单卡完成真实知识库实验，同时保留更换API模型与扩展本地检索服务的灵活性。')}
    `,'资源效率');
    page('conclusion','8 项目价值与后续规划',`<h1>8　项目价值与后续规划</h1>
      ${h2('8.1　以证据组织驱动问答质量跃升')}
      ${p('EvidenceChain RAG在既有LightRAG基础上，完成了从“检索片段后直接生成”到“文档融合、上下文恢复与逻辑核验”的系统升级。新留出集86.00% EM、独立验证集87.50% EM及可回答题84.09% EM，共同构成了本轮真实模型验收结果。')}
      ${p('项目最突出的增益出现在跨源比较和时间关系任务：前者提升62.96个百分点，后者提升40个百分点。它们直接回应了多跳检索中“找到了主题，却没有找齐事实”的核心问题，证明面向证据链的组织方式具有明确的应用价值。')}
      ${h2('8.2　兼顾问答能力与过程可解释性')}
      ${p('系统把问题分解、原子事实、来源偏移、逻辑表达式和修复动作组织为统一轨迹。对需要审核的知识问答，用户不仅能够看到答案，也能定位支撑该答案的原始材料。这种可追踪设计适用于企业资料分析、新闻研究、知识助手和专业信息核对等应用方向。')}
      ${h2('8.3　后续优化路线')}
      ${table(['方向','具体动作','预期价值'],[['验证语义校准','重点处理来源限定、否定和非提及误判','减少正确候选损失'],['证据质量自适应','按缺失证据类型分配检索与审查预算','提高额外调用收益'],['成本与延迟优化','控制重排规模、上下文长度与模型分工','改善在线服务效率'],['规模化评估','扩充新留出样本并增加中文及领域文档','检验应用泛化能力']],[25,46,29])}
      ${p('综上，观微算法队以真实调试问题为切入点，形成了覆盖算法改造、真实模型验证和工程交付的完整成果。项目在不训练新生成模型的条件下，实现了显著的同题性能提升，为构建证据可追踪的多跳问答系统提供了可运行、可展示、可继续扩展的技术方案。')}
    `,'总结与展望');
    const refs=[
      ['LightRAG: Simple and Fast Retrieval-Augmented Generation','Zirui Guo et al. 2024','https://arxiv.org/abs/2410.05779'],
      ['BAAI bge-reranker-v2-m3','Beijing Academy of Artificial Intelligence. Model card','https://huggingface.co/BAAI/bge-reranker-v2-m3'],
      ['Reciprocal Rank Fusion in QueryFusionRetriever','LlamaIndex. Open-source implementation','https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/retrievers/fusion_retriever.py'],
      ['Corrective Retrieval Augmented Generation','Shi-Qi Yan et al. 2024','https://arxiv.org/abs/2401.15884'],
      ['Chain-of-Verification Reduces Hallucination in Large Language Models','Shehzaad Dhuliawala et al. 2023','https://arxiv.org/abs/2309.11495'],
      ['MultiHop-RAG: Benchmarking Retrieval-Augmented Generation for Multi-Hop Queries','MultiHop-RAG project and dataset','https://github.com/yixuantt/MultiHop-RAG'],
      ['RAGAS Faithfulness Metric','RAGAS. Atomic statement evaluation implementation','https://github.com/vibrantlabsai/ragas/blob/main/src/ragas/metrics/_faithfulness.py'],
      ['LightRAG competition project','zyyyz-a. Source snapshot b9009d2','https://github.com/zyyyz-a/LightRAG']
    ];
    page('references','参考文献',`<h1>参考文献</h1><div class="references">${refs.map(([title,who,url],i)=>`<p><b>[${i+1}] ${esc(title)}.</b><br>${esc(who)}.<br><a href="${url}">${url}</a></p>`).join('')}</div>${h2('开源使用与本项目工作')}${p('我们复用LightRAG的图向量检索、BGE预训练模型与标准RRF融合方法，参考纠错路由、答案独立检查和原子声明核验思路[1–7]。本项目工作集中在父文档证据组织、候选不可见原子核查、显式逻辑计算与有限预算修复的协同实现，并通过本轮真实模型实验完成验证。')}${p('所有性能数据来自本项目保存的原始实验记录；图表依据对应JSONL及汇总文件绘制，流程图描述当前实现结构。参照图像仅用于版式风格，不包含在实验结果中。','small')}`);
    page('appendix','附录 材料索引与评估定义',`<h1>附录　材料索引与评估定义</h1>
      ${h2('A　交付材料索引')}
      ${table(['材料','内容'],[['protocol.json / freeze.json','固定题目索引、参数及源码哈希'],['results/test/records.jsonl','100题×5方案的答案、证据与评分'],['results/validation/records.jsonl','40题×5方案的验证记录'],['results/per_question_scores.csv','700条独立验证及测试成绩简表'],['cache/','真实模型输入及原始响应'],['selected_source.tar.gz','最终算法源码快照'],['algorithm_v2.patch','相对干净b9009d2版本的补丁'],['REPRODUCE_zh.md','服务器问答与结果复核说明']],[46,54])}
      ${h2('B　主要指标定义')}
      ${p('<b>EM</b>：按项目既有规范化规则比较预测答案与标准答案，完全匹配记1，否则记0。<b>F1</b>：对规范化token的重合计算精确率与召回率的调和均值。无答案题的标准答案设为空，格式无效输出记零。')}
      ${p('<b>作答率</b>：输出非空最终答案的题数占比。<b>已作答EM</b>：只在已输出答案的题目上计算EM。<b>可回答题EM</b>：只在非null题上计算EM。三者与全量EM分别报告，避免混淆。')}
      ${h2('C　补充统计与数据规模')}
      ${p('完整流程全量EM的Wilson 95%区间为77.86%–91.47%；相对基础方案的配对bootstrap差值区间为+21至+41个百分点。精确McNemar双侧p约为3.67×10⁻⁸。统计结果对应本次100题抽样。')}
      ${p('实验保留4轮开发共480条记录、独立验证200条记录及测试500条记录，累计复算1,180条EM/F1。新测试题面与旧200题及本轮开发验证题的规范化完全重复数均为0。')}
      ${p('报告版本　V2.0　　实验日期　2026年10月15日<br>署名　河南大学　观微算法队<br>成员　韩昌达　张中瑜　李嘉栋','end-signature')}
    `);
    const css=`
      @page { size:A4; margin:0; }
      *{box-sizing:border-box;letter-spacing:0} html{scroll-behavior:smooth}body{margin:0;background:#e8e8e8;color:#181818;font-family:'SimSun','Times New Roman',serif;font-size:10.6pt;line-height:1.78}
      .page{width:210mm;height:297mm;padding:23mm 22mm 20mm;background:white;position:relative;margin:8mm auto;break-after:page;page-break-after:always}
      .page:last-child{break-after:auto;page-break-after:auto}.body{height:254mm}h1,h2,h3{color:#000;font-family:'Microsoft YaHei','SimHei',sans-serif;font-weight:700}h1{font-size:21pt;line-height:1.35;margin:0 0 5mm}h2{font-size:12pt;line-height:1.5;margin:4mm 0 2.2mm}p{margin:0 0 3.3mm;text-align:justify;overflow-wrap:anywhere}b{font-weight:700}a{color:inherit;text-decoration:none}
      .running{position:absolute;top:10mm;left:22mm;right:22mm;display:flex;justify-content:space-between;font-family:Arial,'Microsoft YaHei',sans-serif;font-size:8pt;color:#666}.footer{position:absolute;bottom:9mm;left:22mm;right:22mm;display:flex;justify-content:space-between;font:8pt Arial,'Microsoft YaHei',sans-serif;color:#666}
      figure{margin:4mm 0 4mm}figure svg{display:block;width:100%;height:auto;max-height:88mm}figure.wide-diagram svg{max-height:91mm}.repair-diagram svg{height:108mm;max-height:108mm}.case-diagram svg{max-height:66mm}figcaption{font-size:9pt;line-height:1.55;text-align:justify;margin:2mm 0 0;color:#3c3c3c}
      table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:9.3pt;line-height:1.5;margin:3mm 0 4mm}th,td{border:0.6pt solid #D9D9D9;padding:2.1mm 2.4mm;vertical-align:middle;text-align:center;overflow-wrap:anywhere}th{background:#eceff1;color:#000;font-family:'Microsoft YaHei',sans-serif;font-size:9pt;font-weight:600}td.left{text-align:left}tbody tr:nth-child(even){background:#f7f8f8}
      .formula{font-family:'Times New Roman','SimSun',serif;text-align:center;padding:2.5mm 0;margin:2.5mm 0;font-size:12pt}.small{font-size:9pt;line-height:1.65;color:#444}.keywords{margin-top:5mm}.abstract-en{margin-top:5mm;font:9.5pt/1.65 'Times New Roman',serif}.abstract-en p{margin-top:2mm}.quote{border-left:1.6pt solid #aebdbf;padding-left:3.5mm;margin:4mm 0;font-size:9pt;line-height:1.6}.quote b{font-family:'Microsoft YaHei',sans-serif;font-size:9pt}.quote p{font-family:'Times New Roman',serif;margin-top:1.5mm}
      .toc{margin-top:5mm}.toc a{display:flex;align-items:baseline;gap:3mm;font-size:11pt;line-height:2.05}.toc i{flex:1;border-bottom:1px dotted #bbb}.toc b{font:10pt Arial}.toc-note{font-size:9pt;color:#555;line-height:1.8;margin-top:8mm}.references p{font-size:9.4pt;line-height:1.55;margin-bottom:4.5mm}.references a{font-size:8.6pt;word-break:break-all}.end-signature{margin-top:6mm;line-height:2}
      .cover{padding:22mm 22mm 17mm}.cover .body{height:258mm}.cover-top{font:11pt 'Microsoft YaHei',sans-serif;margin-bottom:10mm}.cover-type{font:12pt 'Microsoft YaHei',sans-serif;margin-bottom:7mm}.cover-name{font:700 31pt Arial,sans-serif;margin:0 0 5mm;line-height:1.15;color:#000}.cover-title{font:700 21pt/1.55 'Microsoft YaHei',sans-serif;margin:0 0 3mm}.cover-en{font:10pt/1.6 'Times New Roman',serif;color:#555;text-align:left}.cover-visual{margin:10mm -3mm 9mm}.cover-visual svg{width:100%;height:54mm}.cover-metrics{display:flex;justify-content:space-between;margin:0 0 9mm}.cover-metrics strong{display:block;font:700 27pt Arial,sans-serif}.cover-metrics strong span{font-size:13pt;margin-left:2mm}.cover-metrics small{display:block;font:9.5pt 'Microsoft YaHei',sans-serif;margin-top:2mm;color:#444}.cover-meta p{margin:0;font-size:10.5pt;line-height:2.25;text-align:left}.cover-meta b{font-family:'Microsoft YaHei',sans-serif;font-size:10pt}
      @media print{body{background:white}.page{margin:0;box-shadow:none}a{color:inherit}}
    `;
    const html=`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>EvidenceChain RAG 参赛技术报告 观微算法队</title><style>${css}</style></head><body>${pages.map((r,i)=>`<section class="page ${i===0?'cover':''}" id="${r.id}" aria-label="第${i+1}页 ${r.title}">${i?`<header class="running"><span>EvidenceChain RAG</span><span>观微算法队　河南大学</span></header>`:''}<main class="body">${r.body}</main>${i?`<footer class="footer"><span>${r.chapter||'参赛技术报告'}</span><span>${i+1} / ${pages.length}</span></footer>`:''}</section>`).join('')}</body></html>`;
    const htmlPath=path.join(OUT,'EvidenceChain_RAG_参赛技术报告.html');
    fs.writeFileSync(htmlPath,html);
    const report=await browser.newPage({viewport:{width:1000,height:1200},deviceScaleFactor:1});
    await report.goto('file:///'+htmlPath.replaceAll('\\','/'));
    await report.evaluate(()=>document.fonts.ready);
    const layout=await report.evaluate(()=>[...document.querySelectorAll('.page')].map((el,i)=>{
      const b=el.querySelector('.body');const br=b.getBoundingClientRect();
      const children=[...b.children].map(c=>({tag:c.tagName,bottom:c.getBoundingClientRect().bottom-br.top}));
      return {page:i+1,id:el.id,height:b.clientHeight,scrollHeight:b.scrollHeight,lastBottom:Math.max(...children.map(c=>c.bottom)),overflow:b.scrollHeight>b.clientHeight+2};
    }));
    fs.writeFileSync(path.join(QA,'layout.json'),JSON.stringify(layout,null,2));
    if(layout.some(x=>x.overflow)){console.log('LAYOUT_OVERFLOW',JSON.stringify(layout.filter(x=>x.overflow)));throw new Error('Fix page overflow before PDF');}
    const pdfPath=path.join(OUT,'EvidenceChain_RAG_参赛技术报告.pdf');
    await report.pdf({path:pdfPath,format:'A4',printBackground:true,preferCSSPageSize:true,tagged:true,outline:true,margin:{top:0,right:0,bottom:0,left:0}});
    const pdf=await PDFDocument.load(fs.readFileSync(pdfPath));
    if(pdf.getPageCount()!==pages.length)throw new Error('Unexpected PDF pagination: '+pdf.getPageCount());
    pdf.setTitle('EvidenceChain RAG 参赛技术报告');
    pdf.setAuthor('河南大学 观微算法队 韩昌达 张中瑜 李嘉栋');
    pdf.setSubject('面向多跳问答的证据链增强检索与逻辑验证');
    fs.writeFileSync(pdfPath,await pdf.save());
    // Rasterized page previews are QA only; SVG figures remain vector in the PDF.
    const poppler='C:/Users/fanzhen/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe';
    const render=spawnSync(poppler,['-r','110','-png',pdfPath,path.join(QA,'page')],{encoding:'utf8',timeout:120000,windowsHide:true});
    if(render.status!==0)throw new Error('PDF rasterization failed '+render.stderr);
    const pngs=fs.readdirSync(QA).filter(f=>/^page-\d+\.png$/.test(f)).sort();
    for(let first=0;first<pngs.length;first+=4){
      const group=pngs.slice(first,first+4);const thumbs=[];
      for(let i=0;i<group.length;i++)thumbs.push({input:await sharp(path.join(QA,group[i])).resize({width:500}).png().toBuffer(),left:(i%2)*520,top:Math.floor(i/2)*727});
      await sharp({create:{width:1040,height:1454,channels:3,background:'#d9d9d9'}}).composite(thumbs).png().toFile(path.join(QA,`contact-${Math.floor(first/4)+1}.png`));
    }
    const manifest={team:'观微算法队',members:['韩昌达','张中瑜','李嘉栋'],school:'河南大学',pages:pdf.getPageCount(),figures:figures.size,main_test_em:T.v2_full.em,source_audit_sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(INPUT,'results/audit_and_comparison.json'))).digest('hex'),pdf_sha256:crypto.createHash('sha256').update(fs.readFileSync(pdfPath)).digest('hex'),authoring:'Node.js + Graphviz + ECharts + Chromium; no image generation or Python drawing',layout_overflow_pages:[]};
    fs.writeFileSync(path.join(OUT,'report_manifest.json'),JSON.stringify(manifest,null,2));
    for(const [name,source] of figures){
      await sharp(Buffer.from(source)).resize({width:2400}).flatten({background:'#ffffff'}).png().toFile(path.join(FIG,name+'.png'));
    }
    fs.copyFileSync(__filename,path.join(OUT,'build_competition_report.cjs'));
    const zip=new JSZip();
    for(const file of ['EvidenceChain_RAG_参赛技术报告.pdf','EvidenceChain_RAG_参赛技术报告.html','report_manifest.json','case_evidence.json','build_competition_report.cjs'])zip.file(file,fs.readFileSync(path.join(OUT,file)));
    for(const file of fs.readdirSync(FIG))zip.file('figures/'+file,fs.readFileSync(path.join(FIG,file)));
    zip.file('data/audit_and_comparison.json',fs.readFileSync(path.join(INPUT,'results/audit_and_comparison.json')));
    zip.file('data/gpu_test_samples.jsonl',fs.readFileSync(path.join(INPUT,'results/gpu_test_samples.jsonl')));
    zip.file('data/per_question_scores.csv',fs.readFileSync(path.join(INPUT,'results/per_question_scores.csv')));
    const archive=path.join(OUT,'EvidenceChain_RAG_报告与图表源文件.zip');
    fs.writeFileSync(archive,await zip.generateAsync({type:'nodebuffer',compression:'DEFLATE',compressionOptions:{level:6}}));
    console.log('SOURCE_PACKAGE',archive,fs.statSync(archive).size);
    console.log('REPORT_CREATED',JSON.stringify(manifest));
  } finally { await browser.close(); }
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
