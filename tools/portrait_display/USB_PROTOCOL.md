# P1 USB 完整图片更新

仅用于新 **3.6E 400×600 六色** 独立目标，不适用于旧 H2 4.2 寸板。这里只增加 USB 数据传输，不执行硬件烧录。

## 使用

先生成或从手机页面下载厂商原生色码文件，不要发送语义索引文件：

```sh
python tools/portrait_display/send_frame.py --dry-run tools/portrait_display/output/preview400x600/panel-3in6e-native.bin
# 用户已核对新屏/新板供电并自行烧录匹配固件后，再指定真实串口：
python tools/portrait_display/send_frame.py --port COM5 badge-400x600-native.bin
# Linux 示例：--port /dev/ttyACM0；macOS：实际 /dev/cu.* 设备
```

实际发送依赖 `pyserial==3.5`；`--dry-run` 不依赖串口库，不枚举或打开任何设备。
发送脚本不搜索串口、不烧录固件、不访问网络、不保存密码或凭证。
打开串口可能影响个别开发板的复位接线，需首件确认；程序不主动切换 DTR/RTS。

## 双阶段协议 P36V1

命令是严格 ASCII 行，以 LF 或 CRLF 结束；数据阶段是固定长度的二进制，**没有**行结束符。

1. `RESET` → `RESET`：清理待上传状态；不刷新、不擦屏
2. `HELLO` → `P36V1 EMPTY`，或已有有效 USB 待刷帧时 `P36V1 READY <CRC>`
3. `BEGIN 120000 <8位十六进制CRC>` → `READY 120000`
4. 恰好 120000 字节原生帧 → 长度/色码/CRC 合格才返回 `FRAME <CRC>`
5. 单独发送 `SHOW <相同CRC>` → `DISPLAYING <CRC>`，驱动完成后 `DISPLAY OK <CRC>` 或 `ERR DISPLAY <原因> PANEL_STATE_UNKNOWN`

单独收到完整帧不会启动高压；只有显式 SHOW 才调用显示驱动。重启后状态 EMPTY，默认电源关闭，不自动刷新。
旧单数字纯色串口快捷键已移除，避免随机字符误触发。驱动仍保留 `refresh_solid` 供明确的诊断调用。

### 失败处理

- 错误长度、非法字段、色码、CRC、过长命令：拒绝，要求 RESET
- 接收间隔 3 秒或总时长 30 秒到限：丢弃待上传状态，要求 RESET
- 未结束命令 1 秒到限：拒绝，要求 RESET
- 待刷帧 120 秒过期：释放来源锁，需重新上传
- 分配不到完整 120 KB 连续缓冲：NO_MEMORY，不进入接收或刷新
- SHOW 前再次完整校验，检测接收完成后到刷新前的意外数据变化
- 驱动 BUSY 未应答/超时：硬断电并报告具体阶段；不会自动重刷

串口发送端只在准确收到本帧 FRAME 确认后发送 SHOW；设备拒绝、CRC 不符或超时都不会自动再发 SHOW。
发送 SHOW 后任何响应丢失都按“物理屏面状态未知”处理，不把缺少确认当作刷新成功。

## 单缓冲与手机来源锁

`FrameSession` 是单主循环使用的公用状态机；USB 和本地 HTTP 都使用同一块 **120000 B** 借用缓冲，没有第二帧副本。

- `begin(source,size,crc,now)` 获取 USB 或 Phone 来源锁
- `append(source,offset,data,count,now)` 严格连续偏移，拒绝重复、跳号、超长块；达到完整长度时自动校验
- `finish(source)` 检查是否已完成；`show(source,crc,now)` 才刷新
- 另一个来源的 begin/append/finish/show/reset 返回 Busy，不改原会话；HTTP 应映射为 409
- 超时释放锁；有效帧由原来源持有至 reset 或 120 秒过期
- 实体 UPDATE 键长按 2 秒专用 `prepare_local_frame` 可替换已完成的待刷帧，但不能打断正在接收的帧；它用于把临时配网信息画到屏上，不可暴露成网络 API
- 以上对象不支持并发线程/中断调用；HTTP 必须在同一 Arduino loop 中处理

错误或半帧不会触发新刷新，因此不要求屏幕改变当前画面。**这不是旧帧软件回滚**：新上传会覆盖唯一 RAM 缓冲；没有上一帧可重发副本、Flash 历史、掉电事务或断电恢复保证。刷新一旦开始后失败，屏幕可能停在中间状态。

固件打印启动时的空闲堆和最大 8-bit 连续块，然后检查 `heap_caps_malloc(120000)` 结果。链接器的静态 RAM 数字不含运行期这 120 KB、USB 缓冲及手机 Wi-Fi 开销，不能拿编译成功替代真实最大连续堆测量。

## 验证

```sh
bash tools/portrait_display/run_usb_tests.sh
bash tools/portrait_driver/run_tests.sh
source tools/portrait_environment/env.sh
PLATFORMIO_BUILD_DIR="$BADGE_TOOLCHAIN_ROOT/platformio-build-portrait36-usb" pio run -d firmware/portrait36
```

主机仿真直接编译实际 FrameSession、USB parser、CRC 与屏驱动：

- 469 个不完整接收边界保持不触发新刷新；完整接收单独不刷新
- 错误长度/字段/色码/CRC、越长数据、重复/跳号块、命令超时、时钟回绕、无缓冲、重启、随机串口噪声
- USB/Phone 双向来源互斥，以及实体配网画面接口只在非接收状态接管
- 已生成的真实 120KB 原生文件经串口 parser 进入驱动后，SPI 图像逐字节相同
- 未插屏 BUSY 常高、刷新 BUSY 超时：返回失败并断电；正常重试必须明确 SHOW
- Python 发送端部分写入、拒绝响应、断连、错误应答与安全停止

ASan/UBSan 开启；LeakSanitizer 因执行环境 ptrace 限制未运行。没有真实 USB 设备、无线电、供电电压、实屏或 Flash 掉电测试。
