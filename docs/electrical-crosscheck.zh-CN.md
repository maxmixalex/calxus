# 独立电气核对记录

日期：2026-11-21。对象是 CH444G 四档 RevA / r7 版本，核心 PCB 80×42 mm、外壳 86×48×19 mm。审查输入为 `calxus_design_input.json` 的 r7 修订版：120 个位号、69 个有名网络，其中 23 个 TP 为仅 PCB 测试焊盘，原理图范围为 97 个器件、345 个引脚。

本次逻辑审查通过；脚本结果见 [electrical-contract-r7.json](../validation/electrical-contract-r7.json)。它记录输入文件 SHA-256、与放置坐标无关的逻辑引脚表 SHA-256、逐项结果和实际推导的开关状态。该结论针对设计输入，不能代替实际 EDA 网表等价检查、PCB 连通检查或样机实测。

## 核对依据和方式

先读取器件手册的真实引脚用途，再与设计输入逐项比较。检查器不直接采用输入文件中的档位结果，而是用 Alps SSSS224100 官方触点表、D11–D15 的实际阳极/阴极方向推导选择码和供电使能。USB-C 的合并触点、TUSB 的裸露焊盘 33、CH343P 的裸露焊盘 17 则按本工程实际嘉立创库几何核对；原理图符号内部 UUID 不当作物理引脚号。

| 项目 | 核对结果及实际含义 |
|---|---|
| USB-C | A6/B6 同为 D+；A7/B7 同为 D−；CC1/CC2 各自 5.1 kΩ 到地；VBUS 与 GND 分组符合实际库；SBU 未接 |
| USB-A J2 | C456017 弯插母座；1=VBUS、2=D−、3=D+、4=GND；独立固定脚 5/6 均为 GND，不再使用同号屏蔽焊盘映射 |
| CH444G | YA/YB 为上行 D+/D−；四对输出依次 native、A、Silver、UART；15 脚 NC；EN# 低有效 |
| USB 供电 | 三颗 TPS2552DBVR 的 IN1/OUT6、低有效 EN3、GND2、FAULT4、ILIM5 对应正确；只有当前外部支路或串口支路被启用 |
| TUSB3410 | 3/25 脚为 3.3 V，4 脚为内部 1.8 V，8/18/28/33 接地；USB 6=D+、7=D−；TEST0/TEST1/SIN 有上拉 |
| TI 双线 | P3.3/30 脚到 Tip、P3.4/29 脚到 Ring。NPN 发射极为 GPIO、集电极为计算器线；并联肖特基阳极在 GPIO、阴极在计算器线，与 SilverLink B 参考电路一致 |
| TUSB 挂起 | D10 阳极 VREGEN、阴极 SUSPEND；15 kΩ、32.4 kΩ 与复位电容连接符合 TI 总线供电建议。90.9 kΩ/100 kΩ 保持分压理想空载值约 1.729 V，不能把肖特基低电平压降误当成 1.8 V 电源 |
| CH343P | VDD5/VBUS 在 5V_SERIAL，VIO 为 3.3 V，V3 只按手册去耦；USB 7=D+、8=D−；EP=17 接地；未用脚明确 NC |
| UART | TX 用 SN74LVC1G07 非反相开漏，RX 用 SN74LVC1G17 非反相缓冲。J7 同时选 RX/TX，CASIO/AUX 不并联；CASIO 直插公头 Tip=计算器TX、Ring=计算器RX，与原作者实测接法一致；J6 第 4 针 NC |
| UART 掉电反灌 | D16 阳极 3V3、阴极 UART_PULLUP；R28/R31 从该隔离节点上拉，阻断尾线经上拉电阻回到关闭的 3V3 电源。输入/输出缓冲还依赖自身 Ioff 能力；实际漏电待测 |
| EEPROM | 24LC64 A0/A1/A2 接地，地址 0x50；J9 单独可断 SCL。J8 依次为 EE_VCC、GND、EE_SCL、EE_SDA、EE_WP、SIL_RESET。J10 短接允许写入；R23/R25 可在断电时隔离 SDA/EEPROM 电源 |
| 网络完整性 | 所有有名网络至少有两个节点；关键 NC 和电源节点逐脚检查；电容均有地回路且两端不在同一网络。该检查不证明实际铜线已经完成 |

