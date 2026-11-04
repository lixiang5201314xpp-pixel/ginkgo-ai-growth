/* Isolated rendered-DOM adapter checks. No real browser, network or account state. */
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const ROW='.comment-item,[data-testid="comment-item"]';
const BODY='.comment-content,.comment-text',TIME='.comment-time,time';
const url='https://www.kuaishou.com/short-video/3x7example12';
function node(text='',attrs={}){
 const n={innerText:text,textContent:text,style:{},children:[],attrs,
  getAttribute(k){return this.attrs[k]??null},
  getBoundingClientRect(){return {x:0,y:0,top:10,left:10,right:300,bottom:90,width:290,height:80}},
  querySelectorAll(selector){return this.queries?.[selector]||[]},
  querySelector(selector){return this.querySelectorAll(selector)[0]||null},
  closest(selector){return selector===ROW?this.ownerRow:null},
  contains(value){return this===value||this.children.some(c=>c.contains?.(value))}
 };return n;
}
function comment(value){const row=node(),body=node(value),date=node('今天');body.ownerRow=row;date.ownerRow=row;row.children=[body,date];row.queries={[BODY]:[body],[TIME]:[date]};return row}
function panel(value,links=[url]){const p=node(),row=comment(value);p.children=[row];p.queries={[ROW]:[row],'a[href]':links.map(href=>node('原帖',{href}))};return p}
function fixture(panels=[],options={}){
 const d=node(),win={location:{href:options.url||url},innerHeight:1000,innerWidth:1200,getComputedStyle:n=>({display:'block',visibility:'visible',opacity:'1',...n.style}),getSelection:()=>options.selection||''};
 d.defaultView=win;d.readyState='complete';d.children=panels;
 d.queries={'.video-sidebar-layout':panels,[ROW]:panels.flatMap(p=>p.querySelectorAll(ROW)),
  'a[href]':panels.flatMap(p=>p.querySelectorAll('a[href]')),
  'div.photo-card':options.cards||[]};
 return d;
}
const box={URL,Date,console};vm.createContext(box);vm.runInContext(fs.readFileSync(path.join(__dirname,'browser-helper/capture.js'),'utf8'),box);
const api=box.GinkgoCapture;let tests=0;
function test(name,fn){fn();tests++;console.log('PASS '+name)}
test('multiple visible preloaded panels never mix adjacent work comments',()=>{
 const doc=fixture([panel('成都请问哪里学乒乓球甲'),panel('成都请问哪里学乒乓球乙')]);
 assert.throws(()=>api.collect({document:doc,source_url:url}),/当前作品|相邻|唯一/);
});
test('one pinned public-original panel only reads comments inside that panel',()=>{
 const current=panel('成都请问哪里学乒乓球甲'),other=panel('成都请问哪里学乒乓球乙');const doc=fixture([current]);
 doc.queries[ROW].push(...other.querySelectorAll(ROW));
 const r=api.collect({document:doc,source_url:url});assert.equal(r.items.length,1);assert.match(r.items[0].excerpt,/甲/);
});
test('a playing different original cannot inherit the address-bar source identity',()=>{
 const doc=fixture([panel('成都请问哪里学乒乓球乙',['https://www.kuaishou.com/short-video/another12'])]);
 assert.throws(()=>api.collect({document:doc,source_url:url}),/链接|身份|当前作品/);
});
test('a panel without a verified public-original link is not accepted as evidence',()=>{
 assert.throws(()=>api.collect({document:fixture([panel('成都请问哪里学乒乓球甲',[])]),source_url:url}),/链接|身份|当前作品/);
});
test('several different visible public-original links fail closed',()=>{
 const doc=fixture([panel('成都请问哪里学乒乓球甲',[url,'https://www.kuaishou.com/short-video/another12'])]);
 assert.throws(()=>api.collect({document:doc,source_url:url}),/链接|身份|当前作品/);
});
test('formatting query parameters do not change an otherwise identical original',()=>{
 const doc=fixture([panel('成都请问哪里学乒乓球甲',[url+'?from=public-search'])]);
 assert.equal(api.collect({document:doc,source_url:url}).items.length,1);
});
test('unknown layout cannot fall back to the whole document',()=>{
 const doc=fixture();doc.queries[ROW]=[comment('成都请问哪里学乒乓球甲')];
 assert.throws(()=>api.collect({document:doc,source_url:url}),/当前作品|唯一/);
});
test('opaque visible search cards stop with an explicit source-link reason',()=>{
 const doc=fixture([],{url:'https://www.kuaishou.com/search/成都乒乓球',cards:[node('成都找乒乓球搭子')]});
 const r=api.inspectPublicPage({document:doc});assert.match(r.blocked,/链接/);assert.equal(r.kind,undefined);
});
test('a loading search without visible cards remains a pending search, not a layout failure',()=>{
 const doc=fixture([],{url:'https://www.kuaishou.com/search/成都乒乓球'});doc.readyState='loading';
 const r=api.inspectPublicPage({document:doc});assert.equal(r.kind,'search');assert.equal(r.blocked,undefined);
});
test('selected text outside the pinned panel cannot be attributed to its source',()=>{
 const outside=node('成都请问哪里学乒乓球乙');const doc=fixture([panel('成都请问哪里学乒乓球甲')],{selection:{toString:()=>outside.textContent,anchorNode:outside,focusNode:outside}});
 assert.throws(()=>api.collect({document:doc,source_url:url,mode:'selection'}),/选中|当前作品/);
});
fs.writeFileSync(path.join(__dirname,'kuaishou-scope-verification.json'),JSON.stringify({passed:true,tests,isolated_dom:true,real_browser:false,network_calls:0,customer_messages:0},null,2));
