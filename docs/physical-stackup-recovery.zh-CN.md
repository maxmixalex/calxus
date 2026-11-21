# 物理叠层恢复与导出校验

本文保留 r6 恢复过程和其离线检查证据；其中 97/344/21 与 139 条线、61 个过孔只描述当时快照。现行 r7 为 97 个原理图器件、345 个引脚网络、21 个 NC；最终制造状态以[发布汇总](../validation/release-summary.json)为准。

当前客户端的 `setDocumentSource()` 能使 `getStackup()` 暂时显示修改值，但本项目已实测：同一时段的 STEP 板体仍混用旧物理层参数，重新打开 PCB 后 API 也恢复为默认叠层。因此，[原来的画布源码脚本](../automation/lceda_stackup.js) 仅作为诊断历史保留，不应作为制造叠层已经保存的证明。`getStackup()`、原生归档、重新打开后的读回和 STEP 板体必须分别检查。

当前已验证的离线修补器是 [patch_native_stackup.py](../tools/patch_native_stackup.py)。它只修改完整 `.epro2` 归档中目标 PCB 的物理层记录及三个介质层定义；所有元件、原理图、引脚网络、走线、过孔、板框、铺铜和其他记录逐字节保留。输入文件不会被覆盖，输出必须使用新文件名。尚未完成的原生导入及 STEP 验证会在报告中明确标为 `false`。

## 固定目标

选择 JLC04161H-7628，名义成品厚度 1.6 mm；记录物理层总和含两面 0.01 mm 阻焊为 1.6062 mm。厚度与介电常数以 [阻抗证据](../hardware/electrical/usb_impedance_evidence.json) 的当前 NP-155F 模板为准。外层线路参考 PP 的 Er=4.4，内层芯板 Er=4.38。

| 从上至下 | 原生层 ID | 厚度 mm |
|---|---:|---:|
| 顶阻焊 | 5 | 0.0100 |
| 顶铜 | 1 | 0.0350 |
| PP7628 | 361 | 0.2104 |
| L2 铜 | 15 | 0.0152 |
| 芯板 | 362 | 1.0650 |
| L3 铜 | 16 | 0.0152 |
| PP7628 | 363 | 0.2104 |
| 底铜 | 2 | 0.0350 |
| 底阻焊 | 6 | 0.0100 |

另保留四个零厚度丝印/锡膏物理层，共 13 条 `LAYER_PHYS`。物理顺序由 `zIndex` 决定。当前客户端导出的记录厚度实测采用 mil，修补器按 `mm / 0.0254` 写入；`doc.format` 对此字段的 0.1 mm 单位注释与实际归档及 STEP 数值不一致，不能据该注释重算。修补器会先校验原始外铜厚度量级；遇到未知物理层、重复层键、目标 PCB 不唯一或非四层板时拒绝处理。

## 正式恢复步骤

1. 等原生布线正常完成并保存，从当前完整工程导出新的 `.epro2`。布线前的 `preserved` 文件只用于修补器离线试验，不能替代最终归档。
2. 在项目根目录执行下列命令。若同时应用 EP 钢网四窗修补，两者修改作用域不相交，可串行组合；最后必须检查组合输出。

```sh
python tools/patch_native_stackup.py /path/Calxus_fresh.epro2 \
  /path/Calxus_stackup_fixed.epro2 \
  --report validation/physical-stackup-final-patch.json

python tools/check_native_project_archive.py /path/Calxus_stackup_fixed.epro2 \
  --design hardware/electrical/calxus_design_input.json \
  --plan automation/functional-schematic-plan.json \
  --report validation/physical-stackup-final-schematic-audit.json
```

3. 由当前拥有 EDA 画布的操作方，通过官方工程导入 API 将输出导入新的 EPRJ3 目录，实际调用和项目重新绑定要求见 [原生工程说明](native-project.zh-CN.md)。不要用 `setDocumentSource()` 把修补后的记录再塞回旧活动页，也不要覆盖已有工程目录。
4. 重新枚举并核对实际项目、PCB 和原理图；读回 `getStackup()`，检查 1、15、16、2 铜层顺序、两层 0.2104 mm PP、1.065 mm 芯板和总厚度。保存后关闭并从新 EPRJ3 目录重新打开，再读回相同数据。保存布尔值和归档 SHA 应进入验证记录。
5. 导出仅板体 STEP，使用实体包围盒确认板框、4 个安装孔和实际厚度。厚度应与 1.6062 mm 物理总和相符，允许原生 mil 换算的小数舍入；仍出现 2.9059 mm 时恢复尚未成功。随后导出完整 PCBA STEP，按机械 datum 检查接口、元件、紧固件、滑块全行程和装配干涉。

最终机械装配检查针对实际完整 PCBA；此前只板体诊断和名义元件包络检查不能替代该结果。外壳不会为错误的 2.9 mm 板厚扩大。

## r6 恢复候选中的安装孔禁布圈

实际 r6 完整归档还暴露了独立问题：四个安装孔的两面禁布圈中心 Y 为负值，原生 JRouter 导出没有包含这些安装圈。当前客户端 `PCB_PrimitiveRegion.modify()` 的几何字段是 `complexPolygon`；此前传入 `polygon` 并未实现该修改。`PCB_PrimitivePour.modify()` 也使用 `complexPolygon`。项目 automation 已核对这两个实际字段，并在更新后重新读取源码几何，而非仅凭返回对象判断成功。

经确认后，[patch_native_mount_keepouts.py](../tools/patch_native_mount_keepouts.py) 只将这 8 条已知 CIRCLE 的中心 Y 改正，保留记录头及其他所有字段。可在叠层、EP 修补后运行：

```sh
python tools/patch_native_mount_keepouts.py /path/Calxus_layers_paste_fixed.epro2 \
  /path/Calxus_native_fixed.epro2 \
  --report validation/native-r6-mount-keepout-patch.json
```

当时待导入的 r6 恢复候选保留 **139 条导线、61 个过孔、2 个 GND 铺铜及 TP6=(28,23.5) mm**。它是恢复基线，普通布线仍未完成；不能把它称为完整已布线生产板。导入新工程后，还要重新 `Region.get(id)` 读取 `getState_ComplexPolygon()`，并检查 JRouter 的实际障碍区域包含四个安装圈。原生导入、重开和这些引擎检查应另记结果，离线修补通过并不代表它们已完成。

## r6 历史离线检查

- [修补器试验报告](../validation/physical-stackup-offline-patch-dryrun.json)：布线前恢复归档上 12 条修改/新增记录；非层源码字节及其他 ZIP 条目均保持不变。
- [独立原理图审计](../validation/physical-stackup-offline-schematic-audit.json)：97 个元件、344 个引脚网络、21 个明确 NC 均通过。
- [源码与 API 研究记录](../validation/physical-stackup-source-research.json)：记录单位矛盾、实际导出器旧参数证据和当前 API 可用性。
- [几何状态恢复检查](../validation/geometry-state-recovery-offline.json)：离线模拟失效缓存 ID、缺失单个图元及重复运行，验证重用现有图元、恢复缺项、正 Y 几何和不重复创建；这不是原生画布运行结果。

官方 `overwriteCurrentPhysicalStackingConfiguration` 标注自 EDA v4.2 新增；本次客户端为 v4.1.105，原生文档和实际只读查询未提供可用物理配置对象，因此本次不依赖该接口。后续升级后仍应保留保存、重开和 STEP 的独立核验。
