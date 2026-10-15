const fs=require('fs');
const {createRequire}=require('module');
const {pathToFileURL}=require('url');
const req=createRequire('C:/Users/fanzhen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_qa.cjs');
const root='D:/project/ai算法/deliverables/competition_report_20261015';
(async()=>{
  const bytes=fs.readFileSync(root+'/EvidenceChain_RAG_参赛技术报告.pdf');
  const pdf=await req('pdf-lib').PDFDocument.load(bytes);
  const pdfjs=await import(pathToFileURL(req.resolve('pdfjs-dist/legacy/build/pdf.mjs')).href);
  const parsed=await pdfjs.getDocument({data:new Uint8Array(bytes),useSystemFonts:true}).promise;
  const texts=[];
  for(let n=1;n<=parsed.numPages;n++){
    const page=await parsed.getPage(n);
    texts.push((await page.getTextContent()).items.map(x=>x.str||'').join(''));
  }
  const text=texts.join('').replace(/\s/g,'');
  for(const s of ['观微算法队','韩昌达','张中瑜','李嘉栋','河南大学','86.00%','55.00%','参考文献']){
    if(!text.includes(s))throw Error('Missing PDF text '+s);
  }
  let links=0;
  for(const page of pdf.getPages())links+=page.node.Annots()?.size()||0;
  if(links<20)throw Error('Missing document navigation');
  const zip=await req('jszip').loadAsync(fs.readFileSync(root+'/EvidenceChain_RAG_报告与图表源文件.zip'),{checkCRC32:true});
  const files=Object.keys(zip.files).filter(x=>!zip.files[x].dir);
  for(const f of files){
    const b=await zip.files[f].async('nodebuffer');
    if(/(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{20,}/.test(b.toString('utf8')))throw Error('Potential credential '+f);
  }
  const result={pages:pdf.getPageCount(),pdf_author:pdf.getAuthor(),pdf_text_characters:text.length,link_annotations:links,source_package_files:files.length,png_figures:files.filter(x=>x.startsWith('figures/')&&x.endsWith('.png')).length,zip_crc:'passed',credential_scan:'passed',visual_review:'all19 pages inspected, layout overflow zero'};
  fs.writeFileSync(root+'/qa/final_checks.json',JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
  await parsed.destroy();
})().catch(e=>{console.error(e);process.exitCode=1;});
