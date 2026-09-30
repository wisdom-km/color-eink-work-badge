from pathlib import Path
import json,hashlib,shutil,datetime
R=Path('/workspace/scratch/200245c5fbc3/chroma-badge');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protected=json.loads((R/'verification/visible-final/source-after.json').read_text())
protected.update(json.loads((R/'hardware/portrait/enclosure/validation/execution-provenance.json').read_text())['input_after'])
assert all(sha(R/n)==h for n,h in protected.items())
files={}
start='''# P36 六色竖版工牌：先读这里

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
'''
files['docs/portrait/START_HERE.md']=start
files['docs/portrait/README.md']='# P36 当前工程入口\n\n请先读 [中文开始说明](START_HERE.md)。当前为3.6寸六色400×600、66×109×11.1mm一体工牌源码评审候选；手机和USB功能源码已实现并通过host测试/真实编译。装配阻断和实体测试仍未闭合。\n\n采购候选见 [完整MPN清单](procurement_candidates.csv) 与 [采购说明](procurement_candidates.md)。电气、软件、CAD证据路径及使用方法均在开始说明中。H2旧文件仅为历史，不代表P36功能或尺寸。\n'
files['docs/portrait/00-requirements.md']='''# P36 已确认需求与决策

2026-09-30；原仓库基线84f2264。用户明确旧显示/尺寸/稳定性不满意，重新选型；选定3.6英寸六色竖向400×600；中等科技公司工牌尺寸；参考一体透明结构，无外卡套；手机与USB均可更新；所有建模、PCB和测试在云电脑可见操作。希望合法门禁但不知道系统。

工程方案为Waveshare32651裸屏、50P0.5FPC、ESP32-C3-MINI-1-N4X、保护500mAh原型电池；板58×92.64×0.8，C1外壳66×109×11.1。厚度从历史8.1增加以容纳有来源保护电池和空间预算；不照抄参考TFT/麦克风/扬声器/50g指标。

放弃旋转旧4.2屏、规格矛盾的GDEH037E01以及外卡套方案。当前NFC功能尚未设计完成，无电路或inlay集成；待确定系统和合法发行方式，不能承诺通用门禁。完整现状和制造阻断见START_HERE.md。
'''
files['docs/portrait/03-stability-test-plan.md']='''# 首件稳定性验收计划（尚未实测）

当前电脑测试结果见START_HERE.md，以下是将来实物验收要求，不是已通过记录。

1. 先解决assembly_review_gates.json的PH/SW3和FPC/C118–121空间阻断；来料核电池、PH极性、USB厚度、FPC pin1和锁扣，再制作试装量规。
2. 无屏限流上电，核短路、USB识别、3V3、100mA充电和load-share；测电池与密闭壳温升。两线无NTC，禁止把芯片温控当电芯温控。
3. 断电插屏，核官方波形、BUSY低忙/高就绪、双10uH boost轨峰值/纹波/有效电容、MOS/二极管/采样电阻和电感热应力。
4. 测六色、方向、四角、细字、二维码quiet zone、温区刷新时长；SPI只写没有物理ACK，驱动返回不是画面验收。
5. 满电/低电/USB切换/WiFi与刷新峰值测VBAT和3V3，校准电池3.6V与VBUS ADC阈值及睡眠电流，不凭编译RAM估运行堆余量。
6. 手机iOS/Android实际浏览器和USB实测短包、超长、CRC/色码错、并发、取消、超时、重试、热点过期和设备重启。断电后EMPTY且可重新上传；当前没有Flash图像持久化/旧RAM回滚承诺。
7. 记录真实一次刷新能量和待机电流，注明板号、批次、温度、仪器、采样；无数据不写续航天数。
8. 测玻璃夹持区/胶相容、实际前间隙0.10–0.25、后泡棉压缩20–30%、侧游隙含偏转、回流平整度、按键间隙0.10–0.20及力/行程/寿命、挂绳拉力、螺钉扭矩和跌落；不靠螺钉强压玻璃。
9. NFC需先确定公司系统、取得合法发行凭证，再设计内部安装与天线隔离，并比较裸凭证/整机、满电/更新/低电、距离/偏角重复读卡。现阶段没有NFC功能测试通过。

放行必须同时满足采购规格/追溯、全量EDA审阅、软件编译与故障注入、空间冲突闭合、首件尺寸/电源/显示/热/RF/ESD/机械记录。禁止把源码评审包当生产包，不做破坏性电池试验。
'''
files['hardware/portrait/pcb/README.md']='''# P36 当前电气工程

KiCad10.0.6打开badge.kicad_pro。3.6E六色50针参考电路，非H2旧24针屏。原生已布线badge.kicad_pcb是最终铜线权威源；81封装、968线段、115过孔、10区，板58×92.64×0.8mm，元件B面。

最终证据在仓库根verification/visible-final：DRC/未连/原理图parity0，ignored为空；ERC0错误9条逐项审阅single_global_label警告。81元件/259连接pin/28NC对源一致，warning-review.json保留线端点证据。五页为主索引、usb_mcu、power、boost、display。

设计源scripts/design.py、readable_schematic.py与pinned库均可编辑；不要为检查调用generate.py/gen_pcb.py/import_route.py，它们可能清布线。不要用系统pcbnew9保存本10版板。任何新电气/布线修订须新备份及全量ERC/DRC/parity，原证据不能沿用。

屏关电后SPI控制脚停LOW，BUSY无上拉。独立逻辑/boost磁珠，C100在V_B。电池PH pin1GND/pin2VBAT，仍必须量来料；USB HRO额定1A、0.75对0.8板厚实配待测。充电100mA无电芯NTC。完整采购MPN候选见docs/portrait/procurement_candidates.csv；candidate_bom.csv只是五列工程导出。

当前NFC功能未设计/未集成。PH/SW3和FPC/C118–121空间阻断仍需修订或实物几何证明，EDA0不能放行制造。参见docs/portrait/START_HERE.md。
'''
files['firmware/portrait36/README.md']='''# P36 手机与USB六色更新固件

400×600、每像素4bit，单缓冲120000B，颜色黑0白1黄2红3蓝5绿6；不兼容H2屏。完整用户流程见docs/portrait/START_HERE.md。

长按UPDATE(GPIO1)约2秒启动限时本地SoftAP；屏上给临时SSID/密码/32hex连接码，手动输入，没有配对QR。页面处理图片、六色量化、CRC和≤4096B分块；全部API临时token校验，最多1客户端10分钟，不使用用户既有WiFi凭据。上传合法完整后独立SHOW，成功后30秒状态窗口再关AP。USB同一会话锁，send_frame.py先校验再SHOW。

单缓冲无旧RAM回滚、无Flash/NVS图片持久化，重启EMPTY；无效包不刷新屏但可覆盖RAM。配对页会覆盖先前画面。手机真实浏览器/WiFi/堆峰值未实测；DOM8场景是模拟。

GPIO：电源2 LOW开；SCK6、MOSI7、CS10、DC20、RST21、BUSY3 LOW忙；UPDATE1 RTC唤醒；VBUS ADC4；电池ADC0；BOOT9仅维护。SPI mode0 MSB-first1MHz。所有返回硬断屏电源，控制线LOW，BUSY INPUT无上拉；04/12/02操作要求有界LOW→HIGH。无SPI物理ACK，超时边界待实屏温区验证。

60秒无USB/AP/上传且UPDATE释放后深睡；短按UPDATE唤醒USB，插USB本身不保证唤醒。电源阈值电池估算≥3.6V或VBUS ADC≥1000mV，真实ADC/峰值需校准。初次仅受控台架测试。

仓库根source tools/portrait_environment/env.sh，然后pio run -d firmware/portrait36。完整host套件bash tools/portrait_driver/visible_final_checks.sh。最新编译RAM45932B、Flash784080B；最终以pio.log为准。测试为host/adapter模型、真实编译，不代表硬件成功。本源码包不附固件镜像；样帧.bin绝不是烧录文件。厂商序列与许可见THIRD_PARTY_NOTICES.md。
'''
files['hardware/portrait/enclosure/README.md']='''# C1 一体工牌机械评审候选

当前66×109×11.1mm，FreeCAD直接打开output/portrait_assembly_revisionB.FCStd。已保存颜色并关闭/重开验证，116对象，111显示/5审计预留隐藏。历史8.1mm A文件不是当前交付。不要再次保存已冻结native仅为截图，避免SHA链失效。

## 验证及实际范围

七个真实stage完成，execution-provenance.json状态EXECUTED_REVIEW_REQUIRED_C1_PIPELINE；STEP/STL拓扑和原生BREP有效。116对象=36机械/材料/审计/预留+80器件高度代理，81位号中J3为有来源USB盒；不是全厂家装配，不含真实FPC/电池导线/门禁凭证/螺钉实体。PCB core来自最终已布线KiCad板，名义完整0.8审计体预算铜/阻焊；不能假定每个蚀刻边缘承压高度一致。

assembly_review_gates.json保留PH插头预留与SW3、全块FPC预留与C118–C121的5条装配阻断。TP2/TP3庭院笔宽微交叠原样保留，真实铜pad bbox为0交叠。不能缩预留盒掩盖冲突。全1.2mm屏审计与前垫保守交叠仍保留；局部上部0.85/底9mm1.2模型不代表厂家批准压持。制造放行始终blocked。

实际图：portrait_native_C1_iso/front/internal.png、portrait_actual_section.png（厚度显示5倍）、portrait_layer_stack.png。旧portrait_review_overview.png文案可能误读门禁已集成，因此不交付；NFC电路/inlay当前未集成，制式和位置待设计。

## 材料候选与采购数量

- 前框1、齐平后盖1：烟灰半透PETG或经过验证的韧性聚合物，打印方向/收缩/疲劳未合格
- M2×10螺钉4枚，M2六角螺母4枚：名义对边4.0/厚1.6，槽宽4.2/高1.8；实际头部、盲孔和公差需实配，拆卸防散落
- 屏PSA：3M468MP标称0.13mm，3条；左右各0.9×70mm，上50×0.9mm，仅非AA边缘，屏厂胶相容与夹持许可未取得
- 前垫：PORON4790-92PL-09020标称0.50±0.10mm，3条；另3条0.06mm PSA为厚度预算，未锁定可买胶料MPN
- 后垫4处：各0.05mm post PSA +0.15mm PET +0.05mm foam PSA +PORON4701-30密度400、自由0.79±15%压至0.60mm（名义24.05%）。两个0.05胶层为受控预算，不能假称已锁采购MPN

25层名称/坐标在c1_config.OBJECTS和mechanical_expectation.json。后垫均2×2mm，PCB坐标[1,1,3,3]、[55,18,57,20]、[1,89.64,3,91.64]、[41.6,90.14,43.6,92.14]。原厂材料来源链接见c1_config.SOURCES；JST原图sources/JST-PH-official.pdf。

## 首件测量，不可强装

回流后先测PCB平整度、每点承压完成厚度；不要靠螺钉把翘板或玻璃压平。前垫实际间隙目标0.10–0.25mm；名义0.18/最大局部屏厚0.11，示例公差会降到−0.04，未测不可放行。座Z候选2.30..2.60且剩壁≥0.90；超范围重做。

后选PET：实测肩台到支柱H、当地板厚T、两胶a1/a2、自由泡棉f，PET=H−T−a1−a2−0.75f。名义H1.65/T0.8/a总0.10/f0.79得0.1575mm。选垫0..0.40、增量0.025/0.05候选，目标压缩20–30%；达不到则返工支柱/换受控料，不加螺钉力压板。

在全部肩台/玻璃角测含偏转侧游隙，不只中心平移。UPDATE梁0.65厚×13长×4宽、槽0.45；实际静态间隙0.10–0.20，验证行程/止挡/释放/疲劳。0.6名义止挡不证明安全过行程。原配100–102mm电池线和PH配对、FPC弯折/锁扣、USB实物均须试装。RF、温升、跌落、挂绳和磨损仍未测。

## 复现

有效配置为c1_config.configure(只读H2 PORTRAIT)。本次迁移--setup已执行。常规重新生成先c1_pipeline.py --run，再在真实FreeCAD中运行OpenC1RevisionB.FCMacro，最后--finalize。宏只用于该次headless输出，不可对已样式化文件反复执行。任何源修改都要重新验证全链；不得改冻结电气板后沿用旧报告。日常查看直接打开当前FCStd，无需宏。
'''
files['tools/portrait_driver/README.md']='''# P36 驱动及完整软件验证

真实最终证据：hardware/portrait/verification/visible-final。可见运行visible_final_checks.sh：驱动387例（日志386是中间轮，不能相加）+5GPIO/SPI模型；USB469接收边界/100000畸形字节/11sender例；手机协议43、服务电源模型23、DOM8；完整图像测试及PIO编译。最新RAM45932、Flash784080，最终看pio.log。ASan/UBSan启用，LSan受ptrace限制。

驱动逐字对照固定Waveshare源120061SPI字节；适配模型与故障注入不代表实体SPI/屏BUSY/RF。完整固件使用单120000B缓冲，已实现手机和USB传输；未实机。工具链来源见tools/portrait_environment。包内oracle命令：bash tools/portrait_driver/run_tests.sh third_party/waveshare-3in6e-ESP32/EPD_3in6e.cpp。
'''
phone=R/'tools/portrait_display/phone/README.md';s=phone.read_text();pos=s.index('## 浏览器演练');s=s[:pos]+'''## 验证范围

当前交付不含mock服务器或运行时凭据。test_app.js的8个DOM场景和test_core.js为host模型，真实浏览器访问本地模拟器曾被环境阻止，未绕过。没有Safari/Chrome/真实热点联调通过声明。生产页面没有固定token，手动输入屏上临时连接码。

测试图片可用tools/portrait_display/output/preview400x600/portrait.png。JS对原始RGBA的量化输出已与C++校验的原生bin逐字核对。详细使用步骤见docs/portrait/START_HERE.md。
''';files[str(phone.relative_to(R))]=s
frame=R/'tools/portrait_display/README.md';old=frame.read_text();files[str(frame.relative_to(R))]='''# 当前范围说明（2026-09-30）

手机与USB的单帧固件已在firmware/portrait36实现并通过host测试/真实编译，详见docs/portrait/START_HERE.md。下文是图像工具与双缓冲/提交模型测试的模块说明；其旧“未来/未集成”表述不再描述整个P36项目。模型的旧帧/断电原子性不能用于声称当前固件有Flash持久化或旧RAM回滚。下文保留作算法测试范围记录。

'''+old
for name in ['README.md','AGENTS.md']:
 old=(R/name).read_text()
 if name=='README.md' and old.startswith('> **2026-09-30'):old=old[old.index('# chroma-badge'):]
 banner='''# P36 当前入口（2026-09-30）

当前新设计为3.6寸六色400×600、手机+USB更新、一体66×109×11.1mm工牌。先读[中文开始说明](docs/portrait/START_HERE.md)。源码评审候选仍有PH/SW3、FPC/C118–C121装配阻断，NFC功能尚未设计完成，未做实体测试，不可制造放行。

P36路径：hardware/portrait/、firmware/portrait36/、docs/portrait/。最终已布线KiCad10原生PCB是铜线权威源；不得运行generate.py/gen_pcb.py/旧import_route.py覆盖铜线，不用pcbnew9保存。新电气修订必须备份并重新完整验证；当前报告仅绑定当前SHA。用户已授权此次重新选型、设计和当前文档同步。

## 以下为H2历史基线范围

以下旧4.2寸/ST25/6.3mm/F2未实现及旧流程仅适用历史H2，不覆盖P36新需求/入口/证据。保留原文供追溯；不要按旧生成命令操作P36。通用中文回复、禁止未经要求PR及许可证要求仍有效。

'''
 files[name]=banner+old
