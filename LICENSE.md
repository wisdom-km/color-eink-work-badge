# 许可证

日期：2026-09-15。关闭审查项 F20 的许可证债：仓库以前没有 SPDX，接手无法判断能不能改板、能不能商用打样。

本仓库是**分许可**（CERN OSPO 对「硬件一套、软件一套」的常规做法，不是把硬件当成 MIT 源码）。

| 范围 | SPDX | 为什么 |
|---|---|---|
| **硬件设计**：`hardware/`（`design.py`、原理图、PCB、封装、外壳、Gerber/候选导出） | [CERN-OHL-P-2.0](https://opensource.org/license/cern-ohl-p-2-0) | CERN OHL v2 的**宽松**变体，要求保留版权/免责声明，不强制衍生板开源。官方说明：[cern-ohl.web.cern.ch](https://cern-ohl.web.cern.ch/)、[Which CERN OHL](https://michaelweinberg.org/blog/2025/08/08/which-open-hardare-license/) |
| **固件、脚本、文档、审查工具**：`firmware/`、`hardware/pcb/scripts/`、`tools/`、`docs/`（第三方摘录除外） | [MIT](LICENSES/MIT.txt) | 与 Arduino/PlatformIO 应用层常见许可一致 |
| **第三方** | 保持原许可 | 不得改标 |

第三方（不能改许可）：

- 乐鑫 ESP32-C3-MINI-1 符号/封装/STEP：CC-BY-SA 4.0
- HRO TYPE-C-31-M-14 封装：jenschr/USB-C-Connectors，公有领域
- KiCad 官方库符号与封装：各自许可证
- 预编译 `firmware/output/badge-42c-v0.1*.bin`：与当时 MIT 固件源对应；v0.2 请从源码重建

完整 CERN-OHL-P-2.0 正文以 OSI / CERN 官方文本为准，不在本仓库复制一份以免过期。打样、改板、再分发时保留本文件与 `LICENSES/MIT.txt`。

若以后要改成弱互惠（CERN-OHL-W）或强互惠（CERN-OHL-S），必须 Wisdom 书面改本文件；默认保持 P（宽松）。
