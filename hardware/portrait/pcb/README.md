# P36 当前电气工程

KiCad10.0.6打开badge.kicad_pro。3.6E六色50针参考电路，非H2旧24针屏。原生已布线badge.kicad_pcb是最终铜线权威源；81封装、968线段、115过孔、10区，板58×92.64×0.8mm，元件B面。

最终证据在仓库根verification/visible-final：DRC/未连/原理图parity0，ignored为空；ERC0错误9条逐项审阅single_global_label警告。81元件/259连接pin/28NC对源一致，warning-review.json保留线端点证据。五页为主索引、usb_mcu、power、boost、display。

设计源scripts/design.py、readable_schematic.py与pinned库均可编辑；不要为检查调用generate.py/gen_pcb.py/import_route.py，它们可能清布线。不要用系统pcbnew9保存本10版板。任何新电气/布线修订须新备份及全量ERC/DRC/parity，原证据不能沿用。

屏关电后SPI控制脚停LOW，BUSY无上拉。独立逻辑/boost磁珠，C100在V_B。电池PH pin1GND/pin2VBAT，仍必须量来料；USB HRO额定1A、0.75对0.8板厚实配待测。充电100mA无电芯NTC。完整采购MPN候选见docs/portrait/procurement_candidates.csv；candidate_bom.csv只是五列工程导出。

当前NFC功能未设计/未集成。PH/SW3和FPC/C118–121空间阻断仍需修订或实物几何证明，EDA0不能放行制造。参见docs/portrait/START_HERE.md。
