# 手机浏览器前端

长按新板 UPDATE 键（GPIO1）2 秒进入限时配网；BOOT（GPIO9）只用于维护，不作为更新入口。

无框架、无外部字体/CDN。图片缩放、白底透明合成、六色量化、可选 Floyd–Steinberg 抖色和 CRC 都在手机浏览器里运行。
原生 400×600×4-bit 编码固定为黑0/白1/黄2/红3/蓝5/绿6；可直接下载 120KB bin，交给同一 USB 发送脚本。
RGB 是软件预览近似，不代表实屏色度测量。

接口由隔离目标的 phone 服务实现：

- GET `/api/status`
- POST `/api/reset`，空 body
- POST `/api/begin`，JSON `{size:120000,crc:"8位hex"}`
- POST `/api/chunk?offset=N`，最多4096字节二进制
- POST `/api/show`，JSON `{crc:"8位hex"}`，202返回后查询同一个 job 的真实终态

全部 API 带 `X-P36-Token` 32位临时随机hex；页面从链接片段 `#token=...` 读取后立即清除地址栏片段，只保存在页面内存，不写入localStorage。网页自身可无认证访问。不能将测试模拟器的全零 token 用于固件。

只有同 job 的 `display_status=done` 且 `result=Ok` 才报告设备完成。刷新时服务可能暂时无响应，前端限时重试查询；90秒后提示屏面状态未知，绝不自动重发 SHOW。
上传取消仅在发送 SHOW 前有效；刷新开始后隐藏取消按钮，提示保持供电。

## 生成固件资产

```sh
python tools/portrait_display/build_phone_page.py
node tools/portrait_display/phone/test_core.js
```

生成 `firmware/portrait36/include/phone_page.h`，`epd36::kPhoneIndexHtml` 为 Flash/PROGMEM 内联资源，不需要上传 SPIFFS 文件系统。
修改 HTML/JS 后必须重新生成，不手改生成头文件。

## 验证范围

当前交付不含mock服务器或运行时凭据。test_app.js的8个DOM场景和test_core.js为host模型，真实浏览器访问本地模拟器曾被环境阻止，未绕过。没有Safari/Chrome/真实热点联调通过声明。生产页面没有固定token，手动输入屏上临时连接码。

测试图片可用tools/portrait_display/output/preview400x600/portrait.png。JS对原始RGBA的量化输出已与C++校验的原生bin逐字核对。详细使用步骤见docs/portrait/START_HERE.md。
