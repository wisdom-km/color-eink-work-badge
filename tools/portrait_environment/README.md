# 云端工具链安装与验证（2026-09-30）

本目录记录对已提交的 BADGE-42C H2 基线和本次工具安装的验证。它不是竖版新板的验证报告，也不是生产放行。

## 使用

从仓库根目录执行：

```sh
source tools/portrait_environment/env.sh
kicad-cli version
pio --version
java --version
freerouting -help
freecad-python -c 'import FreeCAD,Part; print(FreeCAD.Version())'
cadquery-python -c 'import cadquery; print(cadquery.__version__)'
```

实际程序安装在 `/workspace/scratch/200245c5fbc3/toolchain`，HOME/XDG/PlatformIO 包与构建缓存也都在该工作区内；不改系统路径、原固件输出或系统安全配置。`env.sh` 绑定当前云端路径，转移到另一台机器须重新安装并调整路径。

## 已验证

| 工具 / 检查 | 版本 / 结果 | 证据 |
|---|---|---|
| KiCad CLI | 官方 Linux Lite AppImage 10.0.6，版本命令 exit 0 | `logs/kicad10-version.log` |
| KiCad pcbnew | 系统 9.0.2，导入成功 | `logs/inventory-initial.log` |
| 原板全量 ERC | 0 violations，exit 0 | `erc-baseline-configured.json` |
| 原板全量 DRC | 0 violations / unconnected / schematic parity，exit 0 | `drc-baseline-configured.json` |
| 网表 vs design.py | 63 nets，exit 0 | `logs/netlist.log` |
| EPD 主机探针 | g++ 14.2.0，20/20 case，exit 0 | `host-probes/epd-probes.json`, `logs/host-probes.log` |
| FreeCAD Part | 1.0.0，立方体有效性、STEP 导出/回读与体积，exit 0 | `logs/freecad-part-smoke.log` |
| CadQuery | 2.7.0，实体体积/有效性，exit 0 | `logs/cadquery-smoke.log` |
| OpenSCAD | 2021.01，STL 导出，exit 0 | `logs/openscad-smoke.log` |
| Java | Temurin JRE 25.0.4.1+1，版本命令 exit 0 | `logs/java25-version.log` |
| Freerouting | 官方 2.4.1，`-help` exit 0 | `logs/freerouting-help.log` |

全量 KiCad 检查包含 warnings、errors、exclusions；DRC 开启 schematic parity。初次未初始化全局 symbol/footprint table 的运行出现配置缺库 warnings，保留在 `*-baseline.json`，**最终结果以 `*-baseline-configured.json` 为准**。全局表已从同一 KiCad 10.0.6 AppImage 自带模板复制到隔离配置目录。

FreeCAD 的 `freecadcmd` 启动在此环境崩溃；已改用官方已安装模块的系统 `/usr/bin/python3` 入口（`freecad-python` 包装器）。CadQuery 使用预装的 Python 3.12；不要与 FreeCAD 的 Python 3.13 混用。

KiCad 使用 Lite 包，不包含官方全套 3D 模型；本次 ERC/DRC 不需要这些模型。机械外观检查必须另外确认所需模型覆盖率，不能以此冒充 3D 全覆盖。

## 固件构建

PlatformIO Core 6.2.0 安装成功；安装日志为 `logs/platformio-install.log`，Python 依赖锁定快照为 `platformio-python-requirements.txt`。工程固定 espressif32@7.1.3。

两次完整编译均通过 exit 0：

1. 当前工作目录构建（包括新 `portrait_frame.cpp` 的当时版本）：`logs/platformio-build.log`
2. 从 HEAD `84f226487c97b10a132f7f11740d5ee0b5bd14c0` 导出的原固件隔离快照：`logs/platformio-baseline-build.log`

两次大小均为 RAM 15320 / 327680 B（4.7%）、Flash 284324 / 1310720 B（21.7%）。未使用的新增代码可被链接器移除，因此大小相同不代表新屏硬件行为已验证。

复现当前固件：`source tools/portrait_environment/env.sh && pio run -d firmware`。原快照使用独立 `PLATFORMIO_BUILD_DIR=$BADGE_TOOLCHAIN_ROOT/platformio-build-baseline`。实际包版本见 `platformio-packages.json`。

首次安装的部分首选包镜像下载校验不匹配，PlatformIO 拒绝后自动改用备用镜像成功；未禁用或跳过完整性校验。完整原始记录保留在构建日志。

`baseline-bin-sha256.txt` 保存原 `firmware/output/badge-42c-v0.1*.bin` 的 SHA256。原 v0.1 应用大小保持 296512 字节；三份文件构建后 SHA256 复核全部 OK，见 `logs/baseline-bin-recheck.log`。

## 来源与完整性

`download-provenance.json` 保存官方来源和哈希。Java 与 Freerouting 下载内容已与官方 API 发布 SHA256 逐字匹配。KiCad 下载自官方页面列出的 CERN 镜像，并记录本地 SHA256；该记录不是独立签名校验。

- KiCad：https://www.kicad.org/download/linux/
- Freerouting：https://github.com/freerouting/freerouting/releases/tag/v2.4.1
- Java：https://adoptium.net/temurin/releases/
- PlatformIO：https://pypi.org/project/platformio/6.2.0/

## 没有做 / 不代表通过

- 未操作实物，未烧录；USB、充电、屏幕 BUSY、NFC、休眠电流仍需真实样机
- 未运行真正 Freerouting 路由任务；后续严格遵守仓库交互 shell、相对路径、日志重定向约定
- 未生成生产 Gerber、生产 ZIP 或下单文件
- 原板 ERC/DRC 通过不意味着竖版新板通过