## 四档状态推导

| SW1 档位 | 官方触点闭合 | IN1 IN0 | CH444 数据对 | 唯一启用的电源 |
|---|---|---|---|---|
| NATIVE | 1–3，6–8 | 00 | USB_NATIVE_DP/DM | VBUS_NATIVE |
| USB-A | 2–3，7–8 | 01 | USB_A_DP/DM | VBUS_USBA |
| SILVER | 3–4，8–9 | 10 | USB_SIL_DP/DM | 5V_SERIAL |
| UART | 3–5，8–10 | 11 | USB_UART_DP/DM | 5V_SERIAL |
| 两刀均开路的间隙 | 无 | 11 | EN# 高，数据断开 | 无 |

5V_SERIAL 同时供给 TUSB3410 和 CH343P，CH444 只选择其中一个数据接口。表中的开路间隙模型不覆盖两个机械刀片的偏斜、触点反弹与电源建立时间，因此使用说明要求拔下上行 USB 后切档；不能据此宣称已验证带电无缝切换。

## 审查中已落实的修正

1. 最终 BOM/引脚表加入 D16 后，发送高电平按实际二极管上拉写成约 3.0–3.2 V；接收和发送的逻辑域仍是 3.3 V。目标输入阈值、线缆电容和 115200 波特率下的上升沿须实测。
2. 首次上电步骤已与分支电源一致：原生/A 档检查串口电源关闭，断电切到 Silver 档后才测 3.3 V、TUSB 1.8 V、复位和晶体。旧步骤在原生档期待 TUSB 起振已删除。
3. 暴露焊盘按实际库使用 TUSB 33、CH343P 17；没有继续使用资料图中的 EP/0 字符直接接网。
4. EEPROM 恢复使用可拆的 J9 SCL 跳帽；外部独立编程同时隔离 R23 与 R25，避免向掉电主板反供电。WP 只保护写入，不能绕过读取旧镜像。

## 电流与反向电流边界

从本次实际重建的 5120 字节固件中读出配置描述符模板：`bMaxPower = 0x32`，即 100 mA；VID/PID 为 0451:E001。见 [离线描述符检查](../firmware/validation/descriptor-inspection.json)。这不是主机枚举抓包。40 mA 是串口支路普通工作设计预算，需测整机而非只看单颗芯片电流。

226 kΩ 的串口限流设置约为 101.3/120.0/142.1 mA（最小/典型/最大）；52.3 kΩ 的两个原生输出支路约为 448.3/501.6/562.4 mA。它们是故障限制，不能当作主机授权的可用电流。USB 设备配置前、配置后及挂起时分别按对应主机和设备要求验收，外部设备的充电也计入预算。

TPS2552 反压保护不是理想二极管：本次手册电气表给出 95–190 mV 的反压判定阈值及 3–7 ms 的关闭响应，期间可能出现反向电流。原生尾线应连接设备角色，USB-A 不接另一台供电主机。掉电反灌、未选桥接芯片的挂起状态、整机挂起总电流、浪涌和 VBUS 压降仍列入实物验收，尚未记为通过。

## 实际 EDA 输出比较

比较器为 [compare_netlists.py](../tools/compare_netlists.py)。默认 `--scope schematic` 明确排除输入里标记 `pcb_only` 的 23 个 TP；其余 97 个器件必须与实际原理图导出的物理引脚号、网名和整个同网引脚组一致。`--scope pcb` 则包含全部 120 个位号及测试焊盘。

```sh
python tools/check_electrical_contract.py path/to/calxus_design_input.json --output validation/electrical-contract.json
python tools/compare_netlists.py --scope schematic --design path/to/calxus_design_input.json --actual path/to/actual-schematic-netlist.json --output validation/schematic-netlist-comparison.json
python tools/compare_netlists.py --scope pcb --design path/to/calxus_design_input.json --actual path/to/actual-pcb-netlist.json --output validation/pcb-netlist-comparison.json
```

