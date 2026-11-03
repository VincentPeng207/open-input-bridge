// Exercise the actual embedded browser handlers, without Windows key injection.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "ly03_voice_bridge_ws_v1.py"), "utf8");
const match = source.match(/PAGE = r'''([\s\S]*?)'''/);
assert(match, "Embedded HTML not found");
const javascript = match[1].match(/<script>([\s\S]*?)<\/script>/)[1]
  .replace("__TOKEN_JSON__", JSON.stringify("test-token"))
  .replaceAll("__DOUBLE_MS__", "300")
  .replaceAll("__WHEEL_BURST_MS__", "75");

function harness() {
  let now = 1000, nextId = 0;
  const timers = new Map(), actions = [], handlers = {}, elements = new Map();
  const getElementById = id => {
    if (!elements.has(id)) elements.set(id, {
      textContent:"",className:"",
      addEventListener(event,callback){handlers[id+":"+event]=callback;}
    });
    return elements.get(id);
  };
  const document = {hidden:false,getElementById,
    addEventListener(event,callback){handlers[event]=callback;}};
  class WS {
    static CONNECTING=0;
    static OPEN=1;
    constructor(url){this.url=url;this.readyState=WS.OPEN;}
    send(body){const data=JSON.parse(body);if(data.type==="action")actions.push(data.cmd);}
    close(){this.readyState=3;}
  }
  const context = vm.createContext({
    WebSocket: WS,location:{host:"127.0.0.1:8766"},document,
    window:{addEventListener(event,callback){handlers["window:"+event]=callback;}},
    Date:class extends Date{static now(){return now;}},
    performance:{now:()=>now},
    setTimeout(callback,delay){const id=++nextId;timers.set(id,{callback,at:now+delay});return id;},
    clearTimeout(id){timers.delete(id);},setInterval(){return 0;}
  });
  vm.runInContext(javascript,context);
  const run = code => vm.runInContext(code,context);
  function advance(ms){
    const target=now+ms;
    while(true){
      let selected=null,id=null;
      for(const [tid,task] of timers)
        if(task.at<=target && (!selected||task.at<selected.at)){selected=task;id=tid;}
      if(!selected)break;
      now=selected.at;timers.delete(id);selected.callback();
    }
    now=target;
  }
  return {run,advance,actions,handlers,document};
}
let cases=0;
function scenario(label,fn){fn();cases++;}
scenario("immediate single up",()=>{
  const t=harness();t.run("queueDirection('up','test')");
  assert.deepEqual(t.actions,["up"]);
  t.advance(1000);assert.deepEqual(t.actions,["up"]);
});
scenario("immediate single down",()=>{
  const t=harness();t.run("queueDirection('down','test')");
  assert.deepEqual(t.actions,["down"]);
});
scenario("two rapid ups remain two single actions",()=>{
  const t=harness();t.run("queueDirection('up','test')");
  t.advance(120);t.run("queueDirection('up','test')");
  assert.deepEqual(t.actions,["up","up"]);
});
scenario("two rapid downs remain two single actions",()=>{
  const t=harness();t.run("queueDirection('down','test')");
  t.advance(120);t.run("queueDirection('down','test')");
  assert.deepEqual(t.actions,["down","down"]);
});
scenario("opposite directions immediate",()=>{
  const t=harness();t.run("queueDirection('up','test')");
  t.advance(50);t.run("queueDirection('down','test')");
  assert.deepEqual(t.actions,["up","down"]);
});
scenario("center quick double unchanged",()=>{
  const t=harness();t.run("queueTap('test')");
  t.advance(140);t.run("queueTap('test')");
  assert.deepEqual(t.actions,["double"]);
  t.advance(400);assert.deepEqual(t.actions,["double"]);
});
scenario("center single retains 300ms wait",()=>{
  const t=harness();t.run("queueTap('test')");
  t.advance(299);assert.deepEqual(t.actions,[]);
  t.advance(1);assert.deepEqual(t.actions,["tap"]);
});
scenario("wheel burst suppressed",()=>{
  const t=harness(),e={target:null,deltaY:-50};
  t.handlers.wheel(e);t.advance(15);t.handlers.wheel(e);
  t.advance(15);t.handlers.wheel(e);
  assert.deepEqual(t.actions,["up"]);
});
scenario("long wheel burst suppressed",()=>{
  const t=harness(),e={target:null,deltaY:-50};
  t.handlers.wheel(e);
  for(let i=0;i<6;i++){t.advance(45);t.handlers.wheel(e);}
  assert.deepEqual(t.actions,["up"]);
});
scenario("separate wheel bursts execute immediately",()=>{
  const t=harness(),e={target:null,deltaY:-50};
  t.handlers.wheel(e);t.advance(175);t.handlers.wheel(e);
  assert.deepEqual(t.actions,["up","up"]);
});
scenario("touch upward swipe retains scrolling semantics",()=>{
  const t=harness();t.run("finish(20,80,20,20,120,'touch')");
  assert.deepEqual(t.actions,["down"]);
});
scenario("touch downward swipe retains scrolling semantics",()=>{
  const t=harness();t.run("finish(20,20,20,80,120,'touch')");
  assert.deepEqual(t.actions,["up"]);
});
scenario("keydown ArrowUp immediate",()=>{
  const t=harness(),e={code:"ArrowUp",repeat:false,target:null};
  t.handlers.keydown(e);assert.deepEqual(t.actions,["up"]);
});
scenario("keydown ArrowDown immediate",()=>{
  const t=harness(),e={code:"ArrowDown",repeat:false,target:null};
  t.handlers.keydown(e);assert.deepEqual(t.actions,["down"]);
});
scenario("pause blocks directions",()=>{
  const t=harness();t.handlers["toggle:click"]();
  t.run("queueDirection('up','test')");assert.deepEqual(t.actions,[]);
});
scenario("background blocks directions",()=>{
  const t=harness();t.document.hidden=true;
  t.run("queueDirection('up','test')");assert.deepEqual(t.actions,[]);
});
scenario("background cancels pending center single",()=>{
  const t=harness();t.run("queueTap('test')");
  t.advance(90);t.document.hidden=true;t.handlers.visibilitychange();
  t.advance(400);assert.deepEqual(t.actions,[]);
});
scenario("no directional double controls exposed",()=>{
  const t=harness();
  assert(!t.handlers["manualUpDouble:click"]);
  assert(!t.handlers["manualDownDouble:click"]);
});
console.log(cases+" browser classifier scenarios passed");