files['THIRD_PARTY_NOTICES.md']='''# 第三方归属与修改

补充根LICENSE.md，项目硬件CERN-OHL-P-2.0，项目固件/脚本MIT，第三方保持原许可。

KiCad Community符号/封装来自本机官方库快照，安装资料登记Copyright2025，CC-BY-SA4.0附KiCad Libraries Exception。设计例外不把再分发库集合改成MIT；保留LICENSES的原版权许可。P36修改了Connector过滤器等，不能称未修改官方库。https://www.kicad.org/libraries/license/

Espressif符号/ESP32-C3封装和STEP继承自项目快照，CC-BY-SA4.0及上游KiCad例外，含工程net-tie/路径适配；原获取commit未知，只记录实际文件SHA。https://github.com/espressif/kicad-libraries 。当前官方许可另附，不捏造原下载版本。

HRO TYPE-C-31-M-14封装源jenschr/USB-C-Connectors为Unlicense，现有courtyard/属性/工程路径修改；USB/JST简化STEP为尺寸工程包络，不是厂商精细CAD或实配证据。https://github.com/jenschr/USB-C-Connectors

Waveshare3.6E序列按其MIT许可适配，原版权和固定SHA见firmware/portrait36/THIRD_PARTY_NOTICES.md及随包vendor源。Freerouting补丁保持GPL3，全文/commit/重建见tools/portrait_environment/freerouting-offline；不附router JAR。厂家规格书/商标归原权利人，不构成背书或制造认证。
'''
backup=R/'docs/portrait/document_backups'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ');backup.mkdir(parents=True)
for n,t in files.items():
 assert n not in protected,n
 p=R/n
 if p.exists():q=backup/n;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t,encoding='utf-8');assert p.read_text()==t
for name in ['footprints','symbols']:
 src=Path('/usr/share/doc/kicad-'+name+'/copyright');assert src.is_file();shutil.copy2(src,R/'LICENSES'/('KiCad-'+name+'-COPYRIGHT.txt'))
assert all(sha(R/n)==h for n,h in protected.items())
print('DOCUMENTS UPDATED',len(files),'EDA/CAD INPUT HASHES UNCHANGED; BACKUP',backup)
