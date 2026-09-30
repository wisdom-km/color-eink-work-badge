/* SPDX-License-Identifier: MIT */
// Mocked DOM/application tests, not a browser rendering or image-codec test.
"use strict";
const assert = require("assert"), fs = require("fs"), vm = require("vm");
const core = require("./core.js");
function png(w = 400, h = 600) {
  const bytes = new Uint8Array(24); bytes.set([137,80,78,71,13,10,26,10]); bytes.set([73,72,68,82], 12);
  new DataView(bytes.buffer).setUint32(16, w); new DataView(bytes.buffer).setUint32(20, h); return bytes;
}
function file(options = {}) {
  const bytes = options.bytes || png();
  return Object.assign({name: "fixture.png", type: "image/png", size: bytes.length,
                       arrayBuffer: async () => bytes.buffer, width: 400, height: 600}, options);
}
function environment() {
  const env = {requests: [], decoded: [], urls: new Map(), downloads: [], result: "Ok", driver: "Ok", jobMismatch: false};
  const ids = {}, white = new Uint8ClampedArray(400 * 600 * 4).fill(255);
  let clock = 0, count = 0, job = 0, phase = "idle", received = 0, crc = "00000000";
  const context2d = {fillRect() {}, fillText() {}, drawImage() {}, putImageData() {},
    getImageData() { return {data: white}; }};
  function element(id = "") {
    return {id, value: "", files: [], disabled: false, hidden: false, style: {}, textContent: "", className: "",
      handlers: {}, addEventListener(event, handler) { this.handlers[event] = handler; },
      getContext() { return context2d; }, click() { env.downloads.push(this); }};
  }
  for (const id of ["preview","token","status","send","download","file","fit","mode","connect","cancel","progress","file-info","mock"]) ids[id] = element(id);
  ids.fit.value = "contain"; ids.mode.value = "text";
  ids.send.disabled = ids.download.disabled = true;
  const response = (status, data) => ({ok: status >= 200 && status < 300, status, text: async () => JSON.stringify(data)});
  const snapshot = () => ({state: received === 120000 ? "Ready" : "Empty", owner: "Phone", received, crc,
    result: env.result, driver_result: env.driver, display_status: phase, job: job + (env.jobMismatch && phase === "done" ? 1 : 0), mock: true});
  const globals = {
    document: {getElementById: id => ids[id], createElement: tag => element(tag)},
    location: {hash: "#token=" + "0".repeat(32), pathname: "/", search: ""},
    history: {replaceState() {}}, PhoneCore: core, Uint8Array, Uint8ClampedArray, URLSearchParams, Blob,
    URL: {createObjectURL(blob) { const url = "blob:test-" + ++count; env.urls.set(url, blob); return url; }, revokeObjectURL() {}},
    Image: class {
      set src(url) {
        const selected = env.urls.get(url); env.decoded.push(selected.name);
        this.width = selected.width; this.height = selected.height;
        queueMicrotask(() => selected.decodeFailure ? this.onerror() : this.onload());
      }
    },
    ImageData: class { constructor(data, width, height) { Object.assign(this, {data,width,height}); } },
    AbortController, TypeError,
    Date: {now() { clock += 1000; return clock; }},
    setTimeout(fn, delay) { if (delay < 2000) queueMicrotask(fn); return 1; }, clearTimeout() {},
    async fetch(path, options) {
      env.requests.push({path, options});
      if (env.offline) throw new TypeError("offline");
      if (options.headers["X-P36-Token"] !== "0".repeat(32)) return response(401, {error:"bad token"});
      if (path === "/api/status") return response(200, snapshot());
      if (path === "/api/reset") { received = 0; phase = "idle"; return response(200,snapshot()); }
      if (path === "/api/begin") { const data = JSON.parse(options.body); assert.strictEqual(data.size,120000); crc = data.crc; return response(200,snapshot()); }
      if (path.startsWith("/api/chunk")) {
        assert(options.body instanceof Uint8Array); assert(options.body.length <= 4096);
        assert.strictEqual(Number(path.split("=")[1]),received); received += options.body.length;
        if (env.onChunk) env.onChunk();
        return response(200,snapshot());
      }
      if (path === "/api/show") {
        assert.strictEqual(received,120000); job++; phase = "queued";
        const result = response(202,snapshot());
        phase = env.driver === "Ok" ? "done" : "failed";
        if (env.driver !== "Ok") env.result = "DisplayFailed";
        return result;
      }
      throw new Error("unexpected request " + path);
    }
  };
  vm.runInNewContext(fs.readFileSync(__dirname + "/app.js","utf8"),globals);
  env.ids = ids;
  env.fire = (id,event = "click") => ids[id].handlers[event]();
  env.choose = async selected => { ids.file.files = [selected]; await env.fire("file","change"); };
  env.ready = async () => { await env.choose(file()); await env.fire("connect"); };
  return env;
}
(async () => {
  let tests = 0;
  {
    const e = environment(); await e.ready(); assert(!e.ids.send.disabled);
    const first = e.fire("send"), repeated = e.fire("send"); await Promise.all([first,repeated]);
    assert.strictEqual(e.requests.filter(r=>r.path==="/api/show").length,1);
    assert.strictEqual(e.requests.filter(r=>r.path.startsWith("/api/chunk")).reduce((n,r)=>n+r.options.body.length,0),120000);
    assert(e.ids.status.textContent.includes("模拟器已完成"));
    await e.fire("send"); assert.strictEqual(e.requests.filter(r=>r.path==="/api/show").length,2);
    e.fire("download"); assert.strictEqual(e.downloads.length,1); tests++;
  }
  {
    const e = environment(); await e.ready();
    e.onChunk = () => e.fire("cancel"); await e.fire("send");
    assert(!e.requests.some(r=>r.path==="/api/show")); assert(e.ids.status.textContent.includes("取消"));
    e.onChunk = null; await e.fire("send"); assert(e.ids.status.textContent.includes("模拟器已完成")); tests++;
  }
  {
    const e = environment(); e.ids.token.value = "a".repeat(32); await e.fire("connect");
    assert(e.ids.status.textContent.includes("连接码错误")); assert(e.ids.send.disabled);
    e.ids.token.value = "0".repeat(32); e.offline = true; await e.fire("connect");
    assert(e.ids.status.textContent.includes("无法连接")); e.offline = false; await e.ready();
    assert(!e.ids.send.disabled); tests++;
  }
  {
    const e = environment();
    for (const bad of [file({type:"image/svg+xml"}), file({bytes:Buffer.from("bad")}),
      file({size:20*1024*1024+1}), file({bytes:png(10000,10000)})]) {
      await e.choose(bad); assert(e.ids.send.disabled && e.ids.download.disabled); assert.strictEqual(e.decoded.length,0);
    }
    await e.choose(file({decodeFailure:true})); assert(e.ids.status.textContent.includes("无法读取"));
    await e.ready(); assert(!e.ids.send.disabled); tests++;
  }
  {
    const e = environment(); let release;
    const old = file({name:"old.png",arrayBuffer:()=>new Promise(resolve=>{release=resolve;})});
    e.ids.file.files = [old]; const oldTask = e.fire("file","change");
    await e.choose(file({name:"new.png"})); release(png().buffer); await oldTask;
    assert.deepStrictEqual(e.decoded,["new.png"]); assert(!e.ids.download.disabled); tests++;
  }
  {
    const e = environment(); await e.ready(); e.driver = "PowerUnsafe"; await e.fire("send");
    assert(e.ids.status.textContent.includes("供电不足")); assert(e.ids.status.textContent.includes("未启动刷新"));
    assert(!e.ids.status.textContent.includes("状态未知")); tests++;
  }
  {
    const e = environment(); await e.ready(); e.driver = "RefreshTimeout"; await e.fire("send");
    assert(e.ids.status.textContent.includes("状态未知")); assert.strictEqual(e.requests.filter(r=>r.path==="/api/show").length,1); tests++;
  }
  {
    const e = environment(); await e.ready(); e.jobMismatch = true; await e.fire("send");
    assert(e.ids.status.textContent.includes("任务号")); assert(!e.ids.status.textContent.includes("模拟器已完成")); tests++;
  }
  console.log(JSON.stringify({passed:true,mocked_dom_scenarios:tests,real_browser_rendering_tested:false,
    native_only_transfer_bytes:120000,svg_rejected_before_decode:true,repeated_click_cancel_retry_tested:true}));
})().catch(error=>{ console.error(error); process.exitCode=1; });
