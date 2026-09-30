# P36 六色竖版工牌：先读这里

2026-09-30。当前交付是可编辑源码评审候选，仍有明确装配阻断，禁止据此下单或强行装配。没有实屏、无线、电池、门禁或实体试装通过的声明。

## 当前设计

用户选定 Waveshare 3.6英寸六色裸屏 SKU32651，竖向400×600，50针FPC。显示为静态工牌用途，厂家预计全刷约15秒。屏外形56×86.6mm；新PCB58×92.64×0.8mm；C1一体烟灰外壳名义66×109×11.1mm，无外部卡套。Adafruit1578保护500mAh电池为原型选型，31×38×5.6mm只是工程预算，非供应商最大值/老化膨胀保证。

NFC/门禁功能尚未设计完成：系统制式、合法发行凭证及安装位置均未知；当前没有NFC电路或内置inlay集成，普通NDEF不等于门禁卡。历史overview图及其生成文案不代表已实现门禁，本次不交付该图。

## 打开文件

- KiCad10.0.6：hardware/portrait/pcb/badge.kicad_pro；主图加四子页，已布线board是铜线权威源
- FreeCAD1.0：hardware/portrait/enclosure/output/portrait_assembly_revisionB.FCStd，已保存颜色/可见性，直接打开；不要选历史A文件
- CAD尺寸源：hardware/portrait/enclosure/c1_config.py、c1_geometry.py、build_enclosure.py
- 固件：firmware/portrait36；手机页面：tools/portrait_display/phone
- 采购：docs/portrait/procurement_candidates.csv、procurement_offboard_candidates.csv、procurement_candidates.md；78个装配位置和3个采购数量0的测试焊盘
- 机械材料与装配门槛：hardware/portrait/enclosure/README.md

## 已实际完成的电脑验证

KiCad板含81封装、968线段、115过孔、10区。全量DRC、未连接、原理图一致性均0，忽略规则为空。ERC为0错误、9条single_global_label警告，均有逐项线端点与网表审阅，不称全量ERC0。网表81元件/259已连接pin/28NC与电气源核对。

软件整套host测试与真实PlatformIO编译通过。驱动387案例及5适配模型；USB469短包边界、100000字节畸形输入与11发送器测试；图像48611672像素核对、141060旋转、470中断模型、256调色板和56位损坏测试；手机协议43、服务/电源模型23、DOM8模拟场景。ASan/UBSan启用，LSan因环境ptrace限制关闭。DOM模拟不是真实浏览器或手机WiFi联调。最近编译RAM45932B、Flash784080B，最终以随包pio.log为准。

CAD116对象保存并重开验证，STEP/STL拓扑通过；116=36机械/材料/审计/预留对象+80器件高度代理，81位号中的J3是有来源USB盒。并非116个采购件或81个厂家精细模型；未包含真实FPC、导线、门禁凭证和螺钉实体。保留25层软材料与真实板core、名义铜/阻焊堆叠。

证据路径从仓库根算：电气 verification/visible-final；软件 hardware/portrait/verification/visible-final；机械 hardware/portrait/enclosure/validation。SHA绑定具体源文件，旧中间报告不替代最终报告。

## 手机更新

首次需给新板烧录此目标并完成电源/屏台架验收；本包不含可直接烧录镜像。长按UPDATE约2秒进入最长10分钟本地热点，屏显示临时SSID、密码和连接码。手机连接此热点，按屏上地址打开本地页面，手动输入临时连接码，选择图片、检查六色预览、上传并等待同一任务完成。没有配对二维码；不收集既有家庭/公司WiFi密码；页面无远端字体/CDN。接收有效帧后才单独SHOW，刷新中保持供电；90秒超时表示屏状态未知，不自动再刷。页面生成的RGB预览不是实屏色度测量。

仅支持一名热点客户端。上传前可取消，SHOW后不能保证取消；USB与手机共享单120000B缓冲和来源锁，禁止并发覆盖。成功后保留30秒状态窗口再关热点。短按UPDATE用于从深睡唤醒USB；插USB本身不保证唤醒。

## USB更新

先用手机页面下载原生120000B帧，或用附带样帧。不是portrait-indexed.bin，也不是固件镜像。仓库根执行：

    python3 tools/portrait_display/send_frame.py tools/portrait_display/output/preview400x600/panel-3in6e-native.bin --dry-run
    python3 tools/portrait_display/send_frame.py tools/portrait_display/output/preview400x600/panel-3in6e-native.bin --port /dev/ttyACM0

真实端口须用户/操作员确认，Windows可用实际COM号；需要pyserial3.5。脚本先RESET/HELLO再BEGIN、完整长度/颜色/CRC校验，收到FRAME后才SHOW。它不扫描端口、不烧录。DISPLAY OK仅为设备驱动报告，仍需观察实体屏。

## 必须保留的局限

单帧RAM没有旧帧回滚，也没有Flash/NVS图像持久化；重启状态EMPTY。坏包不会触发屏刷新，但旧RAM可被覆盖。进入热点配对页也会覆盖先前工牌画面。不能把host双缓冲模型测试写成固件掉电原子提交。

assembly_review_gates.json保留PH插头预留与SW3，以及FPC整块预留与C118–C121冲突。必须取得实际配对/折返几何证明或开新设计修订解决，不能缩盒凑PASS。TP2/TP3庭院笔宽代理微交叠另有真实铜pad包围盒0交叠证据，原代理保留。全1.2mm屏厚保守审计也保留，不能用局部0.85/1.2模型声称厂商批准压持。

电池无NTC，MCP73831仅芯片温控；原型受控室温监督充电，需验证密闭温升。还须测高压轨/有效电容/峰值电流、低电及USB切换、ADC阈值、BUSY时序、颜色/二维码、FPC/线束、玻璃夹持/公差、按键寿命、人体RF、ESD和跌落。未做这些实体测试，不承诺续航、门禁或量产安全。

## 复现及许可

已安装KiCad10.0.6、FreeCAD1.0、CadQuery2.7、PlatformIO6.2等，版本和来源见tools/portrait_environment。其他电脑先调整env.sh和visible_final_checks.sh工作区绝对路径。

    source tools/portrait_environment/env.sh
    bash tools/portrait_driver/visible_final_checks.sh
    pio run -d firmware/portrait36

包内vendor oracle可用：bash tools/portrait_driver/run_tests.sh third_party/waveshare-3in6e-ESP32/EPD_3in6e.cpp。

严禁为检查而运行gen_pcb.py、generate.py、旧import_route.py重建最终铜线。系统pcbnew9不可保存最终KiCad10板。固件与旧H2的24针屏不兼容。首次烧录需按实际分区/bootloader配置完整烧录，不能把样帧.bin当固件或盲目写0地址。

硬件CERN-OHL-P-2.0、项目固件/脚本MIT，第三方保持原许可，见LICENSE.md与THIRD_PARTY_NOTICES.md。没有购买、下单、生产Gerber放行、固件烧录或Git远端提交。
