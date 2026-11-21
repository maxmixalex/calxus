# Calxus 制造文件与装配范围

本目录保存实际原生 Gerber、BOM/CPL 来源与生成的 87 件 SMT 文件。**CAM 文件检查已通过，制造放行仍为 `false`**：原生 PCB DRC 的 3 项总线段长度统计例外已逐项审查，另有 1 项全局 `Netlist Error` 尚未解释。当前原生飞线、连接、净距和物理错误均为 0；这些结果不能合并表述成“DRC 全绿”。见[发布验收汇总](../../validation/release-summary.json)。

| 文件 | 内容与来源 |
|---|---|
| [Calxus_RevA_Gerber.zip](Calxus_RevA_Gerber.zip) | 实际最终原生导出，212148 字节；原始 ZIP 字节未改 |
| [Calxus_RevA_SMT_BOM.csv](Calxus_RevA_SMT_BOM.csv) | 87 件器件、34 行采购分组 |
| [Calxus_RevA_SMT_CPL.csv](Calxus_RevA_SMT_CPL.csv) | 87 行，mm，Top 面，保留原生 Mid X/Y 和角度 |
| [完整原生工程](../native/Calxus_RevA.epro2) | 本次实际保存与导出的源，SHA-256 `40d27f61240cb3974f0bd0ecc4c996582f56a4a142598cf3a2e6bce84b4ce4ac` |
| [三页原生原理图](../schematic/Calxus_RevA_schematic.pdf) | 当前 J2、A2 图框，已实际渲染与目视复核 |
| [实际 CAM 报告](../../validation/native-final-gerber/gerber-validation.json) | 全孔、层、轮廓、阻焊和钢网检查 |
| [实际 SMT 报告](smt-native-export-validation.json) | 本次原生 TSV 筛选与 87 个位号身份/位置/面/角度核对 |

`source/Calxus_RevA_BOM_native.tsv` 与 `source/Calxus_RevA_CPL_native.tsv` 是本次最终原生导出的原始字节，包含当前 J2；其真实文件名、Windows 导出路径及哈希在相邻的 `*-export-report.json` 中。`prepare_smt_files.py` 从这些文件筛选 87 个 SMT 位号，`export_smt_csv.mjs` 使用 artifact-tool 实际生成两份 CSV。最终 CSV 与此前已核对的 SMT 子集逐字节相同。J1 虽有通孔固定脚仍属于 SMT 贴装件；不将器件锚点 Ref X/Y 代替原生 Mid X/Y。

87 件 SMT 中有 52 件基础库、35 件扩展库。J2、J6、J7、J9、J10、SW1 为 6 件手焊通孔器件，板上合计实装 93 件。J3/J4/J5/J8 四组接口 DNP，只作焊线或服务焊盘；另有 23 个 TP。线束和跳帽不进入 SMT CPL，见[手工装配采购表](../electrical/manual_assembly_reference.csv)与[尾线采购说明](../electrical/harness-procurement.zh-CN.md)。两只 2.5 mm TRS 公头仍有采购缺口。

## 本次实际制造几何验收

实际 ZIP 包含四铜层及完整外形、阻焊、丝印、钢网和钻孔文件。板框中心线闭合为 80×42 mm，四角各 R1 mm 圆弧。原始 GKO 命令逐段核验；Gerbonara 1.6.3 预览曾重复最后闭合弧形成显示弦线，仅修正派生 SVG 的重复闭合段，原始 SVG 和前后哈希保留在[板框证据](../../validation/native-final-gerber/outline-corners.json)，原始 Gerber 未改。

全部 247 个唯一加工孔/槽逐一按保存源的位置、圆径、槽长、方向与类别核对，均通过，未发现未解释的孔。构成为：

- [56 个 PAD 孔](../../validation/native-final-tht-drill-expectations.json)：52 PTH + 4 NPTH。J2 为 `C456017 / AF 10.0 HC6.3`，四孔 Ø1.0 mm，两槽 2.1×0.8 mm，长轴沿 PCB Y。
- [两个 J1 定位孔](../../validation/native-final-nonpad-hole-expectations.json)：Ø0.6 mm，来自 Multi-Layer FILL，实际 CAM 中为 NPTH。
- [189 个 VIA](../../validation/native-final-via-drill-expectations.json)：全部中心和直径一致。合并 PTH 文件有 241 孔，NPTH 有 6 孔；VIA-only 辅助钻孔文件的 189 孔已证明为合并 PTH 的严格子集，不能再重复加工。

