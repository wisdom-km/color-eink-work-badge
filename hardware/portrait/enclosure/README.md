# C1 一体工牌机械评审候选

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
