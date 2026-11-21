# 嘉立创原生工程与导出文件

统一入口为 [Calxus_RevA.epro2](../hardware/native/Calxus_RevA.epro2)，346898 字节，SHA-256 `40d27f61240cb3974f0bd0ecc4c996582f56a4a142598cf3a2e6bce84b4ce4ac`。它是本机实际保存、重新打开、重铺两块地铜后导出的完整工程，与原始导出文件 `Calxus_RevA_final.epro2` 字节相同；不是把离线候选改名冒充原生导出。

`.epro2` 是嘉立创专业版 ZIP 容器，内含工程元数据、`.epru` 原生记录流，以及依赖的符号、器件、封装；用“导入专业版工程”打开。离线工作目录采用 `.eprj3` 索引、`.esch2` 原理图、`.epcb2` PCB 及库/配置。需保存整个目录，单独复制索引不足以恢复。单页源码不能改名当作完整工程。

最终保存源有 1508 条铜线记录、189 个过孔、97 个器件及两个已重建铺铜区域。原生画布 API 返回 1493 条线；少的 15 条均小于 0.1 mil，已逐条证明完全被同网铜覆盖，差异与实际铜几何无关，见[数量差异证据](../validation/native-final-line-count-reconciliation.json)。不把源记录数和画布原语数混写成一个未经核对的数值。

原生网表与保存源均已核对 97 个器件、345 个逻辑引脚、21 个 NC；PCB 含测试点为 120 位号、368 个电气焊盘。原生 ERC 只有两条 `SHOWDANDLING`，对应 U2 GPIO30/31 接 PCB-only TP20/21；没有 error/fatal。三页在 metadata 同步后分别保存、关闭、重开，库关联和位置再次核对。

**制造放行仍为 `false`。** 原始 PCB DRC 保留 4 项：3 项经过审查的总线段长度统计例外（USB_UP / USB_SIL / USB_UART），1 项空详情的全局 `Netlist Error`。飞线、连接、净距及物理错误为 0。独立引脚图一致和正确 Board 绑定不等于原生关联诊断通过。

在独立诊断副本上，保存/重开、官方 `pcb_Net.setNetlist` 的 PCB 自身及原理图网表回写、一次 `pcb_Document.importChanges` 均实际执行并有保存结果；受保护的铜、位置、引脚网络、铺铜和规则没有改变，错误仍存在。没有进一步猜测性修改；原始交付源未被诊断操作改动。详见[受限原生诊断](../validation/native-netlist-reference-diagnostic.json)。当前不能确认它是 API 缓存、导入基准或其他原因，也不能把未知错误豁免为“软件 bug”。

本次 [原生 PDF](../hardware/schematic/Calxus_RevA_schematic.pdf) 已真实导出并解包，三页 A2 图框、当前 J2 独立 5/6 屏蔽脚及竖向标签均实际看图通过。原生导出附加边距后 MediaBox 为约 596.138×422.331 mm；保留原始字节，没有暗中裁成 594×420 mm。Gerber 与 SMT 文件的独立结果见[制造文件说明](../hardware/manufacturing/README.md)。

## 原生导入路径

官方 API 支持以下调用；这是工程归档导入，不是原理图更新 PCB。所有导入、重新绑定和画布操作应由当前拥有 EDA 画布的任务串行执行。

```js
const file = await eda.sys_FileSystem.readFileFromFileSystem(archivePath);
if (!file) throw new Error('Missing native project archive');
const imported = await eda.sys_FileManager.importProjectByProjectFile(
  file,
  'JLCEDA Pro',
  undefined,
  {
    operation: 'Offline Client Local Path',
    folderPath: destinationFolder,
    fileFormat: 'eprj3'
  }
);
if (!imported?.uuid) throw new Error('Native project import failed');
```

该模式只适用于客户端半离线/全离线环境，要求扩展有外部交互权限；目标中存在同名工程时会报错，不覆盖现有工程。`fileFormat` 的原生枚举值是小写 `eprj3`。返回的项目 UUID 由本地工程绝对路径派生，不能沿用旧项目 UUID；必须读取实际导入结果、重新枚举文档，并在修改前核对页名、PCB 名及元件原语 ID。