[128 个新增/恢复的普通过孔](../../validation/native-final-tented-via-expectations.json)在实际顶、底阻焊图形中均覆盖；孔边到最近开口的保守最小距离为 **0.10363 mm**，通过 0.10 mm 门限，未放宽门限。此依据仅适用于本版的**绿色阻焊、外层 1 oz**。实际图形验收包含开口极性和镂空，未用 API 的盖油字段代替 CAM。

U2/U3 内共四颗 Ø0.20/0.50 mm 的原有 EP 过孔采用树脂填孔、研磨及盖铜（VIPPO/POFV），与上述普通盖油孔分开处理，见[焊盘内孔工艺](../electrical/ground-and-vippo.zh-CN.md)。实际 Top Paste 已确认 U2 四个 1.49 mm 圆角窗、覆盖率 72.4233%；U3 四个 0.65 mm 圆角窗、覆盖率 58.1806%；两者窗间桥均为 0.20 mm。分窗不能代替填孔盖铜，详细依据见[钢网说明](../electrical/qfn-stencil.zh-CN.md)。

实际顶面、底面和顶层钢网已渲染并目视核对外形、J2 双槽、四安装孔、QFN 开窗、功能接口/档位及极性标记，见[看图记录](../../validation/native-final-gerber/visual-review.json)。六处功能丝印和四档图例的实际墨迹到阻焊开口/板边均超过 0.15 mm；普通密集位号存在局部拥挤或裁切，不宣称全部位号排版理想。R1/R2 的凹口锡膏图形已证明来自原厂库显式开窗，C5/C1 为矩形，见[局部锡膏核对](../../validation/native-final-gerber/stock-passive-paste.json)，未因此改动封装。

## 可复现检查

以下命令读取本次实际保存源和原始 CAM。Python 环境需要 gerbonara 1.6.3、Shapely 2.1.2；预览使用 Sharp/librsvg。

```sh
python tools/inspect_gerber.py hardware/manufacturing/Calxus_RevA_Gerber.zip \
  --output validation/native-final-gerber \
  --pcb validation/native-r7-pads-audit.json \
  --stencil hardware/electrical/ep_stencil_proposal.json \
  --drill-expectations validation/native-final-tht-drill-expectations.json \
  --nonpad-hole-expectations validation/native-final-nonpad-hole-expectations.json \
  --via-expectations validation/native-final-via-drill-expectations.json \
  --tenting-expectations validation/native-final-tented-via-expectations.json
python tools/repair_gerber_preview_outline.py validation/native-final-gerber
node tools/render_gerber_previews.cjs validation/native-final-gerber
```

`native-r7-pads-audit.json` 仅提供保持不变的安装孔参考；全部当前 PAD/VIA/额外定位孔均由本次 `native-final-*` 合同检查。位置与通孔尺寸 0.025 mm、过孔直径 0.01 mm、槽轴 1° 是导出名义几何比较阈值，不是板厂加工公差。默认原点偏移为零；不自动缩放、旋转或镜像使结果通过。

[钻孔](../../validation/gerber-drill-inspector-software-checks.json)、[非 PAD 孔](../../validation/gerber-nonpad-hole-inspector-software-checks.json)和[阻焊](../../validation/gerber-mask-inspector-software-checks.json)检查器的拒错回归另有记录。pre-UP 采样中的两处阻焊失败保留在[历史采样](../../validation/history/native-hole-adoption-cam-sample/gerber-validation.json)，本次实际最终导出已重新逐孔验收，未沿用历史采样状态。

本目录的通过结论属于原型制造文件的几何核对；不代表板厂已接单、贴装机方向已批准、焊接工艺已验证、USB 信号完整性或实物功能已通过。全局 Netlist Error 的原因尚待原生 GUI 进一步确认，因此制造放行保持未通过。
