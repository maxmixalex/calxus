# Calxus 验证记录

记录日期：2026-11-21。对象：一台工程样机的设计、制造文件和固件准备。只有实际执行并保留证据的项目记为通过；资料描述、源几何检查、原生检查、实际 CAM 和实物测试各自保持范围。

当前原生交付为 `Calxus_RevA.epro2`，SHA-256 `40d27f61240cb3974f0bd0ecc4c996582f56a4a142598cf3a2e6bce84b4ce4ac`。工程已真实保存、关闭/重开和重铺两块地铜，原生 PDF、Gerber、BOM/CPL 已实际导出。**CAM 通过，制造放行仍为 false**：原始 PCB DRC 的 4 项中，3 项为逐项审查的总线段长度统计例外，另 1 项全局 Netlist Error 仍未解释。飞线、连接、净距、物理错误均为 0。

## 本次已执行

| 项目 | 实际结果 | 证据 |
|---|---|---|
| 上游固定源与固件构建 | GitHub 原生连接器获取固定提交；两次 SDCC 4.2.0 构建，5120 字节 SHA-1 与上游一致 | `firmware/validation/BUILD_RECORD.json`、`reproducibility.log` |
| EEPROM 镜像和拒错 | 完整 8192 字节镜像头/长度/校验/结束标记/FF 余区通过；五类错误镜像被拒绝 | `firmware/validation/image-format-tests.log`；镜像 SHA-256 `a56dc1ebb386ab03d0d60da3deb4c1583530f4063fd934c7f042a9fc6ba20af5` |
| 固件描述符离线读取 | 0451:E001、bcdDevice 0208、bMaxPower=100 mA；未冒称抓包 | `firmware/validation/descriptor-inspection.json` |
| 电气设计合同 | 四档选择、电源/NC、TI 极性、EEPROM 服务接口通过静态核对 | [电气记录](electrical-crosscheck.zh-CN.md)、`validation/electrical-contract-r7.json` |
| 最终原生原理图审计 | 逐页保存、关闭、重开后，97 个器件、345 个引脚、21 个 NC；位置和库关联相符，NC API=true / 源码=yes | `validation/native-final-schematic-audit.json`、`native-final-schematic-netlist-comparison.json` |
| 最终原生 ERC | 0 error/fatal；仅 U2 GPIO30/31 对 PCB-only TP20/21 两条 SHOWDANDLING | `validation/native-final-erc.json` |
| 最终归档独立重建 | ZIP 可读取；97/345/21 与实际符号/线路/NC 一致；PCB 120 位号、368 电气焊盘匹配 | `validation/native-final-schematic-archive.json`、`native-final-pcb-pin-net-comparison.json` |
| 原理图—PCB 关联范围 | 实例 UID、器件/封装、PAD_NET 与 Board 绑定逐项一致；原生全局错误仍未解释 | `validation/history/native-netlist-error-source-diagnosis.json`、`native-netlist-reference-diagnostic.json` |
| 最终原生三页 PDF | 当前 J2、5/6 GND、镜像符号和竖向标签清楚，全页无裁切；A2 图框，原生含额外页面边距 | `validation/native-final-schematic-review/review.json` |
| 最终保存源铜 | 1508 LINE / 189 VIA；新增净距与非 GND 连通通过；20 对历史微小离散偏差明示 | `validation/native-final-geometry.json` |
| 原生线数差异 | API 1493 与归档 1508 相差 15 条极短线；全部完全覆盖于同网铜，未形成额外几何 | `validation/native-final-line-count-reconciliation.json` |
| 原生 PCB DRC 与飞线 | 0 飞线/连接/净距/物理错误；原始 DRC 为 3 差分统计提示 + 1 未解释全局网表错误，不是全绿 | `validation/native-final-drc-readback-summary.json`、`native-final-drc-raw-tree.json` |
| 差分几何及原生统计口径 | 原生计全部同网 LINE 总和；实际端点主路径匹配通过，USB-C 双向到原生/A 最大差长 0.215986 mm | `validation/native-differential-length-semantics.json`、`native-final-usb-path-lengths.json` |
| 本次实际 Gerber | 四铜层、闭合 80×42 mm 板框、四个 R1 mm 圆角通过；原始 ZIP 未改 | `validation/native-final-gerber/gerber-validation.json`、`outline-corners.json` |
| 全部加工孔/槽 | 56 PAD + 2 J1 + 189 VIA = 247 唯一特征；J2 Ø1.0 和 2.1×0.8 Y 槽正确；无未解释孔 | `validation/native-final-gerber/gerber-validation.json` |
| 实际普通孔阻焊 | 128 孔双面覆盖，最小保守孔边到开口 0.10363 mm，门限 0.10 mm；绿色阻焊/外层 1 oz | 同上；4 EP VIPPO 分开 |
| 实际 QFN 钢网 | U2 四个 1.49 mm 窗、72.4233%；U3 四个 0.65 mm 窗、58.1806%；桥 0.20 mm | 同上 |
| 实际 CAM 图面 | 顶/底/钢网实际看图；功能丝印、档位、极性、安装孔与 J2 双槽核对；预览闭合弧仅显示修复 | `validation/native-final-gerber/visual-review.json`、`functional-silk.json` |
| 局部被动件锡膏核查 | R1/R2 凹口与原始库 FILL 一致；C5/C1 为矩形；未改动封装 | `validation/native-final-gerber/stock-passive-paste.json` |
| 本次原生 SMT 来源与 CSV | 87 件/34 BOM 行/87 CPL 行、52 基础/35 扩展；保留实际 Mid/角度/面，artifact-tool 实际输出 | `hardware/manufacturing/smt-native-export-validation.json` |
| 源设计派生机械总装 | 93 实装模型、114 命名对象、247 孔、16 姿态独立回读通过，7 种打印设计；不是 fresh native 全 PCBA STEP | `mechanical/validation/source-derived-assembly-roundtrip.json` |
| 最终原生机械等价与板体 | 原生源机械输入与已验证总装等价；真实板体厚 1.606203 mm、58 非 VIA 孔正确；原生 STEP 不表示 189 VIA 空洞，实际 CAM 另全部确认 | `mechanical/validation/native-final-mechanical-source-equivalence.json` 及机械验收记录 |

