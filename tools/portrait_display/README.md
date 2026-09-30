# 当前范围说明（2026-09-30）

手机与USB的单帧固件已在firmware/portrait36实现并通过host测试/真实编译，详见docs/portrait/START_HERE.md。下文是图像工具与双缓冲/提交模型测试的模块说明；其旧“未来/未集成”表述不再描述整个P36项目。模型的旧帧/断电原子性不能用于声称当前固件有Flash持久化或旧RAM回滚。下文保留作算法测试范围记录。

# P1 竖版显示与帧完整性探针

此目录是新增、隔离的显示工具，不改 H2 的 `epd.cpp`、`main.cpp`、引脚或 NFC 协议。
P1 软件基线是 Waveshare **3.6inch e-Paper (E)，400×600 原生竖版、六色、4 bit/pixel**。
屏幕颜色来自厂商色码；PNG 的 RGB 仅用于排版预览，**不是实屏色彩、反射率、刷新速度或可读性测量**。

## 文件与边界

- `firmware/include/portrait_frame.h` / `firmware/src/portrait_frame.cpp`：无 Arduino、无堆分配的借用缓冲区视图；通用 1/2/4/8-bit 像素访问、90°/180°/270° 旋转；3.6E 完整帧合法色码检查和 CRC-32/ISO-HDLC
- `render_preview.py`：占位中文姓名、职位、公司，白底黑字，少量六色强调；按参数生成原始像素 PNG、通用索引帧、旋转帧；仅主规格额外导出官方色码原生帧
- `frame_cli.cpp`：调用实际 C++ 模块做旋转和原生帧校验，供 Python 交叉检查
- `test_frame.cpp`：独立逐位 oracle、逐像素双射和往返证明、缓冲区哨兵、非法尺寸/位深/颜色/坐标/重叠测试
- `test_transaction.cpp`：**主机双缓冲内存模型**，验证完整接收且色码/CRC 正确之前不切换当前帧；不是固件传输栈、Flash 事务、线程原子操作或断电恢复实现

没有实现 NFC 图传、门禁卡模拟、访问凭证、BLE 配对或新屏硬件引脚集成。

## 原生格式

400×600 像素，共 **120,000 字节**。行主序，每个字节高四位在前，两像素一字节，无行填充；主屏原生就是竖版，因此 **不旋转**。

| 颜色 | 原生 nibble |
|---|---:|
| 黑 | 0x0 |
| 白 | 0x1 |
| 黄 | 0x2 |
| 红 | 0x3 |
| 蓝 | 0x5 |
| 绿 | 0x6 |

0x4 及 0x7–0xF 均拒绝。CRC 使用反射多项式 0xEDB88320，初值/终值异或均为 0xFFFFFFFF；标准向量 `123456789` 得 `CBF43926`。CRC 仅检测意外损坏，**不认证发送方**。

Python 排版器内部语义索引是黑/白/红/黄/蓝/绿 = 0/1/2/3/4/5，因此必须经显式映射 **0/1/3/2/5/6** 后才能送屏。`portrait-indexed.bin` 不可直接送屏；400×600 六色输出里的 `panel-3in6e-native.bin` 才使用厂商编码。两种格式刻意使用不同文件名，防止黄红互换和非法色码 4。

官方来源（已检视源文件，固定版本）：

- [Waveshare EPD_3in6e.h](https://github.com/waveshareteam/e-Paper/blob/a794fbc39656b0f93938d1ffb3fdc77eaed9e9fc/E-paper_Separate_Program/3.6inch_e-Paper_E/ESP32/EPD_3in6e.h)
- [Waveshare EPD_3in6e.cpp](https://github.com/waveshareteam/e-Paper/blob/a794fbc39656b0f93938d1ffb3fdc77eaed9e9fc/E-paper_Separate_Program/3.6inch_e-Paper_E/ESP32/EPD_3in6e.cpp)

通用旋转遵循像素中心坐标：顺时针 `(x, y) → (H−1−y, x)`，逆时针 `(x, y) → (y, W−1−x)`，半转 `(x, y) → (W−1−x, H−1−y)`。毫米板框的边界坐标变换不可直接拿来当像素索引。

## 复现

仓库根目录运行，依赖 C++17 g++、Python、Pillow、reportlab、libzbar 和 NotoSansCJK Regular/Bold。字体位置可通过 `--regular-font` / `--bold-font` 指定；manifest 记录实际字体 SHA256。相同参数、字体和依赖生成相同像素与文件哈希，不写入时间戳。

```sh
python tools/portrait_display/run_tests.py --out tools/portrait_display/output/tests
python tools/portrait_display/render_preview.py --out tools/portrait_display/output/preview400x600
# 可选：检查排版尺寸参数，不把它们宣称为已选硬件
python tools/portrait_display/render_preview.py --width 480 --height 720 --out /tmp/portrait480x720
python tools/portrait_display/render_preview.py --width 300 --height 400 --colors 4 --out /tmp/portrait300x400
```

`run_tests.py` 打开 AddressSanitizer 和 UndefinedBehaviorSanitizer，编译警告视为错误。容器 ptrace 下 LeakSanitizer 不可用，所以显式关闭漏检并记录；不能宣称完成了内存泄漏检测。

预览输出：

- `portrait.png`：1:1 原始像素，主规格 400×600
- `portrait-2x.png`：严格最近邻 2× 放大，仅供看排版
- `portrait-indexed.bin` / `landscape-cw90-indexed.bin`：通用语义索引帧
- `panel-3in6e-native.bin`：仅 400×600 六色主规格；120,000 B 厂商原生编码
- `manifest.json`：规格、字体哈希、帧 CRC/SHA256、独立 QR 解码、Python/C++ 逐像素旋转一致性

二维码是固定版本 3、纠错 M、四模块白色留边，整数像素模块。内容为保留的不可解析演示地址 `https://example.invalid/badge-demo`，不是门禁凭证或真实员工链接。libzbar 必须能独立读出原图和旋转图；无法解码时生成命令失败，不静默标通过。

## 稳定性验证能说明什么

- 尺寸/深度有效时，通用读写及旋转不越界；负坐标、短缓冲、非法色值、重叠旋转直接拒绝
- 1–13 像素的每组宽高、每个位深均使每种颜色到达每个位置；300×400×2、400×600×4、480×720×4 对所有颜色和所有像素检查三种旋转及逆变换
- 完整帧检查拒绝错误长度、非法 nibble、CRC 不匹配
- 内存模型覆盖每个 256 字节边界处中断、乱序/重复/过长包、取消、重试和二次提交；最后确认的旧帧在失败前保持不变

仍然**没有**测过真实总线、显示故障回滚、Flash 掉电、长时间运行、天线、供电电流、温度或整机。也没有实现把内存模型部署到设备。

400×600×4 的双帧占 240,000 B；480×720×4 的双帧占 345,600 B。ESP32-C3 的可用堆还要留给系统、协议栈和驱动，主机模型不能直接当作可用固件 RAM 方案。生产实现需依据实际最大空闲块评估暂存到 Flash/外部存储、单帧渲染或分块输出；生产刷新前仍须完整校验，不能收到半帧就刷屏。