导入的返回类型为 `IDMT_BriefProjectItem`，包含 `uuid`、`friendlyName` 等简略属性，不包含本地绝对路径；需从指定的 `folderPath` 实际列目录确认生成文件。接口文档没有保证导入会自动打开工程。保存并备份当前工程后，显式调用 `dmt_Project.openProject(imported.uuid)`，核对返回值，并在工程树就绪后读取 `getCurrentProjectInfo()` 的文档树。`openProject` 本身不激活原理图或 PCB；执行画布 API 前仍需打开、激活目标文档并等待就绪。它也不会替旧工程保存尚未保存的修改。

## 独立核验

`tools/check_native_project_archive.py` 直接读取归档内实际 COMPONENT 坐标、嵌入 SYMBOL/PIN、WIRE/LINE/NET 和 NO_CONNECT 属性；符号的 J2 水平镜像也纳入检查。该工具的固定零旋转版面支持范围在源码中明确，不是通用 EDA 渲染器。

```sh
python tools/check_native_project_archive.py hardware/native/Calxus_RevA.epro2 \
  --design hardware/electrical/calxus_design_input.json \
  --plan automation/functional-schematic-plan.json \
  --report validation/native-project-archive.json
```

实际最终报告为[归档原理图审查](../validation/native-final-schematic-archive.json)、[现场原生审计](../validation/native-final-schematic-audit.json)、[PCB 引脚网络对照](../validation/native-final-pcb-pin-net-comparison.json)和[原生 PDF 看图记录](../validation/native-final-schematic-review/review.json)。它们保留各自来源与范围；电气连接、制造孔、实际 CAM、机械装配分项记录。

`Calxus_RevA_candidate.epro2` 是此前冻结的离线完整源设计，SHA-256 `e77aa740ad789c91e3c1e894c3c8e9f85d2b5841f83941e7c9eeb572cf42a449`，1504 条线、189 个过孔、无 POURED 缓存。它用于补线和源派生总装的可复现依据，不是当前统一原生入口。源派生审阅 PDF、pre-J2 原生 PDF、preserved/native_fixed/r6/r7 快照及 pre-UP Gerber 都保留为历史证据。

## 历史恢复证据

以下两份报告均发生在 r7 J2 更换前，原有 344 引脚计数仅属于这些历史快照，不是现行电路数量。2026-11-21 的 `preserved` 检查点实测为 270382 字节，SHA-256 为 `dbcba206e916bfdf074684be270d54cc42647da1c92c3495416e428b080a916d`；其中 97 个元件坐标、344 个引脚网络、21 个显式 NC 与 97 个器件/封装/供应商关联全部通过。对应报告为 [preserved-native-project.json](../validation/preserved-native-project.json)。这是布线前恢复检查点，不是最终生产归档。

同日修正层叠与钢网窗口后的 `native_fixed` 归档实测为 264836 字节，SHA-256 为 `14633dadaf8768727c33a8bd6bf476226d26ff51e3585ab4ac5253297da68137`。重新从归档重建三页原理图，上述 97/344/21 项及 97 个库关联均通过，见 [native-fixed-schematic-archive.json](../validation/native-fixed-schematic-archive.json)。这证明补丁未改变原理图；实际重新打开、最终 PCB 布线与制造导出仍须分别验收。

`Document.save()` 的布尔返回值必须记录；官方文档将 `false` 解释为保存/上传失败。不能仅由没有异常推断保存成功，也不能把 `false` 当成“没有修改”。本项目最终交付应同时验证：原生导出文件可读、内容检查通过、重新打开后的原生网表/ERC 与 PCB DRC 一致。若导出 PDF 返回 ZIP，应保留 ZIP 原扩展，并校验解压后真实 PDF 文件头再提供 `.pdf` 文件。

## 官方依据

- [工程文件导入 API](https://prodocs.lceda.cn/cn/api/reference/pro-api.sys_filemanager.importprojectbyprojectfile.html)
- [工程文件格式枚举](https://prodocs.lceda.cn/cn/api/reference/pro-api.edmt_projectfileformat.html)
- [命令行与 EPRJ3 文件结构](https://prodocs.lceda.cn/cn/api/guide/cli.html)
- [原理图保存返回值](https://prodocs.lceda.cn/en/api/reference/pro-api.sch_document.save.html)
- [PCB 保存返回值](https://prodocs.lceda.cn/en/api/reference/pro-api.pcb_document.save.html)
