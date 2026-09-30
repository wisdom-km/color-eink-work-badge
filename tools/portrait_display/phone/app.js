/* SPDX-License-Identifier: MIT */
(function () {
  "use strict";
  const $ = id => document.getElementById(id);
  const canvas = $("preview"), context = canvas.getContext("2d", {willReadFrequently: true});
  let picture = null, frame = null, connected = false, busy = false, cancelled = false, startedDisplay = false;
  let pictureVersion = 0;
  const hash = new URLSearchParams(location.hash.slice(1));
  if (/^[0-9a-f]{32}$/i.test(hash.get("token") || "")) $("token").value = hash.get("token");
  if (location.hash) history.replaceState(null, "", location.pathname + location.search);
  context.fillStyle = "#fff"; context.fillRect(0, 0, 400, 600);
  context.fillStyle = "#536176"; context.font = "20px sans-serif"; context.textAlign = "center";
  context.fillText("图片预览", 200, 290); context.font = "13px sans-serif"; context.fillText("400 × 600", 200, 320);
  function status(message, kind = "") { $("status").textContent = message; $("status").className = "status " + kind; }
  function updateControls() {
    $("send").disabled = busy || !frame || !connected;
    $("download").disabled = busy || !frame;
    for (const id of ["file", "fit", "mode", "connect", "token"]) $(id).disabled = busy;
    $("cancel").hidden = !busy || startedDisplay;
  }
  function token() {
    const value = $("token").value.trim();
    if (!/^[a-f0-9]{32}$/i.test(value)) throw new Error("请输入屏上两行拼接后的32位临时连接码，或使用串口输出的完整链接");
    return value;
  }
  async function request(path, {method = "GET", body, timeout = 6000} = {}) {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), timeout);
    const headers = {"X-P36-Token": token()};
    if (body && !(body instanceof Uint8Array)) { headers["Content-Type"] = "application/json"; body = JSON.stringify(body); }
    else if (body) headers["Content-Type"] = "application/octet-stream";
    try {
      const response = await fetch(path, {method, body, headers, signal: controller.signal, cache: "no-store", credentials: "omit"});
      const text = await response.text();
      let data;
      try { data = JSON.parse(text); } catch (_) { throw new Error("工牌返回了无法识别的响应"); }
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) throw new Error("连接码错误或已过期，请重新配网");
        if (response.status === 409) throw new Error("工牌正被另一个更新会话使用，请等其结束");
        throw new Error(data.error || data.status || "工牌拒绝请求");
      }
      if (data.mock) $("mock").style.display = "block";
      return data;
    } catch (error) {
      if (error.name === "AbortError") throw new Error("工牌响应超时，请确认仍连接工牌热点");
      if (error instanceof TypeError) throw new Error("无法连接工牌，请确认手机连接的是工牌热点");
      throw error;
    } finally { clearTimeout(timer); }
  }
  function render() {
    if (!picture) return;
    frame = null; updateControls();
    const stage = document.createElement("canvas"); stage.width = 400; stage.height = 600;
    const c = stage.getContext("2d", {willReadFrequently: true});
    c.fillStyle = "#fff"; c.fillRect(0, 0, 400, 600);
    const factor = $("fit").value === "cover" ? Math.max(400 / picture.width, 600 / picture.height) : Math.min(400 / picture.width, 600 / picture.height);
    const w = picture.width * factor, h = picture.height * factor;
    c.drawImage(picture, (400 - w) / 2, (600 - h) / 2, w, h);
    frame = PhoneCore.quantize(c.getImageData(0, 0, 400, 600).data, 400, 600, $("mode").value === "photo");
    context.putImageData(new ImageData(frame.preview, 400, 600), 0, 0);
    $("file-info").textContent = `已转换为六色 · 120,000 字节 · CRC ${frame.crc}`;
    status("预览已准备好。确认画面后连接工牌并发送"); updateControls();
  }
  $("file").addEventListener("change", async () => {
    const version = ++pictureVersion, file = $("file").files[0];
    if (!file) return;
    picture = null; frame = null; updateControls();
    if (file.size > 20 * 1024 * 1024) { status("图片超过20 MB，请先缩小再选择", "error"); return; }
    let url = null;
    try {
      status("正在手机浏览器中检查并转换图片…");
      if (file.type && !["image/png", "image/jpeg"].includes(file.type)) throw new Error("仅支持 PNG 或 JPEG，不接受 SVG 或其他文件");
      const raster = new Uint8Array(await file.arrayBuffer());
      PhoneCore.inspectImage(raster, file.type);
      if (version !== pictureVersion) return;
      url = URL.createObjectURL(file);
      const image = new Image();
      await new Promise((resolve, reject) => { image.onload = resolve; image.onerror = () => reject(new Error("无法读取这张图片，请换成 PNG 或 JPEG")); image.src = url; });
      if (version !== pictureVersion) return;
      if (image.width * image.height > 20000000) throw new Error("图片像素过大，请缩小到2000万像素以内");
      picture = image; render();
    } catch (error) { if (version === pictureVersion) { picture = frame = null; status(error.message, "error"); updateControls(); } }
    finally { if (url) URL.revokeObjectURL(url); }
  });
  $("fit").addEventListener("change", render); $("mode").addEventListener("change", render);
  $("token").addEventListener("input", () => { connected = false; updateControls(); });
  $("connect").addEventListener("click", async () => {
    busy = true; startedDisplay = true; updateControls();
    try { await request("/api/status"); connected = true; status("已连接工牌。确认预览后点击发送并刷新", "good"); }
    catch (error) { connected = false; status(error.message, "error"); }
    finally { busy = false; startedDisplay = false; updateControls(); }
  });
  $("download").addEventListener("click", () => {
    if (!frame || busy) return;
    const url = URL.createObjectURL(new Blob([frame.bytes], {type: "application/octet-stream"}));
    const link = document.createElement("a"); link.href = url; link.download = "badge-400x600-native.bin"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    status("已生成 USB 原生帧文件，可用 send_frame.py 发送");
  });
  $("cancel").addEventListener("click", () => { if (!startedDisplay) { cancelled = true; status("正在停止上传；不会发送刷新命令…"); } });
  $("send").addEventListener("click", async () => {
    if (busy || !frame || !connected) return;
    busy = true; cancelled = false; startedDisplay = false; updateControls();
    $("progress").hidden = false; $("progress").value = 0;
    const current = frame;
    let confirmedNotStarted = false;
    try {
      await request("/api/reset", {method: "POST"});
      if (cancelled) throw new Error("上传已取消，未发送刷新命令");
      await request("/api/begin", {method: "POST", body: {size: current.bytes.length, crc: current.crc}});
      for (let offset = 0; offset < current.bytes.length; offset += 4096) {
        if (cancelled) throw new Error("上传已取消，未发送刷新命令");
        const chunk = current.bytes.subarray(offset, Math.min(offset + 4096, current.bytes.length));
        await request(`/api/chunk?offset=${offset}`, {method: "POST", body: chunk});
        $("progress").value = offset + chunk.length;
        status(`正在上传 ${Math.round(100 * (offset + chunk.length) / current.bytes.length)}% · 尚未刷新屏幕`);
      }
      if (cancelled) throw new Error("上传已取消，未发送刷新命令");
      startedDisplay = true; updateControls();
      status("整帧已发送，正在请求刷新。刷新开始后请保持供电，不要重新发送…");
      const accepted = await request("/api/show", {method: "POST", body: {crc: current.crc}});
      const job = accepted.job;
      if (!Number.isInteger(job)) throw new Error("工牌未返回有效刷新任务号");
      const deadline = Date.now() + 90000;
      let lastError = "";
      while (Date.now() < deadline) {
        await new Promise(resolve => setTimeout(resolve, 1800));
        let result;
        try { result = await request("/api/status", {timeout: 3500}); }
        catch (error) { lastError = error.message; status("工牌正在刷新，暂时无法响应。请保持供电并等待…"); continue; }
        const phase = result.display_status || result.display || "";
        if (phase === "done" || phase === "ok" || phase === "Ok") {
          if (result.job !== job || result.result !== "Ok") throw new Error("刷新任务号或完成状态不一致");
          if (result.crc && result.crc.toLowerCase() !== current.crc) throw new Error("工牌报告的帧校验值不一致");
          status(result.mock ? "模拟器已完成完整上传与刷新流程；未连接真实屏幕" : "工牌报告刷新完成。请查看实屏确认画面", "good");
          return;
        }
        if (phase === "failed" || phase === "error") {
          if (result.driver_result === "PowerUnsafe") {
            confirmedNotStarted = true;
            throw new Error("供电不足，请先连接USB供电或充电");
          }
          throw new Error(`工牌刷新失败：${result.driver_result || result.result || result.error || "未知错误"}`);
        }
        status("工牌正在刷新。屏幕闪动属于刷新过程，请保持供电…");
      }
      throw new Error("等待刷新结果超时" + (lastError ? `；${lastError}` : ""));
    } catch (error) {
      if (!startedDisplay || confirmedNotStarted) { try { await request("/api/reset", {method: "POST", timeout: 2000}); } catch (_) {} }
      status(error.message + (confirmedNotStarted ? "。未启动刷新，本次请求没有改变屏幕画面" : startedDisplay ? "。刷新可能已经开始，屏面状态未知；请检查工牌，再查询连接状态" : "。没有请求新刷新"), "error");
    } finally { busy = false; startedDisplay = false; $("progress").hidden = true; updateControls(); }
  });
})();