保存/重开、两次正式 `setNetlist` 和一次正式 `importChanges` 已在隔离诊断副本执行，受保护的几何/引脚/位置/铺铜/规则无差异，全局错误仍在。原始工程未被诊断改写；等待原生 GUI 的实际差异依据，不能无证据定性为软件故障，也没有把错误隐藏或降低规则。

历史 920/880 中断停点已由完整原生写入取代。pre-J2 图面、r6/r7 归档、离线候选和 pre-UP CAM 样本仅供追溯；其中原始失败保留，不作为本次最终验收。完整文件哈希及分项状态见[发布验收汇总](../validation/release-summary.json)。

## 尚未执行的实物项目

| 编号 | 验收步骤 | 通过依据 | 当前状态 |
|---|---|---|---|
| H01 | 首次上电、断开所有计算器与外设 | 四档供电支路对应正确；原生/A档串口电源关闭，串口两档5 V / 3.3 V / TUSB 1.8 V正常；无异常升温；记录空载电流 | 未执行 |
| H02 | EEPROM 完整写入并读回 | 8192 字节逐字节相同；校验脚本通过 | 未执行 |
| H03 | EEPROM 启动 | `10` 档断电重启 10 次，每次为 SilverLink `0451:E001` | 未执行 |
| H04 | ROM 恢复 | 拔电并断开 SCL 后，`10` 档枚举 `0451:3410`；恢复后正常启动 | 未执行 |
| H05 | 临时 RAM 下载 | 正确下载并运行；拔电后按 EEPROM 恢复；不误记为永久写入 | 未执行 |
| H06 | 四档选择 | `00/01/10/11` 各只连接目标数据路径，无两路并接；重新枚举正确 | 未执行 |
| H07 | 原生 Mini-B | 代表性计算器目录读取、双向小文件；与原装直连结果对照 | 未执行 |
| H08 | USB-A 原生路径 | 使用原装数据线的目标枚举与传输成功；记录 VBUS 负载和压降 | 未执行 |
| H09 | TI Link 电气 | Tip/Ring 空闲及拉低电平、释放上升沿、握手波形符合目标接口 | 未执行 |
| H10 | TI Connect | 固定型号、软件和驱动版本；目录及文件双向传输并核对内容 | 未执行 |
| H11 | WebTILP | 浏览器授权、WinUSB 绑定、同一型号双向传输；与 H10 分开记录 | 未执行 |
| H12 | CH343 串口回环 | 低速、9600 和 115200 等预定速率回环内容一致；无接收错误 | 未执行 |
| H13 | CASIO | 具体串口机型与 FA-124 COM 模式完成双向传输 | 未执行 |
| H14 | AUX 电气 | 3.3 V逻辑域，TX高电平约3.0–3.2 V且符合目标输入；开漏上升沿满足波特率；记录掉电反灌电流 | 未执行 |
| H15 | HP 50g / 39gs | 分机型测唤醒、串口关闭/开启及数据传输；针序和电平各自记录 | 未执行 |
| H16 | TI-Nspire 日志 | 按硬件版本核对触点与电平，115200 8N1 获取可读开机日志 | 未执行 |
| H17 | 挂起、恢复和掉电 | 所选模式符合主机允许的功耗；恢复不死锁；掉电不经尾线反供电 | 未执行 |
| H18 | 机械与线束 | 盒体无挤压、螺柱不顶 PCB、线束应力由夹具承担、切档可操作 | 未执行 |

测试每次记录：样机编号、PCB 版本、固件 SHA-256、计算器型号/硬件版本/系统版本、电脑系统、软件版本、驱动提供者和版本、主档/串口档、线材、实测电流、结果及附件。传输校验以重新接收后的内容一致为准；屏幕出现“已连接”只证明部分链路建立。

## 设计决定

最终使用 CH444G 四选一数据切换，保留原生 USB、SilverLink 与标准 COM 的独立入口。这样不需要新增运行时上位机；原生模式不引入 USB Hub。代价是每次只能选择一个 USB 功能，不能同时连接 Mini-B 与 USB-A，或同时枚举 SilverLink 与 UART。

供电来自上行 USB；没有新增电池或独立主机控制器。具有 Host 能力的计算器作为上行主机仍需其自身驱动、VBUS 能力和正确的主机线。对 HP/Nspire 等专用尾线，确认针序与电平属于实物验收的一部分。
