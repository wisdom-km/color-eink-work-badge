# 3D 模型路径登记（F16）

本目录含封装引用的源模型。`kicad-cli pcb export step` 返回 0 **不能**单独当成覆盖证明。

## 已登记路径

| 位号 | 封装引用 | 文件 | 说明 |
|---|---|---|---|
| U1 | `${KIPRJMOD}/lib/3d/ESP32-C3-MINI-1.STEP` | 仓库内厂商 STEP | 实模 |
| J3 | `${KIPRJMOD}/lib/3d/TYPE-C-31-M-14.step` | `make_envelope_3d.py` 按座子外形包络生成 | **包络，不是 HRO 官方 CAD**。用于装配占位和缺文件门禁。机械验收仍要实装量测 |
| J2 | `${KIPRJMOD}/lib/3d/JST_SHL_SM02B-SHLS-TF_1x02-1MP_P1.00mm_Horizontal.step` | 同上，SHL 2P 包络 | 官方 9.0.8 无 SHL STEP，禁止用 SH 系列顶替。封装已复制到 `badge.pretty` |

检查：`python scripts/check_3d_models.py`。`--fail-missing` 在包络文件就位后应能过。装配干涉不能只靠这些包络。
