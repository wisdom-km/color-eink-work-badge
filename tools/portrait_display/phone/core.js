/* SPDX-License-Identifier: MIT */
(function (root) {
  "use strict";
  const width = 400, height = 600;
  // Preview RGB values are illustrative; native controller nibble codes are exact.
  const palette = [
    {code: 0, rgb: [20, 24, 32]}, {code: 1, rgb: [255, 255, 255]},
    {code: 2, rgb: [244, 201, 38]}, {code: 3, rgb: [198, 35, 45]},
    {code: 5, rgb: [31, 78, 164]}, {code: 6, rgb: [28, 125, 75]}
  ];
  const linear = Array.from({length: 256}, (_, x) => {
    const n = x / 255;
    return n <= 0.04045 ? n / 12.92 : Math.pow((n + 0.055) / 1.055, 2.4);
  });
  const linearPalette = palette.map(p => p.rgb.map(x => linear[x]));
  const clamp = x => Math.max(0, Math.min(255, Math.round(x)));
  function inspectImage(bytes, mime = "") {
    // Reject SVG/HTML and unsupported containers BEFORE creating a blob URL or
    // invoking the browser decoder. Validate declared raster dimensions first.
    if (!bytes || bytes.length > 20 * 1024 * 1024) throw new Error("图片超过20 MB，请先缩小再选择");
    let w = 0, h = 0, format = "";
    if (bytes.length >= 24 && [137,80,78,71,13,10,26,10].every((v, i) => bytes[i] === v) &&
        bytes[12] === 73 && bytes[13] === 72 && bytes[14] === 68 && bytes[15] === 82) {
      const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
      w = view.getUint32(16); h = view.getUint32(20); format = "image/png";
    } else if (bytes.length >= 4 && bytes[0] === 255 && bytes[1] === 216) {
      let p = 2;
      while (p < bytes.length) {
        if (bytes[p++] !== 255) break;
        while (p < bytes.length && bytes[p] === 255) p++;
        if (p >= bytes.length) break;
        const marker = bytes[p++];
        if (marker === 0xd9 || marker === 0xda) break;
        if (marker === 0x01 || marker >= 0xd0 && marker <= 0xd8) continue;
        if (p + 2 > bytes.length) break;
        const size = (bytes[p] << 8) | bytes[p + 1];
        if (size < 2 || p + size > bytes.length) break;
        if ([0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf].includes(marker)) {
          if (size < 7) break;
          h = (bytes[p + 3] << 8) | bytes[p + 4];
          w = (bytes[p + 5] << 8) | bytes[p + 6]; format = "image/jpeg"; break;
        }
        p += size;
      }
    }
    if (!format || mime && mime !== format) throw new Error("仅支持有效 PNG 或 JPEG，不接受 SVG、HTML 或其他文件");
    if (!w || !h || w > 16384 || h > 16384 || w * h > 20000000) throw new Error("图片尺寸过大或无效，请缩小到2000万像素以内");
    return {width: w, height: h, format};
  }
  function crc32(bytes) {
    let crc = 0xffffffff;
    for (const byte of bytes) {
      crc ^= byte;
      for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
    }
    return ((crc ^ 0xffffffff) >>> 0).toString(16).padStart(8, "0");
  }
  function quantize(rgba, w = width, h = height, dither = false) {
    if (!Number.isInteger(w) || !Number.isInteger(h) || w <= 0 || h <= 0 ||
        w * h > 400 * 600 || rgba.length !== w * h * 4) throw new Error("无效图片尺寸");
    const work = new Float32Array(w * h * 3);
    for (let p = 0; p < w * h; p++) {
      const alpha = rgba[p * 4 + 3] / 255;
      for (let c = 0; c < 3; c++) work[p * 3 + c] = rgba[p * 4 + c] * alpha + 255 * (1 - alpha);
    }
    const bytes = new Uint8Array(Math.ceil(w * h / 2));
    const preview = new Uint8ClampedArray(w * h * 4);
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const p = y * w + x;
      const rgb = [clamp(work[p * 3]), clamp(work[p * 3 + 1]), clamp(work[p * 3 + 2])];
      const sample = rgb.map(c => linear[c]);
      let best = 0, distance = Infinity;
      for (let i = 0; i < palette.length; i++) {
        const candidate = linearPalette[i];
        const d = 0.2126 * (sample[0] - candidate[0]) ** 2 +
          0.7152 * (sample[1] - candidate[1]) ** 2 + 0.0722 * (sample[2] - candidate[2]) ** 2;
        if (d < distance) { distance = d; best = i; }
      }
      const color = palette[best];
      bytes[p >>> 1] |= color.code << ((p & 1) ? 0 : 4);
      for (let c = 0; c < 3; c++) preview[p * 4 + c] = color.rgb[c];
      preview[p * 4 + 3] = 255;
      if (dither) {
        for (const [dx, dy, weight] of [[1, 0, 7/16], [-1, 1, 3/16], [0, 1, 5/16], [1, 1, 1/16]]) {
          if (x + dx < 0 || x + dx >= w || y + dy >= h) continue;
          const q = ((y + dy) * w + x + dx) * 3;
          for (let c = 0; c < 3; c++) work[q + c] += (rgb[c] - color.rgb[c]) * weight;
        }
      }
    }
    return {bytes, preview, crc: crc32(bytes)};
  }
  const api = {width, height, palette, crc32, quantize, inspectImage};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.PhoneCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
