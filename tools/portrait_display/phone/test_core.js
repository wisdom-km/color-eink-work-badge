/* SPDX-License-Identifier: MIT */
"use strict";
const assert = require("assert");
const fs = require("fs");
const core = require("./core.js");
assert.strictEqual(core.crc32(Buffer.from("123456789")), "cbf43926");
assert.strictEqual(core.crc32(new Uint8Array()), "00000000");
const pngHeader = (w, h) => {
  const b = new Uint8Array(24); b.set([137,80,78,71,13,10,26,10]); b.set([73,72,68,82], 12);
  new DataView(b.buffer).setUint32(16, w); new DataView(b.buffer).setUint32(20, h); return b;
};
assert.deepStrictEqual(core.inspectImage(pngHeader(400,600), "image/png"), {width:400,height:600,format:"image/png"});
assert.deepStrictEqual(core.inspectImage(new Uint8Array([255,216,255,192,0,7,8,2,88,1,144])), {width:400,height:600,format:"image/jpeg"});
for (const [bytes, mime] of [[Buffer.from('<svg><image href="https://example.com/x"/></svg>'),"image/svg+xml"],
  [Buffer.from("not an image"),"image/png"], [pngHeader(0,600),"image/png"], [pngHeader(10000,10000),"image/png"],
  [pngHeader(400,600),"text/html"], [new Uint8Array(20*1024*1024+1),"image/png"],
  [new Uint8Array([255,216,255,192,0,0]),"image/jpeg"]]) assert.throws(() => core.inspectImage(bytes,mime));
const pixels = new Uint8ClampedArray(core.palette.flatMap(p => [...p.rgb, 255]));
assert.deepStrictEqual(Array.from(core.quantize(pixels, 6, 1).bytes), [0x01, 0x23, 0x56]);
assert.deepStrictEqual(Array.from(core.quantize(pixels, 6, 1, true).bytes), [0x01, 0x23, 0x56]);
assert.strictEqual(core.quantize(new Uint8ClampedArray([0, 0, 0, 0]), 1, 1).bytes[0], 0x10);
for (const bad of [[new Uint8Array(3), 1, 1], [new Uint8Array(), 0, 0], [new Uint8Array(), 401, 601]])
  assert.throws(() => core.quantize(...bad));
const gradient = new Uint8ClampedArray(400 * 600 * 4);
for (let n = 0; n < 400 * 600; n++) gradient.set([n % 256, (n * 17) % 256, (n * 71) % 256, 255], n * 4);
for (const dither of [false, true]) {
  const a = core.quantize(gradient, 400, 600, dither), b = core.quantize(gradient, 400, 600, dither);
  assert.strictEqual(a.bytes.length, 120000);
  assert.deepStrictEqual(a.bytes, b.bytes);
  const codes = new Set([0, 1, 2, 3, 5, 6]);
  for (const byte of a.bytes) assert(codes.has(byte >>> 4) && codes.has(byte & 15));
}
if (process.argv.length === 4) {
  const rgba = new Uint8ClampedArray(fs.readFileSync(process.argv[2]));
  const native = fs.readFileSync(process.argv[3]);
  const output = core.quantize(rgba);
  assert.deepStrictEqual(Buffer.from(output.bytes), native);
  assert.strictEqual(output.crc, "d16b5951");
}
console.log(JSON.stringify({passed: true, palette_codes: [0,1,2,3,5,6], frame_bytes: 120000,
                           rgba_native_fixture_checked: process.argv.length === 4, hardware_tested: false}));