本次最终三页原理图在 metadata 同步、逐页保存/关闭/重开后，97 个器件、345 对物理 pin/net、21 个 API=true / 源码=yes 的 NC 均一致，库关联和坐标全部匹配。见[实际原生网表对照](../validation/native-final-schematic-netlist-comparison.json)、[原生审计](../validation/native-final-schematic-audit.json)和[最终归档重建](../validation/native-final-schematic-archive.json)。J2 的独立屏蔽脚 5/6 均接地；U2 GPIO30/31 的同网 TP 只在 PCB 范围，所以原生 ERC 的两条 `SHOWDANDLING` 是预期单节点提示，没有 error/fatal。

最终 PCB 源包含 120 位号、368 个电气焊盘，与审查输入全部匹配，见[PCB 对照](../validation/native-final-pcb-pin-net-comparison.json)。自由测试焊盘 TPn 映射为相应测试点逻辑 1 脚，原始网名保留。原理图—PCB 的实例 UID、器件/封装、345 个 PAD_NET 复合键、21 个 NC 和 Board 关联另有独立核对；该结果不能替代客户端仍报出的全局网表诊断。

依据：TI TUSB3410 SLLS519J（引脚、图 6-11）；WCH CH440 系列本次实际下载版本 3E（§4.4、逻辑门限）；CH343 v2.0（引脚、电源、挂起）；TI TPS2552 SLVS841G（DBV 脚位、反压保护、限流）；Alps SSSS224100 官方电路图；SilverLink B 参考原理图；SN74LVC1G07/17 数据手册。原始链接见[技术来源索引](sources.md)。

## 最终保存源、铜与制造输出复核

统一原生归档 SHA-256 为 `40d27f61240cb3974f0bd0ecc4c996582f56a4a142598cf3a2e6bce84b4ce4ac`。源铜审查见[最终几何报告](../validation/native-final-geometry.json)：新增铜净距及非 GND 连通通过；既有高速记录 20 对极小源离散偏差明确保留，最大低于名义 6 mil 约 0.000025 mm。实际原生地铜已重铺，飞线为 0；源解析与原生结果分别记录。

原生原始 DRC 仍为 4 项：USB_UP / USB_SIL / USB_UART 三条总 LINE 长度统计例外和一条全局 `Netlist Error`；连接、净距、物理错误均为 0。长度统计与原生 `getNetLength` 以及保存源线长总和已逐项对应，见[统计口径证据](../validation/native-differential-length-semantics.json)。按真实宽铜接触关系求主路径，两种 USB-C 翻转入口到 Mini-B/USB-A 的最大差长为 0.215986 mm，低于 0.254 mm；SIL 为约 0.122045 mm，UART 为约 0.001643 mm，见[最终主路径报告](../validation/native-final-usb-path-lengths.json)。这属于几何核对，不是电磁仿真或 USB 实测；规则未放宽、提示未隐藏。

全局网表错误在隔离副本经过保存/重开、两次正式 setNetlist 和一次正式 importChanges 后仍存在，保护范围差分为零。原始工程保持不变；不能仅凭引脚图相等宣称错误已解决，见[诊断记录](../validation/native-netlist-reference-diagnostic.json)。因此制造放行保持 false。

实际最终 CAM 已验证 56 个 PAD 孔、2 个 J1 定位孔及 189 个 VIA，共 247 个孔/槽；128 个指定普通过孔双面阻焊桥最小 0.10363 mm，四颗 EP VIPPO 单独按工艺处理。两颗 QFN 各四个钢网开窗及 0.20 mm 桥均通过。四铜层、80×42 mm 闭合板框、四角圆弧和实际图面已检查，见[CAM 报告](../validation/native-final-gerber/gerber-validation.json)。这些通过项没有消除独立保留的原生网表错误，也不证明实物功能。

本次重新导出的原生 BOM/CPL 已筛选并实际生成 87 件 SMT / 34 行 BOM / 87 行 CPL；原生 Mid 坐标、角度和面别保留，见[贴装记录](../hardware/manufacturing/smt-native-export-validation.json)。
